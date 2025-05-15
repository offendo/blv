#!/usr/bin/env python3
import argparse
import json
import logging
import os
import subprocess as sp
import threading as t
import time
from pathlib import Path

from rq import Queue, SimpleWorker, Worker
from rq.timeouts import JobTimeoutException
from rq.job import Job
from rq.utils import now
from datetime import timedelta, datetime

from pyleanrepl.config import Config
from pyleanrepl.repl import LeanRepl

logging.basicConfig(level=logging.INFO)

def handle_timeout_exception(job, exc_type, exc_value, traceback):
    if isinstance(exc_value, JobTimeoutException):
        # repl = job.kwargs["repl"]
        # logging.info(f"failure in repl: pid={repl.proc.pid}")

        # new_pid = repl.reset()
        # logging.info(f"rebooted repl: new pid={new_pid}")
        return True
    return False


class VerifierWorker(Worker):
    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Boot the repl
        self.repl = LeanRepl(repl_path=Config.repl_path, project_path=Config.project_path, backport=Config.backport)
        self.pid = self.repl.open()
        logging.info(f"successfully booted repl: pid={self.pid}")

        # Import necessary items
        tik = time.time()
        import_string = "\n".join(Config.imports or []) or "import Mathlib"
        self.repl.interact(import_string)
        tok = time.time()
        log_str = import_string.replace('\n', ', ')
        logging.info(f"{log_str} in {tok-tik:0.2f}s")

        self.push_exc_handler(handle_timeout_exception)

    def execute_job(self, job: Job, queue: Queue):
        # Attach the REPL instance to the job
        job.kwargs["repl"] = self.repl
        return super().execute_job(job, queue)

    @property
    def should_run_maintenance_tasks(self):
        maintenance_interval = timedelta(seconds=Config.maintenance_interval_seconds)
        if self.last_cleaned_at is None:
            return False
        if (now() - self.last_cleaned_at) > maintenance_interval:
            return True
        return False

    def run_maintenance_tasks(self):
        """
        Runs periodic maintenance tasks, these include:
        1. Check if scheduler should be started. This check should not be run
           on first run since worker.work() already calls
           `scheduler.enqueue_scheduled_jobs()` on startup.
        2. Cleaning registries
        """
        # No need to try to start scheduler on first run
        if self.last_cleaned_at:
            if self.scheduler and not self.scheduler._process:
                self.scheduler.acquire_locks(auto_start=True)
        new_pid = self.repl.reset(Config.imports)
        logging.info(f"reset repl: new pid {new_pid}")
        self.clean_registries()


if __name__ == "__main__":
    parser = argparse.ArgumentParser("client")

    # data
    parser.add_argument("--repl", type=str, required=True)
    parser.add_argument("--backport", action="store_true")

    # redis stuff
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=6379)
    parser.add_argument("--db", default=0)

    args = parser.parse_args()

    worker = VerifierWorker(
        repl_path=args.repl,
        project_path=args.repl,
        backport=args.backport,
    )

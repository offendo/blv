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

class VerifierWorker(SimpleWorker):
    def __init__(
        self,
        *args,
        repl_path: str = Config.repl_path,
        project_path: str = Config.project_path,
        backport: bool = Config.backport,
        imports: list[str] = Config.imports,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        # Boot the repl
        self.repl = LeanRepl(repl_path=repl_path, project_path=project_path, backport=backport)
        self.pid = self.repl.open()
        logging.info(f"successfully booted repl: pid={self.pid}")

        # Import necessary items
        import_string = "\n".join(imports)
        log_str = import_string.replace('\n', ', ').replace('import', '')
        out = self.repl.interact(import_string)
        logging.info(f"imported {log_str} in {out['time']:0.2f}s")

    def execute_job(self, job: Job, queue: Queue):
        # Attach the REPL instance to the job
        job.kwargs["repl"] = self.repl
        return super().execute_job(job, queue)

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

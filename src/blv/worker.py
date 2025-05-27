#!/usr/bin/env python3
import argparse
import json
import logging
import os
import subprocess as sp
import threading as t
import time
from datetime import datetime, timedelta
from pathlib import Path

from rq import Queue, SimpleWorker, Worker
from rq.job import Job
from rq.timeouts import JobTimeoutException
from rq.utils import now

from blv.config import Config
from blv.repl import LeanRepl
from blv.utils import make_header_key, Timer, parse_header

logging.basicConfig(level=logging.INFO)


class VerifierWorker(Worker):
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
        self.repl = LeanRepl(
            repl_path=repl_path, project_path=project_path, backport=backport
        )

        # Import necessary items
        import_string = "\n".join(imports)
        log_string = import_string.replace("import ", "").replace("\n", "/")
        with Timer(f"imported {log_string}: " + "{}", logging.info):
            header, theorem = parse_header(import_string)
            out = self.repl.query(theorem, header)

    def execute_job(self, job: Job, queue: Queue):
        # Attach the REPL instance to the job
        job.kwargs["repl"] = self.repl
        return super().execute_job(job, queue)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("client")

    # data
    parser.add_argument("--repl", type=str, required=True)
    parser.add_argument("--backport", action="store_true")
    parser.add_argument("--imports", nargs="+", type=str, required=False, default=[])

    # redis stuff
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=6379)
    parser.add_argument("--db", default=0)

    args = parser.parse_args()

    worker = VerifierWorker(
        repl_path=args.repl,
        project_path=args.repl,
        backport=args.backport,
        imoprts=args.imports,
    )

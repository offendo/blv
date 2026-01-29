#!/usr/bin/env python3
import logging

from rq import Queue, SimpleWorker
from rq.job import Job

from blv.config import Config
from blv.repl import LeanRepl
from blv.utils import Timer, parse_header

class VerifierWorker(SimpleWorker):
    def __init__(
        self,
        *args,
        repl_path: str = Config.repl_path,
        project_path: str = Config.project_path,
        backport: bool = Config.backport,
        imports: list[str] = Config.imports,
        max_jobs: int | None = Config.max_jobs,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.INFO)

        # Save attributes
        self.repl_path = repl_path
        self.project_path = project_path
        self.backport = backport
        self.max_jobs = max_jobs
        self.imports = imports

        # Boot the repl
        self.repl = self.spawn_repl()
        self.completed_jobs = 0

    def spawn_repl(self):
        repl = LeanRepl(repl_path=self.repl_path, project_path=self.project_path, backport=self.backport)
        repl.open_repl(self.imports)
        return repl

    def execute_job(self, job: Job, queue: Queue):
        # Restart the REPL if we're at the limit
        if self.completed_jobs == self.max_jobs:
            self.logger.info(f"Closing and relaunching repl after {self.max_jobs} jobs")
            self.repl.shutdown()
            self.repl = self.spawn_repl()
            self.completed_jobs = 0

        # Attach the REPL instance to the job
        job.kwargs["repl"] = self.repl
        return super().execute_job(job, queue)

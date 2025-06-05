#!/usr/bin/env python3
import logging

from rq import Queue, SimpleWorker
from rq.job import Job

from blv.config import Config
from blv.repl import LeanRepl
from blv.utils import Timer, parse_header

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
        self.logger = logging.getLogger(self.name)

        # Boot the repl
        self.repl = LeanRepl(repl_path=repl_path, project_path=project_path, backport=backport)

        # Import necessary items
        import_string = "\n".join(imports)
        log_string = import_string.replace("import ", "").replace("\n", "/")
        with Timer(f"imported {log_string}: " + "{}", self.logger.info):
            header, theorem = parse_header(import_string)
            out = self.repl.query(theorem, header)
            self.logger.info(f'repl returned initialization with : {out}')

    def execute_job(self, job: Job, queue: Queue):
        # Attach the REPL instance to the job
        job.kwargs["repl"] = self.repl
        return super().execute_job(job, queue)

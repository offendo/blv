#!/usr/bin/env python3
import json
import os
import subprocess as sp
import redis
from more_itertools import divide
from pathlib import Path
from typing import Any, Literal
from src.pyleanrepl.repl import LeanRepl


class VerifierWorker:
    def __init__(
        self,
        repl_path: str | Path,
        project_path: str | Path,
        backport: bool = False,
        imports: list[str] | None = None,
        *,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        protocol: int = 3,
    ):
        self.redis = redis.Redis(host=host, port=port, db=db, protocol=protocol)
        self.pubsub = self.redis.pubsub()

        # Launch the repl instance
        self.repl = LeanRepl(repl_path=repl_path, project_path=project_path, backport=backport)
        self.pid = self.repl.open()
        if not imports:
            self.repl.interact("import Mathlib")
        else:
            self.repl.interact("\n".join(imports))

    def close(self):
        self.repl.close()

    def interact(self, theorem: str):
        return self.repl.interact(theorem, environment=0)

    def work(self, theorem: str):
        self.pubsub.subscribe("unverified")


def multiprocess(
    theorems: list[str],
    n_workers: int,
    repl_path: str,
    project_path: str,
    backport: bool = False,
):
    thms_per_worker = len(theorems) // n_workers
    batches = divide(n_workers, theorems)

    workers = [LeanRepl(repl_path=repl_path, project_path=project_path, backport=backport) for _ in range(n_workers)]
    pids = [w.open() for w in workers]

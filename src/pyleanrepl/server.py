#!/usr/bin/env python3
import json
import logging
import os
import subprocess as sp
import threading as t
import time
import signal
import argparse
import uuid
from tqdm import tqdm
from pathlib import Path
from typing import Any, Literal

import redis
import pandas as pd
from more_itertools import divide

from pyleanrepl.repl import LeanRepl

logging.basicConfig(level=logging.INFO)

class VerifierWorker:
    def __init__(
        self,
        repl_path: str | Path,
        project_path: str | Path,
        backport: bool = False,
        imports: list[str] | None = None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
    ):
        self.redis = redis.Redis(host=host, port=port, db=db)
        self.repl = LeanRepl(repl_path=repl_path, project_path=project_path, backport=backport)
        self.imports = "\n".join(imports or []) or "import Mathlib"

    def close(self):
        self.repl.close()

    def listen(self):
        # Launch the repl instance
        self.pid = self.repl.open()
        logging.info(f"successfully booted repl: pid={self.pid}")
        tik = time.time()
        self.repl.interact(self.imports)
        tok = time.time()
        logging.info(f"imported Mathlib in {tok-tik:0.2f}s")

        
        self.key = f"buffer_{str(uuid.uuid4())}"
        while message := self.redis.brpoplpush("unverified", self.key, timeout=0):
            if message == b"stop":
                self.close()
                break

            try:
                thm = json.loads(message) # type:ignore
            except json.JSONDecodeError as e:
                logging.warning(f"Got malformed JSON: {message}.")
                continue

            lean_response = self.repl.interact(thm["theorem"], environment=0)
            self.redis.lpush("verified", json.dumps({"id": thm["id"], "response": lean_response}))

            # now pop it off the buffer
            self.redis.lpop(self.key)


if __name__ == "__main__":
    parser = argparse.ArgumentParser('client')

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
        host=args.host,
        port=args.port,
        db=args.db,
    )
    worker.listen()

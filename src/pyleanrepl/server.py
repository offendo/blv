#!/usr/bin/env python3
import json
import logging
import os
import subprocess as sp
import threading as t
import time
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
        protocol: int = 3,
    ):
        self.redis = redis.Redis(host=host, port=port, db=db, protocol=protocol)
        self.repl = LeanRepl(repl_path=repl_path, project_path=project_path, backport=backport)
        self.imports = "\n".join(imports or []) or "import Mathlib"

    def close(self):
        self.repl.close()

    def interact(self, theorem: str):
        return self.repl.interact(theorem, environment=0)

    def listen(self):
        # Launch the repl instance
        self.pid = self.repl.open()
        logging.info(f"successfully booted repl: pid={self.pid}")
        tik = time.time()
        self.repl.interact(self.imports)
        tok = time.time()
        logging.info(f"imported Mathlib in {tok-tik:0.2f}s")

        while message := self.redis.blpop(["unverified"], timeout=0):
            queue, data = message  # type:ignore
            if queue == b"stop":
                self.close()
                break

            try:
                thm = json.loads(data)
            except json.JSONDecodeError as e:
                logging.warning(f"Got malformed JSON: {data}.")
                continue

            lean_response = self.interact(thm["theorem"])
            self.redis.lpush("verified", json.dumps({"id": thm["id"], "response": lean_response}))


if __name__ == "__main__":
    REPL_PATH = os.path.expanduser("~/src/repl/")
    PROJECT_PATH = os.path.expanduser("~/src/repl/")
    BACKPORT = False
    N_WORKERS = 2

    DATA_PATH = os.path.expanduser("~/src/autoformalization/formalize/herald_iter3_positives_output.json")
    OUTPUT_PATH = os.path.expanduser("~/src/autoformalization/formalize/herald_iter3_positives_output_verified.json")

    threads: list[t.Thread] = []
    for _ in range(N_WORKERS):
        thread = t.Thread(
            target=VerifierWorker(repl_path=REPL_PATH, project_path=PROJECT_PATH, backport=BACKPORT).listen,
            daemon=True,
        )

        thread.start()
        threads.append(thread)
    logging.info("Launched threads")

    redis = redis.Redis(host="localhost", port=6379, db=0, protocol=3)

    df = pd.read_json(DATA_PATH, lines=True)
    theorems = df.formal_statement.str.replace("import Mathlib", "")
    redis.rpush("unverified", *[json.dumps({"theorem": thm, "id": idx}) for idx, thm in enumerate(theorems)])

    # Stop signal - very crude, should fix
    for _ in range(N_WORKERS):
        redis.rpush("stop", "stop")

    with tqdm(total=len(theorems), desc="Processing") as pbar:
        while (current_queue_size := redis.llen("unverified")) > 0:  # type:ignore
            # check queue size and update progress
            processed_items = len(theorems) - current_queue_size  # type:ignore
            pbar.n = processed_items  # directly set progress
            pbar.refresh()  # force refresh

            # simulate some processing of queue items and update progress
            time.sleep(0.1)
        processed_items = len(theorems) - current_queue_size  # type:ignore
        pbar.n = processed_items  # directly set progress
        pbar.refresh()  # force refresh

    responses = redis.lpop("verified", len(theorems))
    df["responses"] = responses
    df.to_json(OUTPUT_PATH + ".tmp")
    df["responses"] = [json.loads(resp) for resp in responses]  # type:ignore
    df.to_json(OUTPUT_PATH + ".tmp")
    df["verified"] = df["responses"].apply(lambda msgs: all([ms["severity"] != "error" for ms in msgs]))
    df.to_json(OUTPUT_PATH)

import redis
import argparse
import pandas as pd
import time
import logging
import re
import rq
from tqdm import tqdm

from pyleanrepl.repl import LeanRepl

logging.basicConfig(level=logging.INFO)


def remove_informal_prefix(formal_statement: str) -> str:
    pattern = r"/-.* -/\n"
    cleaned_text = re.sub(pattern, "", formal_statement, flags=re.DOTALL)
    return cleaned_text


def verify(theorem_id: int, theorem: str, repl: LeanRepl):
    # Process the theorem
    clean_theorem = remove_informal_prefix(theorem)
    output = repl.interact(clean_theorem, environment=0)
    return {"theorem_id": theorem_id, **output}


if __name__ == "__main__":
    parser = argparse.ArgumentParser("client")

    # data
    parser.add_argument("--data", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--num_samples", type=int, default=-1)

    # redis stuff
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=6379)
    parser.add_argument("--db", default=0)

    args = parser.parse_args()

    client = redis.Redis(host=args.host, port=args.port, db=args.db)
    queue = rq.Queue(connection=client)

    df = pd.read_json(args.data)
    df = df[: args.num_samples] if args.num_samples > 0 else df

    theorems = df.formal_statement.str.replace("import Mathlib", "").apply(lambda x: x.strip()[:2048])
    prepared_jobs = [
        queue.prepare_data(
            "src.pyleanrepl.job.verify",
            kwargs={"theorem_id": idx, "theorem": thm},
            timeout=20,
            retry=rq.Retry(max=3),
        )
        for idx, thm in enumerate(theorems)
    ]
    jobs = queue.enqueue_many(prepared_jobs)

    # Wait to start pbar until 1 at least is in the queue
    while queue.started_job_registry.count == 0:
        time.sleep(0.1)

    with tqdm(total=len(theorems), desc="Processing") as pbar:
        while (queue.finished_job_registry.count + queue.failed_job_registry.count) < len(theorems):  # type:ignore
            pbar.n = queue.finished_job_registry.count
            pbar.refresh()
            time.sleep(0.1)
        pbar.n = queue.finished_job_registry.count
        pbar.refresh()

    responses = [j.return_value() or {"theorem_id": j.kwargs["theorem_id"]} for j in jobs]
    df["responses"] = sorted(responses, key=lambda x: x["theorem_id"])  # type:ignore
    df["verified"] = responses

    df["verified"] = df["responses"].apply(
        lambda resp: len(resp) > 1
        and ("messages" not in resp or not any([ms["severity"] == "error" for ms in resp["messages"]]))
    )
    df.to_json(args.output)

    # clean up jobs
    for job in jobs:
        job.delete()

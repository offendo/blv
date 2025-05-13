"""
For personal use

Processes some theorems using the redis worker queue
"""
import redis
import argparse
import pandas as pd
import time
import logging
import re
import rq
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)

def verify_theorems(theorems: list[str]):
    client = redis.Redis(host=args.host, port=args.port, db=args.db)
    queue = rq.Queue(connection=client)

    prepared_jobs = [
        queue.prepare_data(
            "src.pyleanrepl.job.verify",
            kwargs={"theorem_id": thm_id, "theorem": thm},
            timeout=20,
            result_ttl=-1, # Keep the job forever
        )
        for thm_id, thm in enumerate(theorems)
    ]
    jobs = queue.enqueue_many(prepared_jobs)

    # Wait to start pbar until 1 at least is in the queue
    while queue.started_job_registry.count == 0:
        time.sleep(0.1)

    # Show progress bar of verified theorems
    with tqdm(total=len(jobs), desc="Processing") as pbar:
        while (queue.finished_job_registry.count + queue.failed_job_registry.count) < len(theorems):  # type:ignore
            pbar.n = queue.finished_job_registry.count + queue.failed_job_registry.count
            pbar.set_postfix({"failed jobs": queue.failed_job_registry.count})
            pbar.refresh()
            time.sleep(0.1)
        pbar.n = queue.finished_job_registry.count + queue.failed_job_registry.count
        pbar.refresh()

    responses = [j.return_value() or {"theorem_id": j.kwargs["theorem_id"]} for j in jobs]
    return responses


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

    # Load the data in our very specific format
    df = pd.read_json(args.data)
    df = df[: args.num_samples] if args.num_samples > 0 else df
    df = df.explode(['formal_statement', 'name', 'certainty_score', 'similarity_score', 'score', 'aligned']).reset_index(drop=True)
    theorems = df.formal_statement.str.replace("import Mathlib", "").apply(lambda x: x.strip()[:4096])

    # Verify the theorems
    responses = verify_theorems(theorems)

    # Postprocess the responses
    df["responses"] = sorted(responses, key=lambda x: x['theorem_id'])
    df["verified"] = df["responses"].apply(
        lambda resp: len(resp) > 1
        and ("messages" not in resp or not any([ms["severity"] == "error" for ms in resp["messages"]]))
    )
    df = df.groupby('informal_statement').agg(list)

    # Save the data
    df.to_json(args.output)

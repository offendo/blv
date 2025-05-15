"""
Processes theorems using the redis worker queue
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

def check_response_for_error(resp):
    if 'response' not in resp:
        return (True, ['timeout or other REPL error'])

    resp = resp['response']
    if 'error' in resp:
        return (True, [resp['error']])

    if 'message' in resp and len(resp) == 1:
        return (True, [resp['message']])

    if 'messages' in resp:
        errors = []
        for msg in resp['messages']:
            if msg['severity'] == 'error':
                errors.append(msg)
        return (len(errors) > 0, errors)

    return (False, [])


def verify_theorems(theorems: list[dict]):
    client = redis.Redis()
    queue = rq.Queue(connection=client)

    prepared_jobs = [
        queue.prepare_data(
            "src.pyleanrepl.job.verify",
            kwargs={**thm, "timeout": 60},
            timeout=None,
            result_ttl=-1, # Keep the job forever
        )
        for thm in theorems
    ]
    jobs = queue.enqueue_many(prepared_jobs)

    # Wait to start pbar until 1 at least is in the queue
    while queue.started_job_registry.count == 0:
        time.sleep(0.1)

    # Show progress bar of verified theorems
    tik = time.time()
    with tqdm(total=len(jobs), desc="Processing") as pbar:
        while (queue.finished_job_registry.count + queue.failed_job_registry.count) < len(theorems):  # type:ignore
            pbar.n = queue.finished_job_registry.count + queue.failed_job_registry.count
            pbar.set_postfix({"failed jobs": queue.failed_job_registry.count})
            pbar.refresh()
            time.sleep(0.1)
        pbar.n = queue.finished_job_registry.count + queue.failed_job_registry.count
        pbar.refresh()
    tok = time.time()

    responses = [j.return_value() or {"theorem_id": j.kwargs["theorem_id"], 'theorem': j.kwargs['theorem']} for j in jobs]
    logging.info(f'Verified {len(theorems)} theorems in {tok-tik:0.3f}s')
    return responses


if __name__ == "__main__":
    """ This part of the script is for personal stuff, not generalizable. You
        can replace this with whatever your data loading thing is.
    """
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
    responses = verify_theorems([dict(theorem_id=i, theorem=thm) for i, thm in enumerate(theorems)])

    def measure_stats(df, how='greedy'):
        print(f'Measuring stats for {how}', end='\n' + '='*100 + '\n')
        if how == 'greedy' and isinstance(df['verified'].iloc[0], list):
            ver = df['verified'].apply(lambda x: x[0])
            ali = df['aligned'].apply(lambda x: x[0])
            both = ver & ali
        elif how == 'topk' and isinstance(df['verified'].iloc[0], list):
            ver = df['verified'].apply(any)
            ali = df['aligned'].apply(any)
            both = df.apply(lambda row: len([i for i, (a, v) in enumerate(zip(row.aligned, row.verified)) if a and v]) > 0, axis=1)
        else:
            ver = df['verified']
            ali = df['aligned']
            both = ali & ver
        print(rf"% verified: {(ver.value_counts() / len(df))[True]*100:0.2f}")
        print(rf"% aligned:  {(ali.value_counts() / len(df))[True]*100:0.2f}")
        print(rf"% both:     {(both.value_counts() / len(df))[True] * 100:0.2f}")

    # Postprocess the responses
    df["response"] = sorted(responses, key=lambda x: x['theorem_id'])
    df['verified'] = df['response'].apply(lambda x: not check_response_for_error(x)[0])
    df['error'] = df['response'].apply(lambda x: not check_response_for_error(x)[1])
    df = df.groupby('informal_statement').agg(list)

    measure_stats(df, 'greedy')
    measure_stats(df, 'topk')

    # Save the data
    df.to_json(args.output)

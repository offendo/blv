import redis
import argparse
import pandas as pd
import json
import time
import logging
import re
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)


def remove_informal_prefix(formal_statement: str) -> str:
    pattern = r'/-.* -/\n'
    cleaned_text = re.sub(pattern, '', formal_statement, flags=re.DOTALL)
    return cleaned_text

if __name__ == "__main__":
    parser = argparse.ArgumentParser('client')

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
    client.flushdb()
    df = pd.read_json(args.data)
    if args.num_samples > 0:
        df = df[:args.num_samples]
    theorems = df.formal_statement.str.replace("import Mathlib", "").apply(remove_informal_prefix).apply(lambda x: x[:2048])
    client.rpush(
        "unverified", 
        *[json.dumps({"theorem": thm, "id": idx}) for idx, thm in enumerate(theorems)],
    )
    logging.info("Waiting for workers to start...")
    while client.llen("verified") == 0:
        time.sleep(1)

    with tqdm(total=len(theorems), desc="Processing") as pbar:
        while (current_queue_size := client.llen("verified")) < len(theorems):  # type:ignore
            pbar.n = current_queue_size 
            pbar.refresh()
            time.sleep(0.1)
        pbar.n = current_queue_size
        pbar.refresh()

    responses = client.lpop("verified", count=len(theorems))

    df["responses"] = responses
    df.to_json(args.output + ".tmp")

    df["responses"] = sorted([json.loads(resp) for resp in responses], key=lambda x: x['id'])  # type:ignore
    df.to_json(args.output + ".tmp")

    # verified if we got a positive response and there are no errors
    df["verified"] = df["responses"].apply(lambda resp: len(resp) > 0 and all([ms["severity"] != "error" for ms in resp['response'].get('messages', [])]))
    df.to_json(args.output)

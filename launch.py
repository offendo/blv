"""
Processes theorems using the redis worker queue
"""

import redis
import argparse
import pandas as pd
import time
import logging
import rq
from src.blv.verify import verify_theorems
from src.blv.utils import remove_comments

logging.basicConfig(level=logging.INFO)


def measure_stats(df, how="greedy"):
    print(f"Measuring stats for {how}", end="\n" + "=" * 100 + "\n")
    if how == "greedy" and isinstance(df["verified"].iloc[0], list):
        ver = df["verified"].apply(lambda x: x[0])
        ali = df["aligned"].apply(lambda x: x[0])
        both = ver & ali
    elif how == "topk" and isinstance(df["verified"].iloc[0], list):
        ver = df["verified"].apply(any)
        ali = df["aligned"].apply(any)
        both = df.apply(
            lambda row: len(
                [
                    i
                    for i, (a, v) in enumerate(zip(row.aligned, row.verified))
                    if a and v
                ]
            )
            > 0,
            axis=1,
        )
    else:
        ver = df["verified"]
        ali = df["aligned"]
        both = ali & ver
    print(rf"% verified: {(ver.value_counts() / len(df))[True] * 100:0.2f}")
    print(rf"% aligned:  {(ali.value_counts() / len(df))[True] * 100:0.2f}")
    print(rf"% both:     {(both.value_counts() / len(df))[True] * 100:0.2f}")


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
    client.flushdb()
    queue = rq.Queue(connection=client)

    # Load the data in our very specific format
    df = pd.read_json(args.data)
    df = df.iloc[: args.num_samples] if args.num_samples > 0 else df
    df = df.explode(
        [
            "formal_statement",
            "name",
            "certainty_score",
            "similarity_score",
            "score",
            "aligned",
        ]
    ).reset_index(drop=True)
    # theorems = df.formal_statement.str.replace("import Mathlib", "").apply(lambda x: x.strip()[:4096])
    theorems = df.formal_statement.apply(lambda x: remove_comments(x.strip())[:4096])

    # Verify the theorems
    responses = verify_theorems(
        theorems=theorems,
        connection=client,
        timeout=20,
    )

    # Postprocess the responses
    df["response"] = [r["response"] for r in responses]
    df["verified"] = [r["verified"] for r in responses]
    df["errors"] = [r["errors"] for r in responses]
    df = (
        df.groupby("informal_statement")
        .agg(list)
        .reset_index(names=["informal_statement"])
    )

    measure_stats(df, "greedy")
    measure_stats(df, "topk")

    # Save the data
    df.to_json(args.output)

"""Little script to replicate the benchmark from kimina-lean-server"""

import redis
from datasets import load_dataset
import pandas as pd

from blv.verify import verify_theorems


def benchmark_api(n):
    # Load data
    dataset = load_dataset("Goedel-LM/Lean-workbook-proofs", split="train")
    dataset = dataset.select(range(n))

    samples = [sample["full_proof"] for sample in dataset]

    # Verify the proofs
    r = redis.Redis("localhost", port=6379, db=0)
    r.flushdb()
    results = verify_theorems(samples, connection=r, timeout=60)

    # Now do a little formatting then save it
    df = pd.DataFrame(
        {
            "theorem": [s["theorem"] for s in samples],
            "response": results,
        }
    )
    df["og_theorem"] = dataset["full_proof"]
    df["verified"] = df["response"].apply(lambda x: x["verified"])
    df["errors"] = df["response"].apply(lambda x: x["errors"])

    # Print out stats
    num_valid = int(df.verified.sum())
    print(f"Found {num_valid}/{n} valid theorems")

    df.to_json("benchmark.json")


if __name__ == "__main__":
    benchmark_api(100)

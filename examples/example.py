# examples/example.py

import pandas as pd
from redis import Redis
import blv

# Supposing you have a JSON file which has a field called 'theorem' you want to verify
df = pd.read_json("examples/example-input-theorems.json")

redis = Redis(host="localhost", port=6379, db=0)

# WARNING: Only run this part if no other projects are using redis db 0!
# If you do have conflicting projects, just change the DB to something else!
redis.flushdb()

# Now launch the jobs, wait for completion, and save to disk.
examples: list[str] = [row["theorem"] for idx, row in df.iterrows()]  # type:ignore
responses = blv.verify_theorems(examples, timeout=30, flush_db_after=True)
df["response"] = [r["response"] for r in responses]
df["verified"] = [r["verified"] for r in responses]
df["errors"] = [r["errors"] for r in responses]
print(f"{sum(df.verified)}/{len(df)} valid theorems")

df.to_json("examples/example-verified.json")

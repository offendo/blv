# blv - bulk lean verifier

`blv` is a tool to verify large amounts of theorems in parallel.

It's faster than doing things one at a time, and faster than [kimina-lean-server](https://github.com/project-numina/kimina-lean-server).

It's still a work in progress (see [TODO list](#todo-list)) -  `blv` doesn't support changing imports from theorem-to-theorem yet (i.e., every theorem must have the same imports)

## Installation

`blv` uses `redis` (and python's `rq`) as a worker queue, and a custom fork of [Lean REPL](https://github.com/offendo/repl) (which supports timeouts) to handle the actual verification part.

> [!NOTE]
>
> Only Lean versions `v4.15.0` and `v4.20.0-rc5` are supported right now, but if you would like to use another version of Lean, please submit an issue and I will help you out. Some older versions might be a bit finnicky, but hopefully new ones will be easy to add.

### With Docker

The easiest way to install/use `blv` is with Docker.

```bash
export LEAN_VERSION="<your project's lean version>"
docker pull ghcr.io/offendo/blv:$LEAN_VERSION
```

### Manual Installation

Otherwise, you'll need to install a few things:

```bash
export LEAN_VERSION="<your project's lean version>"

# 1. Clone blv and install the python requirements
git clone https://github.com/offendo/blv.git
cd blv
pip install -r requirements.lock

# 2. Install elan if not already installed (Lean 4 version manager)
curl https://elan.lean-lang.org/elan-init.sh -sSf | sh

# 3. Clone the custom REPL fork and build
git clone --depth 1 --branch ${LEAN_VERSION} https://github.com/offendo/repl.git
(cd repl && lake build)

# 4. Ensure redis is installed (varies by OS)
redis-cli --version

```

## Usage

`blv` is primarily for quickly verifying a large amount of theorems/proofs in parallel. This is currently done using `rq`.

### Start the server

First step is to boot up the server:

```bash
# Copy over the template .env, and adjust anything you need
cp .env.template .env

# Launch redis & the blv workers with docker
docker compose up -d

# Or, do so manually
redis-server > /dev/null 2>&1 &
rq worker-pool -n $N_WORKERS -q --worker-class 'src.blv.worker.VerifierWorker'
```

Then you can use `blv.verify.verify_theorems` to process theorems in bulk.

> [!WARNING]
>
> This example script will wipe `redis db 0`, so **be careful if you already are using Redis for something else**!

```python
# examples/example.py

import pandas as pd
from redis import Redis
from src.blv.verify import verify_theorems

# Supposing you have a JSON file which has a field called 'theorem' you want to verify
df = pd.read_json('examples/example-input-theorems.json')

redis = Redis(host="localhost", port=6379, db=0)

# WARNING: Only run this part if no other projects are using redis db 0!
# If you do have conflicting projects, just change the DB to something else!
redis.flushdb()

# Create input examples
examples = [row['theorem'] for idx, row in df.iterrows()]

# This is the only user-facing function you need
responses = verify_theorems(examples, connection=redis, timeout=30)

# Format & save to disk
df["response"] = [r['response'] for r in responses]
df["verified"] = [r['verified'] for r in responses]
df["errors"]   = [r['errors'] for r in responses]
print(f"{sum(df.verified)}/{len(df)} valid theorems")

df.to_json('examples/example-verified.json')
```

### From Python

You can use the `LeanRepl` object directly, which is fairly straightforward. This is basically just a thin wrapper around the Lean REPL, but it communicates via TCP which I think is slightly nicer than stdio, which caused a bunch of problems before.

> [!TIP]
>
> There's no parallelization in this usage. If you have a small number of theorems to verify all using the same imports, this might suffice. For more than ~20 theorems, parallelization is pretty critical for speed, and there's really no downside to interacting via the worker queue.

```python
from blv import LeanRepl

repl_path = '/path/to/repl'  # Path to Lean REPL
proj_path = '/path/to/proj'  # Path to a Lean project with mathlib/other deps

# Initialize the `LeanRepl` object
repl = LeanRepl(repl_path, proj_path)

header = ["import Mathlib"]
ex1 = "\n".join(["def f : Nat := 5", "#print f"])
r1 = repl.query(ex1, header=header)

# Use the returned environment which now contains `f`.
ex2 = "\n".join(["def g := f + 3","#print g"])
new_env = r1.get('env')
r2 = repl.query(ex2, header=header, environment=new_env)
```

## Why use `blv`?

* The simplest reason is it's faster than the alternatives right now.
  * Also, I can't say this confidently, but it seems more stable than `kimina-lean-server` which caused a number of problems when I used it, including getting stuck, evicting workers which didn't need to be evicted, and overheating my laptop. Again, this might just have been me misusing it (and shame on me, I didn't submit an issue), so please don't take my word for it.
* It supports timeouts from the Lean side of things, which means we don't have to kill and restart a worker whenever it times out from the python side.
  * This is because I added this feature to my fork of Lean REPL.
* It can easily scale by just cranking up `N_WORKERS`, so if you have a lot of theorems and a lot of machinery, go for it.
* The code is pretty darn simple, which makes it really easy to maintain. There are only 224 lines of python code as of writing this (measured using `cloc src/`).
* More things to come.

#### TODO list

- [ ] Support different headers per theorem (i.e., implementing an LRU cache to swap workers, similar to how `kimina-lean-server` does things, but hopefully much simpler)
- [ ] Support more versions of Lean 4.
- [ ] More convenient setup/UI if you're not using Docker. Docker makes life easy in this case but I know not everyone has access to it (e.g., if they're not an admin of their machine). Ideally, it would be as simple as (1) clone, (2) boot server, (3) call `verify_theorems`
- [ ] Make project pip-installable for ease of use
- [ ] More information in the progress bar (e.g., real-time success rate)
- [ ] From the Lean side, add a Redis client so we can eliminate the subprocess wrapper...or find a better way of handling IPC.
- [ ] Try using Huey instead of `rq` to see if there's a speed increase

## Benchmarks

Stolen from [kimina-lean-server](https://github.com/project-numina/kimina-lean-server).

> [!NOTE]
>
> I did my best to approximate their benchmark, but `kimina-lean-server` benchmarks *very slow* on my machine and I didn't want to unfairly showcase their project, so I just used their numbers.

Running 60 workers on `Intel(R) Xeon(R) Gold 5220R CPU @ 2.20GHz` for the first 1000 examples of the [Goedel Prover Lean Workbook Proofs](https://huggingface.co/datasets/Goedel-LM/Lean-workbook-proofs).

| System | Time Taken | Avg. Iterations / Second | # Processes |
| ------ | ---------- | ------------------------ | ----------- |
| Kimina | 03:51      | 4:33                     | 60          |
| `blv`  | **03:03**  | **5.44**                 | 60          |

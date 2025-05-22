# blv - bulk lean verifier

`blv` is a tool to verify large amounts of theorems in parallel. It is faster than every alternative I've seen so far, including [kimina-lean-server](https://github.com/project-numina/kimina-lean-server).

It's still a work in progress - notably, `blv` doesn't support changing imports from theorem-to-theorem yet (i.e., every theorem must have the same imports). This feature will come soon, though keeping consistent headers will make verification faster.

# Installation

`blv` uses `redis` (and python's `rq`) as a worker queue, and a custom fork of [Lean REPL](https://github.com/offendo/repl) (which supports timeouts) to handle the actual verification part.

**Note:** Only Lean versions `v4.15.0` and `v4.20.0-rc5` are supported right now, but if you would like to use another version of Lean, please submit an issue and I will help you out. Some older versions might be a bit finnicky, but hopefully new ones will be easy to add. 

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

# Usage

`blv` is primarily for quickly verifying a large amount of theorems/proofs in parallel. This is currently done using `rq`. 



### With Docker

```bash
docker-compose up -d # Launch redis & the blv workers
```



```bash
❯ python -m blv -h
usage: blv [-h] [--repl REPL] [--project PROJECT] [--output OUTPUT] lean
```

As a library you can use the `LeanRepl` object directly, which is fairly straightforward
```python
from blv import LeanRepl

repl_path = '/path/to/repl'  # Path to Lean REPL
proj_path = '/path/to/proj'  # Path to a Lean project with mathlib/other deps

# Use as context manager for one-off verifications. This can be slow if you do this in a loop since it'll start/stop the Lean REPL process on open/close, which means you'll have to reload any imports every single time.
with LeanRepl(repl_path, proj_path) as repl:
  	ex1 = "\n".join(["import Mathlib", "def f : Nat := 5", "#print f"])
    r1 = repl.interact(ex1)
    # Use the returned environment, which now contains Mathlib and `f`.
    ex2 = "\n".join(["def g := f + 3","# print g"])
    new_env = r1.get('env')
    r2 = repl.interact(ex2, env=new_env) 

    
# You can also use it as an object 
repl = LeanRepl(repl_path, proj_path)
repl.open()
response = repl.interact("def f : Nat := 5")
repl.close()
```

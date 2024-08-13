# PyLeanRepl

Simple python wrapper for LeanREPL.

# Installation

```bash
pip install -U git+https://github.com/offendo/PyLeanRepl.git
```

# Usage
You can use it as a CLI or in Python
CLI: 
```bash
❯ python -m pyleanrepl -h
usage: pyleanrepl [-h] [--repl REPL] [--project PROJECT] [--output OUTPUT] lean

positional arguments:
  lean                  input file or Lean code to run through the repl

options:
  -h, --help            show this help message and exit
  --repl REPL, -r REPL  path to lean repl dir (which has been built with `lake build`)
  --project PROJECT, -p PROJECT
                        path to lean repl dir (which has been built with `lake build`)
  --output OUTPUT, -o OUTPUT
                        output path, default is stdout
```

As a library:
```python
from pyleanrepl import LeanRepl

repl_path = '/path/to/repl'  # Path to Lean REPL
proj_path = '/path/to/proj'  # Path to a Lean project with mathlib/other deps

# Use as context manager
with LeanRepl(repl_path, proj_path) as repl:
    response = repl.interact("def f : Nat := 5")
    # ...

# ...or as an object
repl = LeanRepl(repl_path, proj_path)
repl.open()
response = repl.interact("def f : Nat := 5")
# ...
repl.close()
```

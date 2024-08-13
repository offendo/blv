import json
from argparse import ArgumentParser, FileType

from pyleanrepl.repl import LeanRepl

if __name__ == "__main__":
    parser = ArgumentParser("pyleanrepl")
    parser.add_argument(
        "--repl", "-r", type=str, default="repl", help="path to lean repl dir (which has been built with `lake build`)"
    )
    parser.add_argument(
        "--project", "-p", type=str, default=".", help="path to lean repl dir (which has been built with `lake build`)"
    )
    parser.add_argument("lean", type=str, help="input file or Lean code to run through the repl")
    parser.add_argument("--output", "-o", type=FileType("w"), help="output path, default is stdout", default="-")

    args = parser.parse_args()
    with LeanRepl(args.repl, args.project) as repl:
        output = repl.interact(args.lean)
        print(json.dumps(output), flush=True, file=args.output)

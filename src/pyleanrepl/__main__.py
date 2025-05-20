import json
from argparse import ArgumentParser, FileType

import rq

from pyleanrepl.repl import LeanRepl

if __name__ == "__main__":
    parser = ArgumentParser("pyleanrepl")
    subparsers = parser.add_subparsers()
    parser.add_argument("--repl", "-r", type=str, default="repl", help="path to lean repl dir (which has been built with `lake build`)")
    parser.add_argument("--project", "-p", type=str, default=".", help="path to lean project dir (which has been built with `lake build`)")
    parser.add_argument("--backport", "-b", action='store_true', help="whether the repl is backported or not")

    server = subparsers.add_parser('server')
    server.add_argument('--workers', '-n', type=int, default=1, help="number of workers to launch")

    cli = subparsers.add_parser('cli')
    cli.add_argument("lean", type=str, help="input file or Lean code to run through the repl")
    cli.add_argument("--output", "-o", type=FileType("w"), help="output path, default is stdout", default="-")

    args = parser.parse_args()

    if args.server:
        from pyleanrepl.worker import VerifierWorker
        VerifierWorker(['default'], 

    if args.cli:
        with LeanRepl(args.repl, args.project, backport=args.backport) as repl:
            output = repl.interact(args.lean)
            print(json.dumps(output), flush=True, file=args.output)

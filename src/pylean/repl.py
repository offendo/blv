#!/usr/bin/env python3
from io import BytesIO
import json
import os
import subprocess as sp
import time
from pprint import pprint
from pathlib import Path
from typing import Any, Literal

LEAN_REPL_PATH = Path(os.environ.get("LEAN_REPL_PATH", "~/src/pylean/repl/")).expanduser().absolute()

class LeanRepl:
    proc: sp.Popen[str]
    env_id: int

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def open(self):
        self.proc = sp.Popen(
            ["lake", "env", f"{LEAN_REPL_PATH}/.lake/build/bin/repl"],
            cwd=LEAN_REPL_PATH.expanduser().parent,
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            bufsize=1,
            universal_newlines=True,
        )
        return self.proc.pid

    def close(self):
        if self.proc.stdin:
            self.proc.stdin.close()
        return self.proc.wait()

    def interact(self, command: str, environment: int | None = None) -> dict:
        cmd: dict[str, Any] = {"allTactics": True}
        if os.path.exists(command):
            cmd["path"] = command
        else:
            cmd["cmd"] = command

        if environment is not None:
            cmd["env"] = environment

        # Send the message
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(cmd) + "\n\n")
        stdout = self._read_stream("stdout")

        # Wait for the response
        out = json.loads(stdout) if stdout else {}
        self.env_id = out.get("env", None)
        return out

    def _read_stream(self, stream: Literal["stdout", "stderr"]) -> str:
        stdio = self.proc.stdout if stream == "stdout" else self.proc.stderr
        assert stdio is not None

        newlines = ["\n", "\n\r", "\r"]
        out = []
        last = stdio.read(1)
        while True:
            out.append(last)
            if all([x in newlines for x in out[-2:]]) and len(out) >= 1:
                break
            last = stdio.read(1)
        return "".join(out).strip()


if __name__ == '__main__':
    with LeanRepl() as repl:
        output = repl.interact(str(Path("../../Pylean/test.lean").expanduser()))
        pprint(output)

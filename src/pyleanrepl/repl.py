#!/usr/bin/env python3
import json
import os
import subprocess as sp
import tempfile
from argparse import ArgumentParser, FileType
from pathlib import Path
from typing import Any, Literal


class TimeoutException(Exception): ...


def timeout_handler(signum, frame):
    raise TimeoutException("ran out of time")


class LeanRepl:
    proc: sp.Popen[str]
    env_id: int
    repl_path: str | Path
    project_path: str | Path

    def __init__(self, repl_path: str | Path, project_path: str | Path, backport: bool = False):
        self.repl_path = repl_path
        self.project_path = project_path
        self.backport = backport
        signal.signal(signal.SIGALRM, timeout_handler)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def open(self):
        if self.backport:
            path = f"{self.repl_path}/build/bin/repl"
        else:
            path = f"{self.repl_path}/.lake/build/bin/repl"
        self.stdin = tempfile.TemporaryFile("w+b", buffering=1)
        self.stdout = tempfile.TemporaryFile("r+b", buffering=1)
        self.stderr = tempfile.TemporaryFile("r+b", buffering=1)
        self.proc = sp.Popen(
            ["lake", "env", path],
            cwd=self.project_path,
            stdin=self.stdin,
            stdout=self.stdout,
            stderr=self.stderr,
            bufsize=1,
            universal_newlines=True,
            text=True,
        )
        return self.proc.pid

    def close(self):
        if self.proc.stdin:
            self.proc.stdin.close()
        return self.proc.wait()

    def interact(self, command: str, environment: int | None = None, timeout: int = 0) -> dict:
        cmd: dict[str, Any] = {"allTactics": True}
        if os.path.exists(command):
            cmd["path"] = command
        else:
            cmd["cmd"] = command

        if environment is not None:
            cmd["env"] = environment

        # Send the message
        assert self.proc.stdin is not None
        self.stdin.write((json.dumps(cmd) + "\n\n").encode())
        stdout = self._read_stream("stdout")

        # Wait for the response
        out = json.loads(stdout) if stdout else {}
        self.env_id = out.get("env", None)
        return out

    def _read_stream(self, stream: Literal["stdout", "stderr"]) -> str | None:
        stdio = self.proc.stdout if stream == "stdout" else self.proc.stderr
        assert stdio is not None

        newlines = ["\n", "\n\r", "\r", ""]
        out = []
        while True:
            line = stdio.readline()
            if not line.strip() and len(out) >= 1:
                break
            out.extend(line)
        return "".join(out).strip()

    def _read_stream_2(self, stream: Literal["stdout", "stderr"]) -> str:
        stdio = self.proc.stdout if stream == "stdout" else self.proc.stderr
        assert stdio is not None

        newlines = ["\n", "\n\r", "\r", ""]
        out = []
        last = stdio.read(1)
        while True:
            out.append(last)
            if all([x in newlines for x in out[-2:]]) and len(out) >= 1:
                break
            last = stdio.read(1)
        return "".join(out).strip()

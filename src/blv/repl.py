#!/usr/bin/env python3
import json
import os
import subprocess as sp
import tempfile
import socket
import logging
import time
import uuid
from argparse import ArgumentParser, FileType
from pathlib import Path
from typing import Any, Literal

from src.blv.config import Config


def get_random_port():
    sock = socket.socket()
    sock.bind(('', 0))
    return sock.getsockname()[1]

class LeanRepl:
    proc: sp.Popen[str] | None
    env_id: int
    repl_path: str | Path
    project_path: str | Path
    sock: socket.socket

    def __init__(self, repl_path: str | Path, project_path: str | Path, backport: bool = False):
        self.repl_path = repl_path
        self.project_path = project_path
        self.backport = backport

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def reset(self, imports: list[str] | None = None):
        self.close()
        pid = self.open()
        self.interact("\n".join(imports or Config.imports))
        return pid

    def open(self):
        if self.backport:
            path = f"{self.repl_path}/build/bin/repl"
        else:
            path = f"{self.repl_path}/.lake/build/bin/repl"
        port = get_random_port()
        self.proc = sp.Popen(
            ["lake", "env", path, "--tcp", str(port)],
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            cwd=self.project_path,
            universal_newlines=True,
        )
        time.sleep(0.5)
        start = time.time()
        self.sock = None
        while self.sock is None and time.time() - start < 10:
            try:
                self.sock = socket.create_connection(("localhost", port))
            except Exception as e:
                time.sleep(1)
                continue
        if self.sock is None:
            raise Exception("Couldn't connect to the REPL; probably busted")

        logging.info(f"REPL open on port {port}")
        return self.proc.pid

    def close(self):
        if self.proc:
            port = self.sock.getsockname()[1]
            self.sock.close()
            self.proc.terminate()
            logging.info(f"closed port {port}")
        self.proc = None

    def interact(self, command: str, environment: int | None = None, timeout: int | None = None) -> dict:
        cmd: dict[str, Any] = {"allTactics": True}
        if timeout:
            cmd['timeout'] = timeout
        if os.path.exists(command):
            cmd["path"] = command
        else:
            cmd["cmd"] = command

        if environment is not None:
            cmd["env"] = environment

        start = time.time()
        # Send the package, then wait for the initial response.
        bytes_sent = self.sock.send(json.dumps(cmd).encode())

        # Read in the packet; initially we start with 16kb
        bufsize = 2 ** 16 # 64kb
        response = self.sock.recv(bufsize)
        try:
            out = json.loads(response)
        except Exception as e:
            while True:
                time.sleep(0.1)
                try:
                    response += self.sock.recv(bufsize, socket.MSG_DONTWAIT)
                except BlockingIOError as e:
                    break
        end = time.time()

        # Read in the info & return
        try:
            out = json.loads(response)
            out['time'] = end - start
            self.env_id = out.get("env", None)
            return out
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode response from REPL ({len(response)} bytes).")
            out = {'time': end-start, 'error': str(e)}
            return out


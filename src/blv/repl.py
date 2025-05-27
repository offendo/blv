#!/usr/bin/env python3
from functools import lru_cache
import json
import logging
import socket
import subprocess as sp
import time
from pathlib import Path
from typing import Any
from .utils import make_header_key, parse_header, Timer


def get_random_port():
    sock = socket.socket()
    sock.bind(("", 0))
    return sock.getsockname()[1]


class LeanRepl:
    proc: sp.Popen[str] | None
    env_id: int
    repl_path: str | Path
    project_path: str | Path
    sock: socket.socket

    def __init__(
        self, repl_path: str | Path, project_path: str | Path, backport: bool = False, host: str = "localhost"
    ):
        self.repl_path = repl_path
        self.project_path = project_path
        self.backport = backport
        self.port = get_random_port()
        self.host = host
        self.init_repl()

    def init_repl(self):
        path = str(Path(f"{self.repl_path}/.lake/build/bin/repl").absolute())
        self.proc = sp.Popen(
            ["lake", "env", path, "--tcp", str(self.port)],
            stdin=sp.PIPE,
            stdout=sp.PIPE,
            stderr=sp.PIPE,
            cwd=self.project_path,
            universal_newlines=True,
        )

    @lru_cache(maxsize=5)
    def open(self, imports: tuple):
        # open the socket
        sock = None
        with Timer() as timer:
            while sock is None and timer.elapsed < 10:
                try:
                    sock = socket.create_connection((self.host, self.port))
                except Exception as e:
                    time.sleep(0.5)
            if sock is None:
                raise Exception("Couldn't connect to the REPL; probably busted")

        # initialize the headers
        cmd = {"allTactics": True, "cmd": "\n".join(imports)}
        response = self.interact(sock, cmd)
        if response.get('error'):
            raise Exception(response.get('error'))
        return sock

    def interact(self, sock: socket.socket, cmd: dict[str, Any]):
        with Timer() as timer:
            bytes_sent = sock.send(json.dumps(cmd).encode())

            # Read in the packet; initially we start with 16kb
            bufsize = 2**16  # 64kb
            response = sock.recv(bufsize)
            try:
                out = json.loads(response)
            except Exception as e:
                while True:
                    time.sleep(0.1)
                    try:
                        response += sock.recv(bufsize, socket.MSG_DONTWAIT)
                    except BlockingIOError as e:
                        break
            time_taken = timer.elapsed

        # Read in the info & return
        try:
            out = json.loads(response)
            out["time"] = time_taken
            return out
        except json.JSONDecodeError as e:
            logging.error(f"Failed to decode response from REPL ({len(response)} bytes).")
            out = {"time": time_taken, "error": str(e)}
            return out


    def query(
        self, command: str, environment: int | None = None, timeout: int | None = None
    ) -> dict:
        header, theorem = parse_header(command)
        key = make_header_key(header)
        cmd: dict[str, Any] = {"allTactics": True, "cmd": theorem}
        if timeout:
            cmd["timeout"] = timeout

        if environment is not None:
            cmd["env"] = environment

        sock = self.open(key)
        return self.interact(sock, cmd)

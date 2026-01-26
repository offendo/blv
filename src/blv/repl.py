#!/usr/bin/env python3
import os
import json
import logging
import socket
import signal
import subprocess as sp
import time
from pathlib import Path
from typing import Any

from .utils import Timer, make_header_key, lru_cache

logging.basicConfig(level=logging.DEBUG)

def get_random_port():
    sock = socket.socket()
    sock.bind(("", 0))
    return sock.getsockname()[1]


class LeanRepl:
    def __init__(
        self,
        repl_path: str | Path,
        project_path: str | Path,
        backport: bool = False,
        host: str = "localhost",
    ):
        self.repl_path = repl_path
        self.project_path = project_path
        self.backport = backport
        self.host = host
        self.logger = logging.getLogger(f"repl://{self.host}")

    def shutdown(self):
        self.open_repl.cache_clear()
        self.logger.info(f"Shutdown all REPLs")

    @staticmethod
    def close_repl(proc, sock):
        sock.send("")
        sock.close()
        return os.killpg(os.getpgid(proc.pid), signal.SIGTERM)

    def open_socket(self, port: int):
        sock = None
        with Timer() as timer:
            while sock is None and timer.elapsed < 30:
                try:
                    sock = socket.create_connection((self.host, port))
                except Exception:
                    time.sleep(0.5)
            if sock is None:
                raise Exception("Couldn't connect to the REPL; probably busted")
        return sock

    @lru_cache(
        maxsize=3,
        key_fn=lambda self, imports: make_header_key(imports),
        del_fn=lambda key, proc: self.close_repl(proc[0], proc[1]),
    )
    def open_repl(self, imports: tuple[str, ...]):
        path = str(Path(f"{self.repl_path}/.lake/build/bin/repl").absolute())
        port = get_random_port()
        fout = open(f'/tmp/repl-{port}.log', 'w')
        ferr = open(f'/tmp/repl-{port}.err', 'w')
        proc = sp.Popen(
            ["lake", "-R", "env", path, "--tcp", str(port)],
            stdin=sp.PIPE,
            stdout=fout,
            stderr=ferr,
            cwd=self.project_path,
            universal_newlines=True,
            # preexec_fn=os.setsid,
        )

        # Open connection to repl
        sock = self.open_socket(port)
        self.logger.debug(f"Started REPL as subprocess: pid={proc.pid}")

        # Initialize the headers
        # keepEnv is true because we want to return the header.
        cmd = {"allTactics": True, "cmd": "\n".join(imports), "keepEnv": True}

        # Talk to the repl to init the headers
        response = self.interact(sock, cmd)

        # Make sure things went ok
        if response.get("error"):
            raise Exception(response.get("error"))

        self.logger.debug(
            f"Opened new REPL at port {sock.getsockname()[1]} with imports: {imports} (response: {response})"
        )

        # Return both repl process and socket
        return proc, sock

    def interact(self, sock: socket.socket, cmd: dict[str, Any]):
        with Timer() as timer:
            sock.send(json.dumps(cmd, ensure_ascii=False).encode())

            # Read in the packet; initially we start with 16kb
            bufsize = 2**16  # 64kb
            response = sock.recv(bufsize)
            try:
                out = json.loads(response)
            except Exception:
                while True:
                    time.sleep(0.1)
                    try:
                        response += sock.recv(bufsize, socket.MSG_DONTWAIT)
                    except BlockingIOError:
                        break
            time_taken = timer.elapsed

        # Read in the info & return
        try:
            out = json.loads(response)
            out["time"] = time_taken
            return out
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to decode response from REPL ({len(response)} bytes).")
            out = {"time": time_taken, "error": str(e)}
            return out

    def query(
        self,
        theorem: str,
        header: tuple[str, ...] | None = None,
        environment: int | None = None,
        timeout: int | None = None,
        keep_env: bool = False,
    ) -> dict:
        # keepEnv should be false by default because we don't want to store the env except the first time
        cmd: dict[str, Any] = {"allTactics": True, "cmd": theorem, "keepEnv": keep_env}
        if timeout:
            cmd["timeout"] = timeout

        key = make_header_key(header)
        proc, sock = self.open_repl(key)
        cmd["env"] = environment if environment is not None else 0

        if theorem:
            return self.interact(sock, cmd)
        else:
            return {}

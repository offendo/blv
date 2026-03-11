#!/usr/bin/env python3
import json
import logging
import os
import signal
import socket
import subprocess as sp
import time
from pathlib import Path
from collections import OrderedDict
from typing import Any

from .utils import Timer, make_header_key


class BrokenReplError(Exception): ...


class BadReplResponseError(Exception): ...


def get_random_port():
    sock = socket.socket()
    sock.bind(("", 0))
    return sock.getsockname()[1]


def close_repl(*, proc, sock):
    sock.close()
    return os.killpg(os.getpgid(proc.pid), signal.SIGTERM)


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
        self.logger.setLevel(logging.INFO)

        self.repl_cache = OrderedDict()
        self.maxsize = 3

    def connect_to_repl(self, port: int):
        sock = None
        with Timer() as timer:
            while sock is None and timer.elapsed < 5:
                try:
                    sock = socket.create_connection((self.host, port))
                except Exception:
                    time.sleep(0.5)
            if sock is None:
                self.logger.error(f"Unable to connect to REPL at port {port}")
                raise BrokenReplError(f"Unable to connect to REPL at port {port}")
        return sock

    def interact(self, sock: socket.socket, cmd: dict[str, Any]):
        try:
            with Timer() as timer:
                command_string = json.dumps(cmd, ensure_ascii=True).encode()
                sock.send(command_string)
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
        except Exception as e:
            self.logger.error("Something happened while trying to send message back/forth to REPL: %s\n Caused by: %s", e, json.dumps(cmd, indent=2))
            raise BrokenReplError(f"Something happened while trying to send message back/forth to REPL: {e}")

        # Read in the info & return
        try:
            out = json.loads(response)
            out["time"] = time_taken
            return out
        except Exception as e:
            self.logger.error(f"Bad response from REPL: {response}")
            raise BadReplResponseError(f"Bad response from REPL: {response}")

    def make_or_get_repl(self, *, imports: list[str]) -> tuple[sp.Popen, socket.socket]:
        # Check the cache first
        key = make_header_key(imports)
        if key in self.repl_cache:
            self.repl_cache.move_to_end(key)
            return self.repl_cache[key]

        # Cache miss: have to spawn a new repl
        path = str(Path(f"{self.repl_path}/.lake/build/bin/repl").absolute())
        port = get_random_port()

        # FIXME(nilay) include -R maybe if things break; I forget what this does
        proc = sp.Popen(
            ["lake", "env", path, "--tcp", str(port)],
            stdout=sp.DEVNULL,
            stderr=sp.DEVNULL,
            cwd=self.project_path,
            universal_newlines=True,
            # preexec_fn=os.setsid,
        )

        # Open connection to repl
        sock = self.connect_to_repl(port)
        self.logger.info(f"Started REPL as subprocess: pid={proc.pid}")

        # Initialize the headers
        # keepEnv is true because we want to return the header.
        cmd = {"allTactics": True, "cmd": "\n".join(imports), "keepEnv": True}

        # Talk to the repl to init the headers
        try:
            response = self.interact(sock, cmd)
        except Exception as e:
            close_repl(proc=proc, sock=sock)
            raise e

        # Make sure things went ok
        if response.get("error"):
            close_repl(proc=proc, sock=sock)
            raise BrokenReplError(response.get("error"))

        self.logger.info(
            f"Opened new REPL at port {sock.getsockname()[1]} with imports: {imports} (response: {response})"
        )

        # Update the cache
        # Evict if needed:
        if len(self.repl_cache) >= self.maxsize:
            self.evict_repl()
        self.repl_cache[key] = (proc, sock)

        # Return both repl process and socket
        return proc, sock

    def evict_repl(self, imports: list[str] | None = None):
        if imports is not None:
            evicted_key = make_header_key(imports)
            evicted_proc, evicted_sock = self.repl_cache[evicted_key]
        else:
            evicted_key, (evicted_proc, evicted_sock) = self.repl_cache.popitem(last=False)
        del self.repl_cache[evicted_key]
        close_repl(proc=evicted_proc, sock=evicted_sock)
        self.logger.info("Evicted repl with imports %s", str(evicted_key))

    def query(
        self,
        theorem: str,
        imports: list[str],
        environment: int | None = None,
        timeout: int | None = None,
        keep_env: bool = False,
    ) -> dict:

        if len(theorem) == 0:
            return {"error": "Empty theorem supplied."}

        # keepEnv should be false by default because we don't want to store the env except the first time
        cmd: dict[str, Any] = {"allTactics": True, "cmd": theorem, "keepEnv": keep_env}
        if timeout:
            cmd["timeout"] = timeout

        cmd["env"] = environment if environment is not None else 0
        try:
            proc, sock = self.make_or_get_repl(imports=imports)
        except Exception as e:
            return {"error": e}

        # Try, reboot repl if needed
        for _ in range(3):
            try:
                return self.interact(sock, cmd)
            except Exception as e:
                self.evict_repl(imports=imports)
                proc, sock = self.make_or_get_repl(imports=imports)

        return {"error": "repl broken after 3 attempts; giving up"}

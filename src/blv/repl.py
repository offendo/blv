#!/usr/bin/env python3
import json
import logging
import os
import signal
import socket
import subprocess as sp
import time
from pathlib import Path
from typing import Any, Callable
from collections import OrderedDict

from .utils import Timer, make_header_key


class BrokenReplError(Exception):
    ...

def get_random_port():
    sock = socket.socket()
    sock.bind(("", 0))
    return sock.getsockname()[1]

def close_repl(proc, sock):
    self.logger.info(f"Closing repl: pid={proc.pid}, sock={sock}")
    sock.close()
    return os.killpg(os.getpgid(proc.pid), signal.SIGTERM)

def lru_cache(maxsize: int | None = None):
    class ReplCache:
        def __init__(self):
            self.maxsize = maxsize
            self.cache = OrderedDict()
            self.del_fn = close_repl

        @staticmethod
        def key_fn(*, imports, **kwargs):
            return make_header_key(imports)

        def evict(self, key):
            # Construct the key as specified
            proc, sock = self.cache[key]
            del self.cache[key]
            self.del_fn(proc, sock)

        def __call__(self, fn):
            def _wrapped(*args, imports, **kwargs):
                # Construct the key as specified
                key = self.key_fn(imports=imports)

                # Cache hit
                if key in self.cache:
                    self.cache.move_to_end(key)
                    return self.cache[key]

                # Cache miss
                val = fn(*args, imports=imports, **kwargs)

                # Evict if needed:
                if len(self.cache) >= self.maxsize:
                    evicted_key, (proc, sock) = self.cache.popitem(last=False)
                    self.del_fn(proc, sock)

                self.cache[key] = val
                return val

            # Expose evict/cache
            _wrapped.evict = self.evict
            _wrapped.cache = self.cache
            return _wrapped
    return ReplCache()


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

    def open_socket(self, port: int):
        sock = None
        with Timer() as timer:
            while sock is None and timer.elapsed < 5:
                try:
                    sock = socket.create_connection((self.host, port))
                except Exception:
                    time.sleep(0.5)
            if sock is None:
                raise Exception("Couldn't connect to the REPL; probably busted")
        return sock

    def interact(self, sock: socket.socket, cmd: dict[str, Any]):
        with Timer() as timer:
            # This sometimes fails if the REPL dies. If we catch it here, we can retry
            try:
                sock.send(json.dumps(cmd, ensure_ascii=False).encode())
                bufsize = 2**16  # 64kb
                response = sock.recv(bufsize)
            except Exception as e:
                self.logger.error(f"Repl at port {sock.getsockname()[1]} broken.", exc_info=True)
                raise BrokenReplError(f"Repl at port {sock.getsockname()[1]} broken.")

            # This loop will ensure we get the ENTIRE response. Unless the
            # server sends infinite data back, this loop will surely terminate.
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


    @lru_cache(maxsize=3)
    def get_repl(self, *, imports: tuple[str, ...]):
        path = str(Path(f"{self.repl_path}/.lake/build/bin/repl").absolute())
        port = get_random_port()
        proc = sp.Popen(
            ["lake", "-R", "env", path, "--tcp", str(port)],
            cwd=self.project_path,
            universal_newlines=True,
            # preexec_fn=os.setsid,
        )

        # Open connection to repl
        sock = self.open_socket(port)
        self.logger.info(f"Started REPL as subprocess: pid={proc.pid}")

        # Initialize the headers
        # keepEnv is true because we want to return the header.
        cmd = {"allTactics": True, "cmd": "\n".join(imports), "keepEnv": True}

        # Talk to the repl to init the headers
        response = self.interact(sock, cmd)

        # Make sure things went ok
        if response.get("error"):
            raise BrokenReplError(response.get("error"))

        self.logger.info(
            f"Opened new REPL at port {sock.getsockname()[1]} with imports: {imports} (response: {response})"
        )

        # Return both repl process and socket
        return proc, sock

    def query(
        self,
        theorem: str,
        header: tuple[str, ...] | None = None,
        environment: int | None = None,
        timeout: int | None = None,
        keep_env: bool = False,
    ) -> dict:

        if len(theorem) == 0:
            raise ValueError("Empty theorem supplied.")

        # keepEnv should be false by default because we don't want to store the env except the first time
        cmd: dict[str, Any] = {"allTactics": True, "cmd": theorem, "keepEnv": keep_env}
        if timeout:
            cmd["timeout"] = timeout

        key = make_header_key(header)
        cmd["env"] = environment if environment is not None else 0
        proc, sock = self.get_repl(imports=key)

        # Try, reboot repl if needed
        for _ in range(3):
            try:
                return self.interact(sock, cmd)
            except BrokenReplError as e:
                self.get_repl.evict(key)
                proc, sock = self.get_repl(imports=key)

        return {"error": "repl broken after 3 attempts; giving up"}

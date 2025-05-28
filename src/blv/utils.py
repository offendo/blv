import re
import time
from typing import Callable


def parse_header(theorem: str):
    pattern = r"^import .*$"
    header = []
    rest = []
    for line in (l for l in theorem.splitlines() if len(l.strip())):
        if re.match(pattern, line):
            header.append(line.strip())
        else:
            rest.append(line)
    return header, "\n".join(rest).strip()


def make_header_key(header: list[str] | None) -> tuple:
    return tuple(sorted(header)) if header else ()


def remove_comments(formal_statement: str) -> str:
    block_pattern = r"/-.*? -/\n"
    inline_pattern = r"--.*?\n"
    return re.sub(inline_pattern, "", re.sub(block_pattern, "", formal_statement, flags=re.DOTALL), flags=re.DOTALL)


def check_response_for_error(resp):
    """Parses Lean REPL response to check for errors.

    Mostly just a helper function.

    Arguments
    ---------
    resp : dict
        Response from Lean REPL (i.e., output of `verify`)

    Returns
    -------
    tuple[bool, list[str]]
        `(True, [])` if no complaints, otherwise `(False, <errors>)`
    """
    # If the job return value is nothing, something failed in the REPL
    if resp is None or len(resp) == 0:
        return {
            "verified": False,
            "errors": ["Job failed; please report an issue on GitHub because this should never happen."],
        }

    # If the REPL sends back a 'message' with 'timeout', then we timed out (failure)
    if "timeout" in resp.get("message", ""):
        return {"verified": False, "errors": ["timeout"]}

    # Otherwise it might have an 'error' keyword, in which case we fail with that error
    if "error" in resp:
        return {"verified": False, "errors": [resp["error"]]}

    # Finally, we need to make sure there aren't any syntax/semantic errors from the compiler
    if "messages" in resp:
        errors = []
        for msg in resp["messages"]:
            if msg["severity"] == "error":
                errors.append(msg)
        return {"verified": len(errors) == 0, "errors": errors}

    # If all that is good, then we return with no errors.
    return {"verified": True, "errors": []}


class Timer:
    def __init__(self, msg_template: str | None = None, logger_func: Callable | None = None) -> None:
        self.msg_template = msg_template or "{}"
        self.logger_func = logger_func or (lambda *x, **y: None)

    def __enter__(self):
        self.start = time.time()
        return self

    @property
    def elapsed(self):
        return time.time() - self.start

    def __exit__(self, *args, **kwargs):
        self.end = time.time()
        self.logger_func(self.msg_template.format(self.end - self.start))

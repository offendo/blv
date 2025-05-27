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

def make_header_key(header: list[str]):
    return tuple(sorted(header))

def remove_comments(formal_statement: str) -> str:
    block_pattern = r"/-.*? -/\n"
    no_blocks = re.sub(block_pattern, "", formal_statement, flags=re.DOTALL)
    inline_pattern = r"--.*?\n"
    no_blocks_or_inline = re.sub(inline_pattern, "", no_blocks, flags=re.DOTALL)
    return no_blocks_or_inline

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

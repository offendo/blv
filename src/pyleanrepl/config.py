#!/usr/bin/env python3
import os


class Config:
    repl_path: str = os.path.expanduser("~/src/repl")
    project_path: str = os.path.expanduser("~/src/repl")
    backport: bool = False
    imports: list[str] = []

#!/usr/bin/env python3
import os


class Config:
    repl_path: str = os.path.expanduser(os.environ['REPL_PATH'])
    project_path: str = os.path.expanduser(os.environ['PROJECT_PATH'])
    backport: bool = False
    imports: list[str] = ['import Mathlib', 'import Aesop']

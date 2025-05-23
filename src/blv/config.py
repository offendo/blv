#!/usr/bin/env python3
import os


class Config:
    repl_path: str = os.path.expanduser("./repl")
    project_path: str = os.path.expanduser("./repl")
    backport: bool = False
    imports: list[str] = ['import Mathlib', 'import Aesop']

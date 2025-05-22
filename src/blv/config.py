#!/usr/bin/env python3
import os


class Config:
    repl_path: str = "/repl"
    project_path: str = "/project"
    backport: bool = False
    imports: list[str] = ['import Mathlib', 'import Aesop']

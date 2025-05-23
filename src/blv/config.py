#!/usr/bin/env python3
import os


class Config:
    repl_path: str = os.path.expanduser(os.environ.get("BLV_REPL_PATH", "/repl"))
    project_path: str = os.path.expanduser(os.environ.get("BLV_PROJECT_PATH", "/project"))
    backport: bool = False
    imports: list[str] = ["import Mathlib", "import Aesop"]

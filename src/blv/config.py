#!/usr/bin/env python3
import os


class Config:
    repl_path: str = os.path.expanduser(os.environ.get("BLV_REPL_PATH", "/repl"))
    project_path: str = os.path.expanduser(os.environ.get("BLV_PROJECT_PATH", "/repl"))
    backport: bool = False
    imports: list[str] = os.environ.get("BLV_IMPORTS", "import Mathlib,import Aesop").split(",")

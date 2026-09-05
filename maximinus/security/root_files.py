"""Shared helpers for reading/writing root-owned config files via sudo."""

import os
import subprocess
import tempfile

from .sudo_session import run_privileged


def read_root_file(path: str) -> str:
    result = subprocess.run(
        ["sudo", "cat", path], capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode == 0 else ""


def write_root_file(path: str, content: str, mode: str = "0644") -> None:
    with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        run_privileged(["install", "-m", mode, "-o", "root", "-g", "root", tmp_path, path])
    finally:
        os.unlink(tmp_path)

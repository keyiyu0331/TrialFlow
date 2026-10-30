"""Shared helpers for the Claude Code hooks: read the event, find the repo and its tools."""

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
FRONTEND = ROOT / "frontend"


def read_event() -> dict:
    try:
        # Claude Code sends UTF-8; don't rely on the platform's default stdin encoding.
        return json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {}


def venv_tool(name: str) -> str | None:
    """A tool from the repo's .venv (bin/ on macOS/Linux, Scripts/ on Windows), else PATH."""
    for sub in ("bin", "Scripts"):
        found = shutil.which(name, path=str(ROOT / ".venv" / sub))
        if found:
            return found
    return shutil.which(name)


def biome() -> str | None:
    return shutil.which("biome", path=str(FRONTEND / "node_modules" / ".bin"))


def rel(path: str) -> str:
    """Repo-relative POSIX path, or the input unchanged if it lies outside the repo."""
    try:
        return Path(path).resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()

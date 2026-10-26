"""PostToolUse (Edit/Write): format the file Claude just changed. Never blocks."""

import subprocess
import sys

from _common import FRONTEND, ROOT, biome, read_event, rel, venv_tool

BIOME_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".json")


def main() -> None:
    path = (read_event().get("tool_input") or {}).get("file_path")
    if not path:
        return
    relpath = rel(path)
    if relpath.startswith("data/"):
        return
    if relpath.endswith(".py") and (ruff := venv_tool("ruff")):
        subprocess.run([ruff, "check", "--fix", "--quiet", "--exit-zero", path], cwd=ROOT, check=False)
        subprocess.run([ruff, "format", "--quiet", path], cwd=ROOT, check=False)
    elif relpath.startswith("frontend/") and relpath.endswith(BIOME_SUFFIXES) and (bin_ := biome()):
        subprocess.run(
            [bin_, "check", "--write", "--no-errors-on-unmatched", path],
            cwd=FRONTEND,
            check=False,
            capture_output=True,
        )


if __name__ == "__main__":
    main()
    sys.exit(0)

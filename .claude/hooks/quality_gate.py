"""Stop: before Claude finishes, run the checks for whatever changed.

Fails once with exit 2 so Claude fixes the problems. If the checks still fail on the
retry (stop_hook_active), Claude may stop and the user sees a warning, so a problem
Claude can't fix never loops forever.
"""

import json
import shutil
import subprocess
import sys

from _common import FRONTEND, ROOT, biome, read_event, venv_tool

MAX_LINES = 40


def changed_files() -> list[str]:
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    return [line[3:].strip().strip('"') for line in out.splitlines() if line.strip()]


def run(label: str, cmd: list[str], cwd) -> str | None:
    """Run one check; return a trimmed failure report, or None if it passed."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode == 0:
        return None
    lines = (result.stdout + result.stderr).strip().splitlines()
    return f"## {label} failed\n" + "\n".join(lines[-MAX_LINES:])


def checks(files: list[str]) -> tuple[list, list[str]]:
    plan, missing = [], []
    if any(f.endswith(".py") for f in files):
        ruff, pytest = venv_tool("ruff"), venv_tool("pytest")
        if ruff:
            plan.append(("ruff check", [ruff, "check", "."], ROOT))
            plan.append(("ruff format --check", [ruff, "format", "--check", "."], ROOT))
        else:
            missing.append("ruff (pip install -r backend/requirements.txt)")
        if pytest:
            plan.append(("pytest", [pytest, "-q", "-x"], ROOT / "backend"))
        else:
            missing.append("pytest (pip install -r backend/requirements.txt)")
    if any(f.startswith("frontend/") and not f.startswith("frontend/.next") for f in files):
        bin_, npm = biome(), shutil.which("npm")
        if bin_ and npm:
            plan.append(("biome check", [bin_, "check", "."], FRONTEND))
            plan.append(("typecheck", [npm, "run", "--silent", "typecheck"], FRONTEND))
        else:
            missing.append("frontend tools (cd frontend && npm install)")
    return plan, missing


def main() -> int:
    event = read_event()
    plan, missing = checks(changed_files())
    failures = [report for label, cmd, cwd in plan if (report := run(label, cmd, cwd))]
    report = "\n\n".join(failures)
    if failures and not event.get("stop_hook_active"):
        print("Checks failed; fix these before finishing:\n\n" + report, file=sys.stderr)
        return 2
    notes = []
    if missing:
        notes.append("Quality gate skipped: install " + ", ".join(missing))
    if failures:
        notes.append("Quality gate still failing after a retry:\n" + report)
    if notes:
        print(json.dumps({"systemMessage": "\n\n".join(notes)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

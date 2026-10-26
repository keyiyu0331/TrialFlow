"""PreToolUse: block actions CLAUDE.md forbids. Exit 2 sends the reason back to Claude."""

import re
import sys
from pathlib import PurePosixPath

from _common import read_event, rel

BASH_RULES = [
    (r"--no-verify\b|\bgit\s+commit\b[^|;&]*\s-n\b", "Don't skip git hooks (--no-verify); fix what they report."),
    (
        r"\bgit\s+push\b[^|;&]*(\s-f\b|--force(?!-with-lease))",
        "Don't force-push; ask the user first (--force-with-lease is allowed).",
    ),
    (r"run_extraction\.ps1", "scripts/run_extraction.ps1 calls the missing extract_trials.py; don't run it."),
]


def check_file(path: str) -> str | None:
    relpath = rel(path)
    if relpath.startswith("data/"):
        return f"{relpath} is registry input: never hand-edit it; regenerate it from the ClinicalTrials.gov API."
    name = PurePosixPath(relpath).name
    if name.startswith(".env") and name != ".env.example":
        return f"{relpath} holds secrets: don't read or write it; config comes from environment variables."
    return None


def main() -> int:
    event = read_event()
    tool_input = event.get("tool_input") or {}
    if event.get("tool_name") == "Bash":
        # Match flags, not text inside quotes (e.g. a commit message that mentions --no-verify).
        command = re.sub(r"\"[^\"]*\"|'[^']*'", '""', tool_input.get("command", ""))
        reason = next((msg for pattern, msg in BASH_RULES if re.search(pattern, command)), None)
    else:
        path = tool_input.get("file_path") or tool_input.get("notebook_path")
        reason = check_file(path) if path else None
    if reason:
        print(f"Blocked by .claude/hooks/guard.py: {reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

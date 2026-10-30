# Claude Code hooks

Wired in `.claude/settings.json`; they run in every Claude Code session in this repo. They need `python3` on PATH, plus `pip install -r backend/requirements.txt` and `cd frontend && npm install` for the tools they call.

- `guard.py` (PreToolUse): blocks edits to `data/` and `.env*`, `--no-verify` / `commit -n`, force-push (not `--force-with-lease`), and `run_extraction.ps1`.
- `format_file.py` (PostToolUse): formats the edited file with ruff (`.py`) or Biome (`frontend/`). Never blocks.
- `quality_gate.py` (Stop): for changed Python files it runs `ruff check`, `ruff format --check`, and `pytest`; for changed frontend files, `biome check` and `npm run typecheck`. It blocks once with the failures; if they persist on the retry, it lets Claude stop and warns the user.

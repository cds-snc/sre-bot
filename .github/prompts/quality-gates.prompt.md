---
name: quality-gates
description: Run Python quality gates with root-cause triage and minimal fixes.
agent: implementation
model: Auto (copilot)
---

Run and report quality gates per the `python-quality-gates` skill:

1. `cd app && uv run mypy . --exclude '(?:^|/)\\.venv(?:/|$)'`
2. `cd app && uv run ruff check .`
3. `cd app && uv run pytest tests --ignore=tests/smoke`

Report using the skill's format (gate status, root causes, fixes applied, verification reruns, residual risk).

If failures are unrelated pre-existing issues, identify them explicitly and avoid broad unrelated changes.

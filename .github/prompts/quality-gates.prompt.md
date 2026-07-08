---
name: quality-gates
description: Run Python quality gates with root-cause triage and minimal fixes.
agent: implementation
model: Auto (copilot)
---

Run and report quality gates per the `python-quality-gates` skill:

1. `mypy`
2. `flake8`
3. `black --check .`
4. `pytest app/tests --ignore=app/tests/smoke`

Report using the skill's format (gate status, root causes, fixes applied, verification reruns, residual risk).

If failures are unrelated pre-existing issues, identify them explicitly and avoid broad unrelated changes.

---
name: quality-gates
description: Run Python quality gates with root-cause triage and minimal fixes.
agent: implementation
model: Auto (copilot)
---

Run quality gates per the [python-quality-gates skill](../skills/python-quality-gates/SKILL.md).

1. `mypy`
2. `flake8`
3. `black --check .`
4. `pytest app/tests --ignore=app/tests/smoke`

Report: status per command → root-cause grouping → minimal fixes → targeted reruns → full rerun status.

Pre-existing unrelated failures: identify explicitly, skip.

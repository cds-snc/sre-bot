---
name: quality-gates
description: Run Python quality gates with root-cause triage and minimal fixes.
agent: implementation
model: Auto (copilot)
---

Run and report quality gates in this order:

1. mypy
2. flake8
3. black --check .
4. pytest

Report format:
1. Status per command.
2. Root-cause grouping.
3. Minimal fixes applied.
4. Targeted reruns performed.
5. Full rerun final status.

If failures are unrelated pre-existing issues, identify them explicitly and avoid broad unrelated changes.

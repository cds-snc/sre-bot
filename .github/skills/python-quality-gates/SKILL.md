---
name: python-quality-gates
description: Run and triage Python quality gates with minimal, root-cause fixes; use when validating feature work before completion.
---

## Gate Sequence

Run after each feature section:
1. `mypy` — type correctness
2. `flake8` — style, unused imports
3. `black --check` — formatting
4. `pytest app/tests --ignore=app/tests/smoke` — behavior

## Triage

Group failures by root cause. Fix the smallest change resolving the root cause. No unrelated refactoring.

## Common Causes

| Gate | Cause |
|------|-------|
| mypy | Missing Protocol method; wrong return type |
| mypy | Nested BaseSettings in BaseSettings |
| mypy | Pydantic BaseModel in domain module |
| pytest | @lru_cache state leak between tests |
| pytest | Unfrozen dataclass crossing boundary |
| flake8 | Unused import; bare except |

## Stop Conditions

Pre-existing failures: report, skip. No convergence: stop, request direction.

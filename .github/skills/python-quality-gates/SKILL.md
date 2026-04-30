---
name: python-quality-gates
description: Run and triage Python quality gates with minimal, root-cause fixes; use when validating feature work before completion.
---

Use after each 3-5 meaningful edits and before task completion.

## Gate Sequence

1. `mypy`
2. `flake8`
3. `black --check .`
4. `pytest app/tests --ignore=app/tests/smoke`

No smoke tests unless explicitly requested with env vars confirmed.

## Triage

- Group failures by root cause, not file count.
- Fix the smallest change that resolves the root cause.
- Do not refactor unrelated areas.
- Re-run affected checks first, then full sequence before completion.

## Common Root Causes

| Gate | Cause | ADR |
|------|-------|-----|
| mypy | Missing Protocol method / wrong return type | ADR-0065, ADR-0077 |
| mypy | `BaseSettings` nested in `BaseSettings` | ADR-0055 |
| pytest | `@lru_cache` state leak between tests | ADR-0062 |
| pytest | Missing `dependency_overrides` cleanup | ADR-0062 |

## Stop Conditions

- Pre-existing unrelated failures: report clearly, skip.
- No convergence after reasonable retries: stop and request direction.

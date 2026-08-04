---
name: python-quality-gates
description: Run and triage Python quality gates with minimal, root-cause fixes; use when validating feature work before completion.
---

# Python Quality Gates

Use this skill after each 3-5 meaningful edits and before task completion.

## Gate Order

Run checks in this order for fastest signal:

1. `cd app && uv run mypy . --exclude '(?:^|/)\\.venv(?:/|$)'`
2. `cd app && uv run ruff check .`
3. `cd app && uv run pytest tests --ignore=tests/smoke`

By default, do not run `app/tests/smoke/*`. Run smoke tests only when explicitly requested and env vars are confirmed.
Always run from `app/` and keep checks scoped to project code only (exclude virtualenv and non-project paths).

## Triage Rules

1. Group failures by root cause, not by file count.
2. Fix the smallest change that resolves the root cause.
3. Do not refactor unrelated areas while addressing gate failures.
4. Re-run only affected checks first.
5. Re-run the full gate sequence before completion.

## Targeted Re-run Examples

- Type changes only: run `mypy` first, then full sequence.
- Lint-only changes: run `ruff check`, then full sequence.
- Behavioral changes or tests touched: run focused `pytest` target, then full sequence.
- When a targeted run includes smoke tests, skip unless the task explicitly requests smoke execution with env configured.

## Reporting Format

When reporting results, use this structure:

1. Gate status summary (pass/fail by command).
2. Root causes identified.
3. Fixes applied.
4. Verification reruns performed.
5. Residual risk (if any).

## Stop Conditions

- If a gate fails due to unrelated pre-existing issues, report clearly and avoid unrelated broad fixes.
- If repeated attempts do not converge, stop after reasonable retries and request direction.

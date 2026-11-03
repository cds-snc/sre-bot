---
name: python-quality-gates
description: Run and triage Python quality gates with minimal, root-cause fixes; use when validating feature work before completion.
---

# Python Quality Gates

Use this skill before task completion. During implementation run only `ruff check .` and the targeted test files.

## Gate Order

Once every other change is finished, run each full gate once, one after the other, never in parallel with each other or other heavy work:

1. `cd app && uv run ruff check .`
2. `cd app && uv run mypy . --exclude '(?:^|/)\\.venv(?:/|$)'`, then fix what it finds
3. `cd app && uv run pytest tests --ignore=tests/smoke`, on its own

Rerun a full gate only when it raised a real error.

By default, do not run `app/tests/smoke/*`. Run smoke tests only when explicitly requested and env vars are confirmed.
Always run from `app/` and keep checks scoped to project code only (exclude virtualenv and non-project paths).

## Triage Rules

1. Group failures by root cause, not by file count.
2. Fix the smallest change that resolves the root cause.
3. Do not refactor unrelated areas while addressing gate failures.
4. Re-run only affected checks first (ruff, the targeted test files).
5. Re-run a full gate only if its own run raised a real error.

## Targeted Re-run Examples

- Lint-only changes: run `ruff check`, then the full sequence.
- Type changes only: run `ruff check` (it is nearly free) then `mypy`, then the
  full sequence.
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

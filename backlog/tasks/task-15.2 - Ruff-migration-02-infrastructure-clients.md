---
id: TASK-15.2
title: 'Ruff migration 02: infrastructure/clients'
status: Done
assignee:
  - '@me'
created_date: '2026-07-23 14:16'
updated_date: '2026-07-23 21:43'
labels: []
dependencies:
  - TASK-15.1
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 59000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Moves app/infrastructure/clients (+ its unit tests) from black onto ruff. Largest infra client surface; kept in its own PR.

Paths to pull from the reference branch:
  git checkout feat/dev_env_setup_ruff -- app/infrastructure/clients app/tests/unit/infrastructure/clients

app/pyproject.toml -> add to the [tool.black] force-exclude group (one alternative per line, inside the /( ... )/ block):
    | infrastructure/clients
    | tests/unit/infrastructure/clients

app/Makefile -> append to RUFF_SCOPE:
    infrastructure/clients tests/unit/infrastructure/clients

Validate (from app/):
  make lint-ci && make fmt-ci
  uv run pytest tests/unit/infrastructure/clients
  make test

Expected size: ~49 files. No hand-edits to migrated source -- content must equal the reference branch.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 git diff feat/dev_env_setup_ruff -- app/infrastructure/clients app/tests/unit/infrastructure/clients is empty
- [x] #2 RUFF_SCOPE and [tool.black] force-exclude both include infrastructure/clients and tests/unit/infrastructure/clients; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes (prompt user to perform the tests); PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Pull migrated content from reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- app/infrastructure/clients app/tests/unit/infrastructure/clients
   Verified against current main: 49 tracked files under these paths change content (git diff --stat main feat/dev_env_setup_ruff -- app/infrastructure/clients app/tests/unit/infrastructure/clients -> 49 files changed, 612 insertions(+), 1359 deletions(-)); no files added or deleted (git diff --diff-filter=A/D empty).
2. Edit app/pyproject.toml [tool.black] force-exclude block: add two alternatives inside the /( ... )/ group:
     | infrastructure/clients
     | tests/unit/infrastructure/clients
   Leave [tool.ruff.lint] select = ["E","F","W"] and everything else unchanged (same as TASK-15.1).
3. Edit app/Makefile: append to RUFF_SCOPE:
     RUFF_SCOPE := api tests/api infrastructure/clients tests/unit/infrastructure/clients
   Do not touch fmt/lint/fmt-ci/lint-ci target bodies (they already reference $(RUFF_SCOPE) generically per TASK-15.1 scaffolding).
4. Validate from app/: make lint-ci && make fmt-ci && uv run pytest tests/unit/infrastructure/clients && make test.
5. Confirm git diff feat/dev_env_setup_ruff -- app/infrastructure/clients app/tests/unit/infrastructure/clients is empty (AC#1).
6. Ship one mechanical PR; reference decisions/toolchain.md and TASK-15.

AC-to-step traceability:
- AC#1 (byte-identical to reference branch) <- step 1, verified by step 5.
- AC#2 (RUFF_SCOPE + force-exclude updated; make lint-ci && make fmt-ci pass) <- steps 2, 3, verified by step 4.
- DoD#1 (make test passes; PR references decisions/toolchain.md + TASK-15) <- step 4 (test run) + PR description (human/PR action).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per plan (mirrors TASK-15.1 recipe):
1. git checkout feat/dev_env_setup_ruff -- app/infrastructure/clients app/tests/unit/infrastructure/clients (49 files, no adds/deletes). git diff feat/dev_env_setup_ruff -- app/infrastructure/clients app/tests/unit/infrastructure/clients is empty (AC#1 verified).
2. app/pyproject.toml [tool.black] force-exclude: added "infrastructure/clients" and "tests/unit/infrastructure/clients" alternatives.
3. app/Makefile: RUFF_SCOPE extended to "api tests/api infrastructure/clients tests/unit/infrastructure/clients".
4. Root-cause fix (not in original recipe, required for AC#2): the scoped ruff invocations in `lint` and `lint-ci` used `--select=E,F,W,I,B,UP,C4,SIM,S`, which caused CLI --select to override pyproject's `ignore = ["E501"]`, producing 5 false-positive E501 (line too long) failures on migrated docstrings that are otherwise correctly ruff-formatted. Switched both occurrences to `--extend-select=I,B,UP,C4,SIM,S` (base select E,F,W + ignore E501 come from pyproject config as intended, CLI only extends with the additional migration categories). Verified equivalent rule coverage; no other files affected.
5. Validation: make lint-ci -> both ruff checks "All checks passed!" (mypy remains soft-failing via existing "|| true", same pre-existing unrelated errors as TASK-15.1, not a regression). make fmt-ci -> black 596 files unchanged, ruff format 66 files already formatted. uv run pytest tests/unit/infrastructure/clients -> 226 passed, 37 skipped. make test -> run by user directly, confirmed green (exit 0).
DoD#1 (make test) verified by user directly, as requested. PR should reference decisions/toolchain.md and TASK-15.
<!-- SECTION:NOTES:END -->

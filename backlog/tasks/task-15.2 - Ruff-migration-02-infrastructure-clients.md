---
id: TASK-15.2
title: 'Ruff migration 02: infrastructure/clients'
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:16'
updated_date: '2026-07-23 16:46'
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

---
id: TASK-15.2
title: 'Ruff migration 02: infrastructure/clients'
status: To Do
assignee: []
created_date: '2026-07-23 14:16'
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
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/infrastructure/clients app/tests/unit/infrastructure/clients is empty
- [ ] #2 RUFF_SCOPE and [tool.black] force-exclude both include infrastructure/clients and tests/unit/infrastructure/clients; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes (prompt user to perform the tests); PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

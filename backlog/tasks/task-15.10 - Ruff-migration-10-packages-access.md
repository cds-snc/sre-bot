---
id: TASK-15.10
title: 'Ruff migration 10: packages/access'
status: To Do
assignee: []
created_date: '2026-07-23 14:19'
labels: []
dependencies:
  - TASK-15.9
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 67000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates the packages/access feature package and its unit tests.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- app/packages/access app/tests/unit/packages/access

Note: packages/access/sync/application.py carries reviewed S101 type-narrowing noqa markers (asserts guarded by preceding error checks) from the branch -- keep verbatim.

app/pyproject.toml -> add to [tool.black] force-exclude:
    | packages/access
    | tests/unit/packages/access

app/Makefile -> append to RUFF_SCOPE:
    packages/access tests/unit/packages/access

Validate (from app/): make lint-ci && make fmt-ci && make test
Expected size: ~60 files. If reviewers require <50, split into two PRs by access sub-package: (a) packages/access/sync + packages/access/common, (b) packages/access/catalog + packages/access/request -- pulling the matching tests/unit/packages/access/* files with each. Keep the force-exclude/RUFF_SCOPE entries at the granular sub-package level in that case.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/packages/access app/tests/unit/packages/access is empty
- [ ] #2 force-exclude + RUFF_SCOPE include packages/access and tests/unit/packages/access; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

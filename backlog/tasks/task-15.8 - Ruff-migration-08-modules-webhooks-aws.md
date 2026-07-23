---
id: TASK-15.8
title: 'Ruff migration 08: modules webhooks + aws'
status: To Do
assignee: []
created_date: '2026-07-23 14:18'
labels: []
dependencies:
  - TASK-15.7
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 65000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates modules/webhooks and modules/aws and their tests.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- \
    app/modules/webhooks app/modules/aws \
    app/tests/modules/webhooks app/tests/unit/modules/aws

Note: modules/webhooks and modules/aws files carry reviewed S105/S106/S107 noqa markers (non-secret names) from the branch -- keep verbatim.

app/pyproject.toml -> add to [tool.black] force-exclude:
    | modules/webhooks
    | modules/aws
    | tests/modules/webhooks
    | tests/unit/modules/aws

app/Makefile -> append to RUFF_SCOPE:
    modules/webhooks modules/aws tests/modules/webhooks tests/unit/modules/aws

Validate (from app/): make lint-ci && make fmt-ci && make test
Expected size: ~44 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/modules/webhooks app/modules/aws app/tests/modules/webhooks app/tests/unit/modules/aws is empty
- [ ] #2 force-exclude + RUFF_SCOPE include modules/webhooks, modules/aws, tests/modules/webhooks, tests/unit/modules/aws; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

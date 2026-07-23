---
id: TASK-15.7
title: 'Ruff migration 07: modules incident + small (atip, secret, role)'
status: To Do
assignee: []
created_date: '2026-07-23 14:18'
labels: []
dependencies:
  - TASK-15.6
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 64000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates modules/incident plus the small modules (atip, secret, role) and their tests.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- \
    app/modules/incident app/modules/atip app/modules/secret app/modules/role \
    app/tests/modules/incident app/tests/modules/secret app/tests/modules/role app/tests/unit/modules/atip

Note: modules/secret/secret.py is the actual secrets module and carries carefully-reviewed S-family noqa markers from the checkout -- keep them verbatim; do NOT reflexively add/remove noqa. modules/incident files carry reviewed B904/SIM/S fixes from the branch. modules/atip had an unmerged PR that we are going to merge prior to starting this task. This means the feat/dev_env_setup_ruff branch may have diverging content from main on modules/atip and its tests. We will need to keep the logic change from main but migrate or adjust its formatting from to align with the reference branch feat/dev_env_setup_ruff 

app/pyproject.toml -> add to [tool.black] force-exclude:
    | modules/incident
    | modules/atip
    | modules/secret
    | modules/role
    | tests/modules/incident
    | tests/modules/secret
    | tests/modules/role
    | tests/unit/modules/atip

app/Makefile -> append to RUFF_SCOPE:
    modules/incident modules/atip modules/secret modules/role tests/modules/incident tests/modules/secret tests/modules/role tests/unit/modules/atip

Validate (from app/): make lint-ci && make fmt-ci && make test
Expected size: ~38 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/modules/incident app/modules/atip app/modules/secret app/modules/role app/tests/modules/incident app/tests/modules/secret app/tests/modules/role app/tests/unit/modules/atip is empty
- [ ] #2 force-exclude + RUFF_SCOPE include all listed module src/test dirs; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

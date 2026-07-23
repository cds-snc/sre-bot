---
id: TASK-15.9
title: >-
  Ruff migration 09: modules tail + misc (utils, models, jobs, bin, server);
  completes modules/
status: To Do
assignee: []
created_date: '2026-07-23 14:18'
labels: []
dependencies:
  - TASK-15.8
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 66000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates the remaining small modules (sre, slack, provisioning, dev, reports, modules/__init__.py) plus the miscellaneous top-level src trees (utils, models, jobs, bin, server) and their unit tests. COMPLETES modules/.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- \
    app/modules/sre app/modules/slack app/modules/provisioning app/modules/dev app/modules/reports app/modules/__init__.py \
    app/utils app/models app/jobs app/bin app/server \
    app/tests/modules/slack app/tests/modules/provisioning app/tests/modules/permissions app/tests/modules/ops \
    app/tests/unit/modules/sre app/tests/unit/jobs app/tests/unit/server app/tests/unit/models

Note: bin/check_prefix_command_namespace.py carries the reviewed SIM102/SIM103 rewrites -- after checkout run 'make check-prefix-guardrail' to confirm the guardrail still passes.

CONSOLIDATION (this PR completes modules/, tests/modules/, tests/unit/modules/):
- app/pyproject.toml [tool.black] force-exclude: REPLACE the granular 'modules/*', 'tests/modules/*', 'tests/unit/modules/*' alternatives from TASK-15.7/08 with:
    | modules
    | tests/modules
    | tests/unit/modules
  and ADD the misc trees:
    | utils
    | models
    | jobs
    | bin
    | server
    | tests/unit/jobs
    | tests/unit/server
    | tests/unit/models
- app/Makefile RUFF_SCOPE: replace granular modules tokens with 'modules tests/modules tests/unit/modules' and append 'utils models jobs bin server tests/unit/jobs tests/unit/server tests/unit/models'.

Validate (from app/): make lint-ci && make fmt-ci && make check-prefix-guardrail && make test
Expected size: ~39 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/modules app/tests/modules app/tests/unit/modules app/utils app/models app/jobs app/bin app/server app/tests/unit/jobs app/tests/unit/server app/tests/unit/models is empty
- [ ] #2 force-exclude + RUFF_SCOPE consolidated for modules (modules, tests/modules, tests/unit/modules) and include utils, models, jobs, bin, server + their unit tests; make lint-ci && make fmt-ci pass
- [ ] #3 make check-prefix-guardrail passes after migrating bin/check_prefix_command_namespace.py
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

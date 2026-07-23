---
id: TASK-15.9
title: >-
  Ruff migration 09: modules tail + misc (utils, models, jobs, bin, server);
  completes modules/
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:18'
updated_date: '2026-07-23 20:41'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Branch (done): feat/dev_env_setup_ruff_9, branched from main after TASK-15.8.
2. Pull migrated content for this slice from the reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- \
     app/modules/sre app/modules/slack app/modules/provisioning app/modules/dev app/modules/reports app/modules/__init__.py \
     app/utils app/models app/jobs app/bin app/server \
     app/tests/modules/slack app/tests/modules/provisioning app/tests/modules/permissions app/tests/modules/ops \
     app/tests/unit/modules/sre app/tests/unit/jobs app/tests/unit/server app/tests/unit/models
   Verified against current main: git diff --stat main feat/dev_env_setup_ruff -- <paths> -> 40 files changed, 261 insertions(+), 511 deletions(-); no adds/deletes (git diff --diff-filter=AD --name-status empty). Matches expected ~39 files in the task description.
   Note: app/modules/ops and app/modules/permissions are NOT in the pull list (already byte-identical to the reference branch -- confirmed empty diff) but their tests dirs (tests/modules/ops, tests/modules/permissions) DO change and are pulled. Both source dirs still move into the consolidated RUFF_SCOPE/force-exclude below since this PR completes modules/ as a whole.
   Note: bin/check_prefix_command_namespace.py carries reviewed SIM102/SIM103 rewrites -- run 'make check-prefix-guardrail' after checkout to confirm the guardrail still passes.
3. Edit app/pyproject.toml [tool.black] force-exclude: replace the granular modules/incident, modules/atip, modules/secret, modules/role, modules/webhooks, modules/aws, tests/modules/incident, tests/modules/secret, tests/modules/role, tests/modules/webhooks, tests/unit/modules/atip, tests/unit/modules/aws entries with the consolidated:
     | modules
     | tests/modules
     | tests/unit/modules
   and add the misc trees:
     | utils
     | models
     | jobs
     | bin
     | server
     | tests/unit/jobs
     | tests/unit/server
     | tests/unit/models
   Leave [tool.ruff.lint] select = ["E","F","W"] and the api/infrastructure/integrations force-exclude entries from prior PRs unchanged.
4. Edit app/Makefile RUFF_SCOPE: replace the granular modules/* and tests/modules/* and tests/unit/modules/* tokens with 'modules tests/modules tests/unit/modules' and append 'utils models jobs bin server tests/unit/jobs tests/unit/server tests/unit/models'. Do not touch fmt/lint/fmt-ci/lint-ci target bodies (already generic).
5. Edit .github/workflows/scripts/run_bandit_scan.sh RUFF_MIGRATED_PATHS to stay in sync: replace the granular modules/* entries with /data/app/modules,/data/app/tests/modules,/data/app/tests/unit/modules and append /data/app/utils,/data/app/models,/data/app/jobs,/data/app/bin,/data/app/server,/data/app/tests/unit/jobs,/data/app/tests/unit/server,/data/app/tests/unit/models.
6. Validate from app/: make lint-ci && make fmt-ci && make check-prefix-guardrail && uv run pytest tests/modules tests/unit/modules tests/unit/jobs tests/unit/server tests/unit/models tests/utils -q (scoped run to keep iteration fast; full make test deferred).
7. Confirm git diff feat/dev_env_setup_ruff -- <all pulled paths> is empty (AC#1).
8. Defer make test (long-running full suite) to the user to run directly as the final check before closing this task -- do not run it as the agent.
9. Ship one mechanical PR; reference decisions/toolchain.md and TASK-15.

AC-to-step traceability:
- AC#1 (byte-identical to reference branch) <- step 2, verified by step 7.
- AC#2 (force-exclude + RUFF_SCOPE consolidated for modules and include utils/models/jobs/bin/server + unit tests; make lint-ci && make fmt-ci pass) <- steps 3, 4, verified by step 6.
- AC#3 (make check-prefix-guardrail passes) <- step 6.
- DoD#1 (make test passes; PR references decisions/toolchain.md + TASK-15) <- step 8 (user-run) + PR description (human/PR action).
<!-- SECTION:PLAN:END -->

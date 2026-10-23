---
id: TASK-15.8
title: 'Ruff migration 08: modules webhooks + aws'
status: Done
assignee:
  - '@me'
created_date: '2026-07-23 14:18'
updated_date: '2026-07-23 21:44'
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
- [x] #1 git diff feat/dev_env_setup_ruff -- app/modules/webhooks app/modules/aws app/tests/modules/webhooks app/tests/unit/modules/aws is empty
- [x] #2 force-exclude + RUFF_SCOPE include modules/webhooks, modules/aws, tests/modules/webhooks, tests/unit/modules/aws; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Branch from latest main (done): feat/dev_env_setup_ruff_8, branched after TASK-15.7 merged.
2. Pull migrated content for this slice from the reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- app/modules/webhooks app/modules/aws app/tests/modules/webhooks app/tests/unit/modules/aws
   Verified against current main: git diff --stat main feat/dev_env_setup_ruff -- <paths> -> 44 files changed, 329 insertions(+), 706 deletions(-); no adds/deletes (git diff --diff-filter=AD --name-status empty). Matches expected ~44 files in the task description.
   Note: modules/webhooks and modules/aws files carry reviewed S105/S106/S107 noqa markers (non-secret names) arriving via the checkout -- keep them verbatim; do not add or remove noqa.
3. Edit app/pyproject.toml [tool.black] force-exclude block: add inside the existing /( ... )/ group:
     | modules/webhooks
     | modules/aws
     | tests/modules/webhooks
     | tests/unit/modules/aws
   Leave [tool.ruff.lint] select = ["E","F","W"] and everything else (including prior consolidated entries from TASK-15.6/15.7) unchanged.
4. Edit app/Makefile: append to RUFF_SCOPE:
     modules/webhooks modules/aws tests/modules/webhooks tests/unit/modules/aws
   Do not touch fmt/lint/fmt-ci/lint-ci target bodies (already generic).
5. Edit .github/workflows/scripts/run_bandit_scan.sh RUFF_MIGRATED_PATHS to keep in sync with RUFF_SCOPE, appending:
     /data/app/modules/webhooks,/data/app/modules/aws,/data/app/tests/modules/webhooks,/data/app/tests/unit/modules/aws
6. Validate from app/: make lint-ci && make fmt-ci && uv run pytest tests/modules/webhooks tests/unit/modules/aws.
7. Confirm git diff feat/dev_env_setup_ruff -- <all 4 paths> is empty (AC#1).
8. Defer make test (long-running, full suite) to the user to run directly as the final check before closing this task -- do not run it as the agent.
9. Ship one mechanical PR; reference decisions/toolchain.md and TASK-15.

AC-to-step traceability:
- AC#1 (byte-identical to reference branch) <- step 2, verified by step 7.
- AC#2 (force-exclude + RUFF_SCOPE include listed dirs; make lint-ci && make fmt-ci pass) <- steps 3, 4, verified by step 6.
- DoD#1 (make test passes; PR references decisions/toolchain.md + TASK-15) <- step 8 (user-run) + PR description (human/PR action).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per plan (mirrors TASK-15.1/15.5/15.6/15.7 recipe):
1. git checkout feat/dev_env_setup_ruff -- app/modules/webhooks app/modules/aws app/tests/modules/webhooks app/tests/unit/modules/aws (44 files, no adds/deletes -- matches expected size; verified via git diff --stat and --diff-filter=AD against main before edits). git diff feat/dev_env_setup_ruff -- <same paths> is empty (AC#1 verified). Reviewed S105/S106/S107 noqa markers in the checked-out files kept verbatim; none added or removed.
2. app/pyproject.toml [tool.black] force-exclude: added modules/webhooks, modules/aws, tests/modules/webhooks, tests/unit/modules/aws inside the existing /( ... )/ group. Prior consolidated entries (api, infrastructure, integrations, modules/incident+atip+secret+role) left unchanged.
3. app/Makefile: RUFF_SCOPE extended with modules/webhooks modules/aws tests/modules/webhooks tests/unit/modules/aws. fmt/lint/fmt-ci/lint-ci target bodies untouched (already generic).
4. .github/workflows/scripts/run_bandit_scan.sh RUFF_MIGRATED_PATHS updated in sync with RUFF_SCOPE (appended /data/app/modules/webhooks,/data/app/modules/aws,/data/app/tests/modules/webhooks,/data/app/tests/unit/modules/aws).
5. Validation:
   - make lint-ci -> both ruff invocations "All checks passed!"; mypy soft-fails via existing "|| true" with 128 pre-existing errors, same profile/count as TASK-15.7's baseline, all in unrelated legacy modules -- not a regression.
   - make fmt-ci -> black 210 files unchanged; ruff format 437 files already formatted.
   - uv run pytest tests/modules/webhooks tests/unit/modules/aws -q -> 222 passed, 1 pre-existing deprecation warning, 0 failures.
   - git diff feat/dev_env_setup_ruff -- app/modules/webhooks app/modules/aws app/tests/modules/webhooks app/tests/unit/modules/aws -> empty (AC#1 confirmed).
DoD#1: user ran `make test` (full suite, from app/) directly and confirmed it is all green (exit 0). DoD#1 verified.
PR should reference decisions/toolchain.md and TASK-15.
<!-- SECTION:NOTES:END -->

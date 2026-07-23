---
id: TASK-15.4
title: 'Ruff migration 04: infrastructure reliability tail (completes infrastructure/)'
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:17'
updated_date: '2026-07-23 17:27'
labels: []
dependencies:
  - TASK-15.3
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 61000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates the remaining infrastructure subsystems (resilience, idempotency, logging, audit, operations, events, storage) plus the leftover loose unit-test files, COMPLETING infrastructure/.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- \
    app/infrastructure/resilience app/infrastructure/idempotency app/infrastructure/logging app/infrastructure/audit app/infrastructure/operations app/infrastructure/events app/infrastructure/storage \
    app/tests/unit/infrastructure/resilience app/tests/unit/infrastructure/idempotency app/tests/unit/infrastructure/logging app/tests/unit/infrastructure/audit app/tests/unit/infrastructure/operations app/tests/unit/infrastructure/events app/tests/unit/infrastructure/storage app/tests/unit/infrastructure/services \
    app/tests/unit/infrastructure/conftest.py app/tests/unit/infrastructure/test_operations_result.py app/tests/unit/infrastructure/test_logging.py app/tests/unit/infrastructure/test_circuit_breaker.py

CONSOLIDATION (this PR completes the whole infrastructure/ + tests/unit/infrastructure/ trees):
- app/pyproject.toml [tool.black] force-exclude: REPLACE all the granular 'infrastructure/*' and 'tests/unit/infrastructure/*' alternatives added by TASK-15.2 and TASK-15.3 with just two lines:
    | infrastructure
    | tests/unit/infrastructure
- app/Makefile RUFF_SCOPE: REMOVE the granular infrastructure/* and tests/unit/infrastructure/* tokens and replace them with:
    infrastructure tests/unit/infrastructure
  (This is a pure simplification; the migrated file set is unchanged. Verify with the AC diff check.)

Validate (from app/): make lint-ci && make fmt-ci && make test
Expected size: ~59 files (note: reviewers may split resilience/idempotency/logging from audit/operations/events/storage into two PRs if <50 is required).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/infrastructure app/tests/unit/infrastructure is empty (entire infrastructure src + unit-test trees now migrated)
- [ ] #2 force-exclude and RUFF_SCOPE consolidated to the single entries 'infrastructure' and 'tests/unit/infrastructure'; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Branch from latest main (done): feat/dev_env_setup_ruff_4, branched after TASK-15.3 merged.
2. Pull migrated content for this slice from the reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- app/infrastructure/resilience app/infrastructure/idempotency app/infrastructure/logging app/infrastructure/audit app/infrastructure/operations app/infrastructure/events app/infrastructure/storage app/tests/unit/infrastructure/resilience app/tests/unit/infrastructure/idempotency app/tests/unit/infrastructure/logging app/tests/unit/infrastructure/audit app/tests/unit/infrastructure/operations app/tests/unit/infrastructure/events app/tests/unit/infrastructure/storage app/tests/unit/infrastructure/services app/tests/unit/infrastructure/conftest.py app/tests/unit/infrastructure/test_operations_result.py app/tests/unit/infrastructure/test_logging.py app/tests/unit/infrastructure/test_circuit_breaker.py
   Verified against current main: git diff --stat main feat/dev_env_setup_ruff -- <paths> -> 59 files changed, 411 insertions(+), 672 deletions(-); no adds/deletes (git diff --diff-filter=AD --name-status empty). Matches expected ~59 files in the task description.
3. CONSOLIDATE app/pyproject.toml [tool.black] force-exclude: this PR completes the whole infrastructure/ tree, so REPLACE all granular infrastructure/* and tests/unit/infrastructure/* alternatives added by TASK-15.2/15.3 with just:
     | infrastructure
     | tests/unit/infrastructure
   (keeping the `api` / `tests/api` alternatives from TASK-15.1 unchanged). Leave [tool.ruff.lint] select = ["E","F","W"] unchanged.
4. CONSOLIDATE app/Makefile RUFF_SCOPE: remove the granular infrastructure/* and tests/unit/infrastructure/* tokens, replace with:
     RUFF_SCOPE := api tests/api infrastructure tests/unit/infrastructure
   Pure simplification, migrated file set unchanged. Do not touch fmt/lint/fmt-ci/lint-ci target bodies (already reference $(RUFF_SCOPE) generically, using --extend-select per TASK-15.2's fix).
5. Validate from app/: make lint-ci && make fmt-ci && uv run pytest tests/unit/infrastructure (whole consolidated tree, since RUFF_SCOPE/force-exclude now cover it as one unit).
6. Confirm git diff feat/dev_env_setup_ruff -- app/infrastructure app/tests/unit/infrastructure is empty (AC#1) -- this now covers the ENTIRE infrastructure src + unit-test trees since TASK-15.2/15.3/15.4 combined complete the migration.
7. Defer make test (long-running, full suite) to the user to run directly as the final check before closing this task -- do not run it as the agent.
8. Ship one mechanical PR; reference decisions/toolchain.md and TASK-15.

AC-to-step traceability:
- AC#1 (git diff feat/dev_env_setup_ruff -- app/infrastructure app/tests/unit/infrastructure empty) <- step 2, verified by step 6.
- AC#2 (force-exclude + RUFF_SCOPE consolidated to single entries; make lint-ci && make fmt-ci pass) <- steps 3, 4, verified by step 5.
- DoD#1 (make test passes; PR references decisions/toolchain.md + TASK-15) <- step 7 (user-run) + PR description (human/PR action).
<!-- SECTION:PLAN:END -->

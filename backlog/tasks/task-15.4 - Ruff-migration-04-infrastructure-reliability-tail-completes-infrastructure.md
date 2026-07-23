---
id: TASK-15.4
title: 'Ruff migration 04: infrastructure reliability tail (completes infrastructure/)'
status: To Do
assignee: []
created_date: '2026-07-23 14:17'
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

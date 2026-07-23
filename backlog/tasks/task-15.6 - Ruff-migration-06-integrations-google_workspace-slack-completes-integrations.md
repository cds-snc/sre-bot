---
id: TASK-15.6
title: >-
  Ruff migration 06: integrations google_workspace + slack (completes
  integrations/)
status: To Do
assignee: []
created_date: '2026-07-23 14:18'
labels: []
dependencies:
  - TASK-15.5
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 63000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates the two largest integrations (google_workspace, slack) and their tests, COMPLETING integrations/.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- \
    app/integrations/google_workspace app/integrations/slack \
    app/tests/integrations/google_workspace app/tests/integrations/slack

Note: slack + google_workspace files carry reviewed S105/S106/S107 noqa markers (non-secret token/field names) from the checkout -- keep verbatim.

CONSOLIDATION (this PR completes integrations/ and tests/integrations/):
- app/pyproject.toml [tool.black] force-exclude: REPLACE the granular 'integrations/*' and 'tests/integrations/*' alternatives from TASK-15.5 with:
    | integrations
    | tests/integrations
  (Leave the 'tests/unit/integrations' line from TASK-15.5 as-is.)
- app/Makefile RUFF_SCOPE: replace the granular integrations/* and tests/integrations/* tokens with:
    integrations tests/integrations
  (Keep tests/unit/integrations.)

Validate (from app/): make lint-ci && make fmt-ci && make test
Expected size: ~39 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/integrations app/tests/integrations is empty (entire integrations src + legacy-test trees now migrated)
- [ ] #2 force-exclude + RUFF_SCOPE consolidated to 'integrations' and 'tests/integrations' (tests/unit/integrations already migrated in TASK-15.5); make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

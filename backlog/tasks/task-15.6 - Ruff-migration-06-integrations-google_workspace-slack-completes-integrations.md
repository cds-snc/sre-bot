---
id: TASK-15.6
title: >-
  Ruff migration 06: integrations google_workspace + slack (completes
  integrations/)
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:18'
updated_date: '2026-07-23 18:50'
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
- [x] #1 git diff feat/dev_env_setup_ruff -- app/integrations app/tests/integrations is empty (entire integrations src + legacy-test trees now migrated)
- [x] #2 force-exclude + RUFF_SCOPE consolidated to 'integrations' and 'tests/integrations' (tests/unit/integrations already migrated in TASK-15.5); make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Pull migrated content for this slice from reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- app/integrations/google_workspace app/integrations/slack app/tests/integrations/google_workspace app/tests/integrations/slack
   Verify expected scope via git diff --stat main feat/dev_env_setup_ruff -- <paths> (about 39 files; no adds/deletes).
2. Consolidate app/pyproject.toml [tool.black] force-exclude integrations entries by replacing granular TASK-15.5 alternatives with:
     | integrations
     | tests/integrations
   Keep existing entries for api, tests/api, infrastructure, tests/unit/infrastructure, and tests/unit/integrations unchanged.
3. Consolidate app/Makefile RUFF_SCOPE by replacing granular integrations/* + tests/integrations/* tokens with:
     integrations tests/integrations
   Keep tests/unit/integrations token and the existing infrastructure/api tokens; do not edit target bodies.
4. Keep .github/workflows/scripts/run_bandit_scan.sh RUFF_MIGRATED_PATHS in sync with RUFF_SCOPE by replacing granular integrations and tests/integrations entries with:
     /data/app/integrations,/data/app/tests/integrations
   Keep /data/app/tests/unit/integrations and all existing non-integrations migrated paths.
5. Validate from app/: make lint-ci && make fmt-ci && uv run pytest tests/integrations/google_workspace tests/integrations/slack.
6. Verify AC#1: git diff feat/dev_env_setup_ruff -- app/integrations app/tests/integrations is empty.
7. Defer full-suite make test until the very end and prompt the user to run it locally because it is long-running/token-heavy; once user confirms success, check DoD and finalize notes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per TASK-15.1 shared recipe and prior TASK-15.x migration slices:
1. Pulled migrated content from reference branch (no hand edits to migrated sources/tests):
   git checkout feat/dev_env_setup_ruff -- app/integrations/google_workspace app/integrations/slack app/tests/integrations/google_workspace app/tests/integrations/slack
   Scope verification against main: 39 files changed, 614 insertions(+), 1218 deletions(-), no adds/deletes (AD count 0).
2. Consolidation edits for integrations completion:
   - app/pyproject.toml [tool.black] force-exclude: replaced granular integrations/* + tests/integrations/* entries with:
       | integrations
       | tests/integrations
     Kept tests/unit/integrations and prior api/infrastructure entries unchanged.
   - app/Makefile RUFF_SCOPE consolidated to:
       api tests/api infrastructure tests/unit/infrastructure integrations tests/integrations tests/unit/integrations
   - .github/workflows/scripts/run_bandit_scan.sh RUFF_MIGRATED_PATHS kept in sync with Makefile scope by consolidating to:
       /data/app/integrations,/data/app/tests/integrations
     while preserving /data/app/tests/unit/integrations and earlier migrated paths.
3. Validation evidence:
   - AC#1: git diff feat/dev_env_setup_ruff -- app/integrations app/tests/integrations is empty (0 changed files).
   - AC#2 command coverage:
     * make lint-ci -> pass (ruff checks pass; mypy remains soft-failing via existing '|| true', same pre-existing debt profile from prior TASK-15 slices, not a migration regression).
     * make fmt-ci -> pass (black --check clean; ruff format --check clean on consolidated RUFF_SCOPE).
     * Focused tests for migrated large integrations: uv run pytest -q tests/integrations/google_workspace tests/integrations/slack -> 247 passed, 5 warnings, 0 failures.
4. DoD#1: full suite run deferred to user as instructed for token/runtime reasons; user executed make test from /workspace and confirmed all green (exit 0).
PR should reference decisions/toolchain.md and TASK-15.
<!-- SECTION:NOTES:END -->

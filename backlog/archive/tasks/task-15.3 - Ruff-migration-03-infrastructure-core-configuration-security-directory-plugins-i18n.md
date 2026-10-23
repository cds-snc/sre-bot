---
id: TASK-15.3
title: >-
  Ruff migration 03: infrastructure core (configuration, security, directory,
  plugins, i18n)
status: Done
assignee:
  - '@me'
created_date: '2026-07-23 14:17'
updated_date: '2026-07-23 21:44'
labels: []
dependencies:
  - TASK-15.2
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 60000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates the infrastructure core services and their unit tests.

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- \
    app/infrastructure/configuration app/infrastructure/security app/infrastructure/directory app/infrastructure/plugins app/infrastructure/i18n \
    app/tests/unit/infrastructure/configuration app/tests/unit/infrastructure/security app/tests/unit/infrastructure/directory app/tests/unit/infrastructure/plugins app/tests/unit/infrastructure/i18n

IMPORTANT: this slice carries the pre-existing circular-import fix that ruff's I001 import-sorting exposed, in infrastructure/security/current_user.py and infrastructure/directory/google.py (they now import from infrastructure.security.jwks / infrastructure.directory.models directly). That fix arrives automatically via the checkout above -- do not re-introduce the parent-package self-imports. Run the full suite to confirm no import regression.

app/pyproject.toml -> add to the [tool.black] force-exclude group:
    | infrastructure/configuration
    | infrastructure/security
    | infrastructure/directory
    | infrastructure/plugins
    | infrastructure/i18n
    | tests/unit/infrastructure/configuration
    | tests/unit/infrastructure/security
    | tests/unit/infrastructure/directory
    | tests/unit/infrastructure/plugins
    | tests/unit/infrastructure/i18n

app/Makefile -> append to RUFF_SCOPE:
    infrastructure/configuration infrastructure/security infrastructure/directory infrastructure/plugins infrastructure/i18n tests/unit/infrastructure/configuration tests/unit/infrastructure/security tests/unit/infrastructure/directory tests/unit/infrastructure/plugins tests/unit/infrastructure/i18n

Validate (from app/): make lint-ci && make fmt-ci && make test
Expected size: ~52 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 git diff feat/dev_env_setup_ruff -- app/infrastructure/configuration app/infrastructure/security app/infrastructure/directory app/infrastructure/plugins app/infrastructure/i18n app/tests/unit/infrastructure/configuration app/tests/unit/infrastructure/security app/tests/unit/infrastructure/directory app/tests/unit/infrastructure/plugins app/tests/unit/infrastructure/i18n is empty
- [x] #2 RUFF_SCOPE and [tool.black] force-exclude include all five src dirs and their five unit-test dirs; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Branch from latest main (done): feat/dev_env_setup_ruff_3, branched after TASK-15.2 merged.
2. Pull migrated content for this slice from the reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- app/infrastructure/configuration app/infrastructure/security app/infrastructure/directory app/infrastructure/plugins app/infrastructure/i18n app/tests/unit/infrastructure/configuration app/tests/unit/infrastructure/security app/tests/unit/infrastructure/directory app/tests/unit/infrastructure/plugins app/tests/unit/infrastructure/i18n
   Verified against current main: git diff --stat main feat/dev_env_setup_ruff -- <paths> -> 52 files changed, no adds/deletes (git diff --diff-filter=AD --name-status is empty). Matches expected ~52 files in the task description.
   This slice carries the pre-existing circular-import fix (infrastructure/security/current_user.py, infrastructure/directory/google.py importing from infrastructure.security.jwks / infrastructure.directory.models directly instead of parent-package self-imports) -- arrives automatically via checkout, do not re-introduce the old self-imports.
3. Edit app/pyproject.toml [tool.black] force-exclude block: add five alternatives inside the existing /( ... )/ group (after infrastructure/clients, before tests/unit/infrastructure/clients, to keep src dirs grouped before test dirs -- order within the regex is not semantically significant, alternation matches any line):
     | infrastructure/configuration
     | infrastructure/security
     | infrastructure/directory
     | infrastructure/plugins
     | infrastructure/i18n
     | tests/unit/infrastructure/configuration
     | tests/unit/infrastructure/security
     | tests/unit/infrastructure/directory
     | tests/unit/infrastructure/plugins
     | tests/unit/infrastructure/i18n
   Leave [tool.ruff.lint] select = ["E","F","W"] and everything else unchanged.
4. Edit app/Makefile: append to RUFF_SCOPE:
     RUFF_SCOPE := api tests/api infrastructure/clients tests/unit/infrastructure/clients infrastructure/configuration infrastructure/security infrastructure/directory infrastructure/plugins infrastructure/i18n tests/unit/infrastructure/configuration tests/unit/infrastructure/security tests/unit/infrastructure/directory tests/unit/infrastructure/plugins tests/unit/infrastructure/i18n
   Do not touch fmt/lint/fmt-ci/lint-ci target bodies (already reference $(RUFF_SCOPE) generically per TASK-15.1 scaffolding, using --extend-select per the TASK-15.2 root-cause fix).
5. Validate from app/: make lint-ci && make fmt-ci && uv run pytest tests/unit/infrastructure/configuration tests/unit/infrastructure/security tests/unit/infrastructure/directory tests/unit/infrastructure/plugins tests/unit/infrastructure/i18n. Run the full test suite (make test) to confirm no import regression from the circular-import fix, but defer that run to the end (long-running) with explicit user confirmation before executing.
6. Confirm git diff feat/dev_env_setup_ruff -- <all ten paths> is empty (AC#1).
7. Ship one mechanical PR; reference decisions/toolchain.md and TASK-15.

AC-to-step traceability:
- AC#1 (byte-identical to reference branch) <- step 2, verified by step 6.
- AC#2 (RUFF_SCOPE + force-exclude updated for all 10 paths; make lint-ci && make fmt-ci pass) <- steps 3, 4, verified by step 5.
- DoD#1 (make test passes; PR references decisions/toolchain.md + TASK-15) <- step 5 (full make test, user-confirmed) + PR description (human/PR action).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per plan (mirrors TASK-15.1/15.2 recipe):
1. git checkout feat/dev_env_setup_ruff -- app/infrastructure/{configuration,security,directory,plugins,i18n} app/tests/unit/infrastructure/{configuration,security,directory,plugins,i18n} (52 files, no adds/deletes -- matches expected size). git diff feat/dev_env_setup_ruff -- <same paths> is empty both before and after config edits (AC#1 verified).
   Confirmed the circular-import fix (infrastructure/security/current_user.py, infrastructure/directory/google.py now import from infrastructure.security.jwks / infrastructure.directory.models directly) arrived via the checkout; no parent-package self-imports were reintroduced.
2. app/pyproject.toml [tool.black] force-exclude: added the five infrastructure src alternatives and five tests/unit/infrastructure alternatives (configuration, security, directory, plugins, i18n) inside the existing /( ... )/ group.
3. app/Makefile: RUFF_SCOPE extended with all ten new paths (kept existing api/tests/api/infrastructure/clients/tests/unit/infrastructure/clients entries from prior slices). fmt/lint/fmt-ci/lint-ci target bodies untouched (already generic + using --extend-select per TASK-15.2's fix).
4. Validation: make lint-ci -> both ruff invocations "All checks passed!"; mypy soft-fails via existing "|| true" with 126 pre-existing errors in unrelated legacy modules (modules/incident, modules/webhooks, modules/role, packages/access) -- same count as TASK-15.1/15.2 notes, not a regression, not caused by this slice. make fmt-ci -> black 518 files unchanged, ruff format 144 files already formatted. uv run pytest tests/unit/infrastructure/{configuration,security,directory,plugins,i18n} -> 318 passed, 0 failures (no import regression from the circular-import fix).
DoD#1 (make test, full suite) intentionally deferred: it is long-running, so the user will run it directly rather than the agent, per explicit instruction, as the final check before closing this task. PR should reference decisions/toolchain.md and TASK-15.
<!-- SECTION:NOTES:END -->

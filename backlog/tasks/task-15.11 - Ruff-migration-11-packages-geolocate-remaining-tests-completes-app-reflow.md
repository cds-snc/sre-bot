---
id: TASK-15.11
title: >-
  Ruff migration 11: packages/geolocate + remaining tests (completes app/
  reflow)
status: In Progress
assignee:
  - '@me'
created_date: '2026-07-23 14:19'
updated_date: '2026-07-23 21:17'
labels: []
dependencies:
  - TASK-15.10
references:
  - decisions/toolchain.md
parent_task_id: TASK-15
ordinal: 68000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow the SHARED RECIPE in TASK-15.1. Migrates packages/geolocate plus every remaining test surface (tests/integration, factories, fixtures, tests/utils, smoke, and the two loose tests/*.py files). After this PR ALL app source and test files are byte-identical to the reference branch; only the toolchain config still differs (handled by TASK-15.12).

Paths to pull:
  git checkout feat/dev_env_setup_ruff -- \
    app/packages/geolocate app/tests/unit/packages/geolocate \
    app/tests/integration app/tests/factories app/tests/fixtures app/tests/utils app/tests/smoke \
    app/tests/conftest.py app/tests/test_factory_validation.py

Note: packages/geolocate/routes.py and schemas.py carry reviewed S-family noqa from the branch -- keep verbatim.

CONSOLIDATION (this PR completes packages/ and the entire tests/ tree):
- app/pyproject.toml [tool.black] force-exclude: REPLACE the 'packages/access' + 'tests/unit/packages/access' entries from TASK-15.10 with 'packages', and replace ALL the granular 'tests/*' alternatives accumulated so far (tests/api, tests/unit/*, tests/modules, tests/integrations, tests/integration, ...) with a single 'tests' entry. The force-exclude block should now read simply:
      force-exclude = '''
      /(
          api
        | infrastructure
        | integrations
        | modules
        | packages
        | utils
        | models
        | jobs
        | bin
        | server
        | tests
      )/
      '''
- app/Makefile RUFF_SCOPE: collapse to the migrated top-level trees:
      RUFF_SCOPE := api infrastructure integrations modules packages utils models jobs bin server tests

Validate (from app/): make lint-ci && make fmt-ci && make test
Sanity: 'git diff feat/dev_env_setup_ruff -- app' should now show ONLY app/pyproject.toml, app/Makefile, app/uv.lock (config not yet cut over).
Expected size: ~38 files.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/packages app/tests is empty (every app source + test file now matches the reference branch)
- [ ] #2 force-exclude + RUFF_SCOPE consolidated to 'packages' and 'tests'; make lint-ci && make fmt-ci pass over the whole tree
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Branch (done): feat/dev_env_setup_ruff_11, branched from main after TASK-15.10 content landed on main.
2. Pull migrated content for this slice from the reference branch (never hand-edit migrated source):
   git checkout feat/dev_env_setup_ruff -- app/packages/geolocate app/tests/unit/packages/geolocate app/tests/integration app/tests/factories app/tests/fixtures app/tests/utils app/tests/smoke app/tests/conftest.py app/tests/test_factory_validation.py
   Verified against current main: git diff --stat main feat/dev_env_setup_ruff -- <paths> -> 37 files changed, 257 insertions(+), 461 deletions(-); no adds/deletes (git diff --diff-filter=AD --name-status empty). Matches expected ~38 files in the task description.
   Note: packages/geolocate/routes.py and schemas.py carry reviewed S-family noqa markers from the reference branch -- keep verbatim, do not edit.
3. Edit app/pyproject.toml [tool.black] force-exclude: replace the entire alternation (currently api | tests/api | infrastructure | tests/unit/infrastructure | integrations | tests/integrations | tests/unit/integrations | modules | tests/modules | tests/unit/modules | utils | models | jobs | bin | server | tests/unit/jobs | tests/unit/server | tests/unit/models | packages/access | tests/unit/packages/access) with the consolidated:
     api | infrastructure | integrations | modules | packages | utils | models | jobs | bin | server | tests
   Leave [tool.ruff.lint] select/extend-select unchanged.
4. Edit app/Makefile RUFF_SCOPE: collapse to 'api infrastructure integrations modules packages utils models jobs bin server tests'. Do not touch fmt/lint/fmt-ci/lint-ci target bodies (already generic).
5. Edit .github/workflows/scripts/run_bandit_scan.sh RUFF_MIGRATED_PATHS to stay in sync: collapse to /data/app/api,/data/app/infrastructure,/data/app/integrations,/data/app/modules,/data/app/packages,/data/app/utils,/data/app/models,/data/app/jobs,/data/app/bin,/data/app/server,/data/app/tests.
6. Validate from app/: make lint-ci && make fmt-ci. Run a scoped pytest first to keep iteration fast: uv run pytest tests/unit/packages/geolocate tests/integration tests/utils tests/smoke tests/test_factory_validation.py -q --collect-only (smoke requires live creds so collect-only there; run the rest for real). Defer the full 'make test' (long-running) to the user to run directly as the final DoD check before closing this task -- do not run it as the agent.
7. Confirm git diff feat/dev_env_setup_ruff -- app/packages app/tests is empty (AC#1), and git diff feat/dev_env_setup_ruff -- app shows only app/pyproject.toml, app/Makefile, app/uv.lock (sanity check from task description).
8. Ship one mechanical PR; reference decisions/toolchain.md and TASK-15.

AC-to-step traceability:
- AC#1 (git diff feat/dev_env_setup_ruff -- app/packages app/tests empty) <- step 2, verified by step 7.
- AC#2 (force-exclude + RUFF_SCOPE consolidated to packages/tests; make lint-ci && make fmt-ci pass) <- steps 3, 4, verified by step 6.
- DoD#1 (make test passes; PR references decisions/toolchain.md + TASK-15) <- step 6 (user-run, deferred) + PR description (human/PR action).
<!-- SECTION:PLAN:END -->

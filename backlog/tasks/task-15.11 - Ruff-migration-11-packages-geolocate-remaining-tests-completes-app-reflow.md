---
id: TASK-15.11
title: >-
  Ruff migration 11: packages/geolocate + remaining tests (completes app/
  reflow)
status: To Do
assignee: []
created_date: '2026-07-23 14:19'
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

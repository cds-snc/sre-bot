---
id: TASK-15.3
title: >-
  Ruff migration 03: infrastructure core (configuration, security, directory,
  plugins, i18n)
status: To Do
assignee: []
created_date: '2026-07-23 14:17'
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
- [ ] #1 git diff feat/dev_env_setup_ruff -- app/infrastructure/configuration app/infrastructure/security app/infrastructure/directory app/infrastructure/plugins app/infrastructure/i18n app/tests/unit/infrastructure/configuration app/tests/unit/infrastructure/security app/tests/unit/infrastructure/directory app/tests/unit/infrastructure/plugins app/tests/unit/infrastructure/i18n is empty
- [ ] #2 RUFF_SCOPE and [tool.black] force-exclude include all five src dirs and their five unit-test dirs; make lint-ci && make fmt-ci pass
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 make test passes; PR references decisions/toolchain.md and TASK-15
<!-- DOD:END -->

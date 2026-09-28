---
id: TASK-111
title: >-
  Load settings from checked-in base and per-ENVIRONMENT TOML files; environment
  variables carry only secrets and deployment identity
status: To Do
assignee: []
created_date: '2026-09-24 19:59'
updated_date: '2026-09-25 15:00'
labels:
  - plugin-architecture
  - configuration
milestone: m-7
dependencies:
  - TASK-24
references:
  - decisions/configuration.md
  - decisions/lifecycle.md
priority: medium
type: feature
ordinal: 253000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/configuration.md:
- values come from checked-in TOML configuration files: a base file with defaults for every slice, plus one file per environment, selected by ENVIRONMENT and loaded through pydantic-settings' TOML source, with each slice reading its own table;
- environment variables carry only secrets and deployment identity (ENVIRONMENT, GIT_SHA);
- every slice validates in lifespan's configuration phase, and an invalid file fails boot naming the key.
This is the "configuration files and TOML loading" ticket the record says is still to create.

Scope: the loader, the precedence rules, the file layout, the CI checks, and moving the non-secret values of the host and framework slices (server, security, logging, transport) into the files. The deployment side (terraform task definitions, SSM parameters) stops setting the moved non-secret values in the same change.

Feature and capability slices move their values into the files when their package moves (decisions/configuration.md: "Migration rides with the work"). Each package-move ticket carries that acceptance criterion, so no slice is left split between files and environment variables.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A base TOML file and one file per ENVIRONMENT value exist in the repo; pydantic-settings loads base, then the environment file, then secrets from the environment
- [ ] #2 The host and framework slices read their non-secret values from the files, and the deployment config no longer sets those values as environment variables
- [ ] #3 Boot test: an invalid file or an unknown key fails boot with a message naming the key; a missing required secret fails naming it
- [ ] #4 CI checks: no secret-shaped key appears in a configuration file; each key is owned by exactly one settings slice
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #6 Before any value moves, the current contents of the sre-bot-config and sre-bot-config-infrastructure SSM parameters (read by app/bin/entry.sh into .env) are inventoried by key, with secret values omitted, and each key is mapped to its owning slice and to a file, a secret or deletion; the inventory records whether production sets ACCESS_SYNC_ENABLED, AWS_ORG_ACCOUNT_ROLE_ARN and DIRECTORY_REQUIRE_STARTUP_WARMUP
<!-- AC:END -->

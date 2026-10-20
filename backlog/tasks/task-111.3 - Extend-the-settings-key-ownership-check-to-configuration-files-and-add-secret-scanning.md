---
id: TASK-111.3
title: >-
  Extend the settings key ownership check to configuration files and add secret
  scanning
status: To Do
assignee: []
created_date: '2026-10-20 23:25'
updated_date: '2026-10-20 23:36'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.2
references:
  - app/bin/check_settings_key_ownership.py
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1750'
parent_task_id: TASK-111
type: feature
ordinal: 409000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
bin/check_settings_key_ownership.py gains a config-file claim source: each table in app/config/*.toml is claimed by the slice that names it; a table no slice owns fails; a secret-shaped key fails; the platform-provided names and the exempt SDK namespaces are allow-listed. gitleaks (MIT) runs in CI over the repository.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each table and key in app/config/*.toml is claimed by exactly one settings slice; two slices naming one table, or a table no slice names, fail the check
- [ ] #2 A secret-shaped key (token, password, secret, key, credential segments) in a configuration file fails the check
- [ ] #3 The platform-provided names (ENVIRONMENT, GIT_SHA, FORWARDED_ALLOW_IPS) and the AWS_*, UVICORN_*, OTEL_* namespaces are allow-listed and never claimed by a slice
- [ ] #4 gitleaks runs in CI and fails the build on a detected secret
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

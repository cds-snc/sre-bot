---
id: TASK-111.8
title: Move the security slice onto the files
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-22T13:57:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.5.1
  - TASK-111.16
references:
  - decisions/security.md
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1755
parent_task_id: TASK-111
type: feature
ordinal: 414000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
issuer_config, cors_allowed_origins/methods/headers and dev_bypass_enabled move to [security] in the files (production values from the inventory; production CORS origins are empty today); dev_bypass_token is read as SECURITY__DEV_BYPASS_TOKEN; extra=forbid. Ships and deploys alone because it changes security behaviour inputs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SecuritySettings reads issuer_config, the CORS lists and dev_bypass_enabled from [security]; production resolves the same values as before
- [ ] #2 dev_bypass_token is read only as SECURITY__DEV_BYPASS_TOKEN; base.toml keeps the dev bypass off
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

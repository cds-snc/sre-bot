---
id: TASK-24.6
title: >-
  Check that no env var is read by two settings classes; boot test for a missing
  vendor credential
status: To Do
assignee: []
created_date: '2026-10-19 17:19'
updated_date: '2026-10-19 17:21'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies:
  - TASK-24.1
  - TASK-24.2
  - TASK-24.5
references:
  - decisions/configuration.md
  - decisions/plugins.md
parent_task_id: TASK-24
priority: medium
ordinal: 404000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 6 of TASK-24, its contract. decisions/configuration.md Checks: each key is owned by exactly one settings slice; a vendor slice with a tenant entry missing a secret fails boot naming the key; no <VENDOR>_ENABLED field in integrations/ (SLACK_ENABLED excepted until TASK-112).

- A CI check (app/bin script, run by the CI workflow) collects every BaseSettings subclass under app/ and fails when one environment variable name is read by two classes. TASK-111 extends it to configuration-file keys.
- A boot test extends tests/integration/server/test_lifespan_vendor_slice_validation.py: a missing required vendor credential fails boot with a message naming the variable.
After this slice TASK-24's umbrella ACs are verifiable and TASK-111 can start.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A CI check fails when one environment variable is read by two settings classes, and it passes on main
- [ ] #2 A boot test shows a missing required vendor credential fails with a message naming the variable
- [ ] #3 A grep check finds no <VENDOR>_ENABLED field in app/integrations/ other than SLACK_ENABLED
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

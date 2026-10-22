---
id: TASK-111.5.2
title: Lower-case the server, dev, Slack transport and app identity settings fields
status: To Do
assignee: []
created_date: '2026-10-21T20:23:00Z'
updated_date: '2026-10-22T13:57:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.5.1
  - TASK-111.16
references:
  - decisions/configuration.md
parent_task_id: TASK-111.5
type: feature
ordinal: 426000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mechanical, second of two PRs for TASK-111.5: exactly the host slices TASK-111.7 moves onto the files. The fields of ServerSettings, DevSettings, SlackTransportSettings (COMMAND_PREFIX) and AppSettings (ENVIRONMENT, GIT_SHA, WEBHOOK_MAX_BODY_BYTES) become lower snake_case with case_sensitive=False, and every reader follows, legacy app/modules included (~23 production files of one-token renames). Environment names do not change; differing aliases (SESSION_SECRET_KEY, SLACK__COMMAND_PREFIX) are kept for 111.7 to delete. Log labels such as {"GIT_SHA": ...} in server/lifespan.py stay as they are, and error text keeps the env-var spelling. Waits on TASK-111.16 because ENVIRONMENT is required at boot: this deploy should have the circuit breaker and immutable tags behind it. LoggingSettings is out of scope (done in 111.2).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ServerSettings, DevSettings, SlackTransportSettings and AppSettings declare lower snake_case fields with case_sensitive=False and read the same environment names as before
- [ ] #2 No behaviour change: existing tests pass with attribute renames only; log labels and error-message env names unchanged
- [ ] #3 The production-names pin test gains rows for every environment name of these slices (doc-14 inventory plus ENVIRONMENT, GIT_SHA and the deploy-interface names)
- [ ] #4 No reader in app/, bin/, terraform/ or .github/ uses an old attribute name (rg check recorded in the notes)
- [ ] #5 ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
- [ ] #6 The implementation notes name the previous image tag and digest and cite docs/runbooks/roll-back-a-deployment.md
<!-- AC:END -->

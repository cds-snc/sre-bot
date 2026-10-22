---
id: TASK-111.6.2
title: >-
  Lower-case the AWS, OpenAI, Notify, Trello, OpsGenie, MaxMind and Sentinel
  settings fields
status: To Do
assignee: []
created_date: '2026-10-21T21:01:00Z'
updated_date: '2026-10-21T21:09:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.6.1
references:
  - decisions/configuration.md
parent_task_id: TASK-111.6
ordinal: 428000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Mechanical, second of two PRs for TASK-111.6. AWSSettings, OpenAISettings, NotifySettings, TrelloSettings, OpsGenieSettings, MaxMindSettings and SentinelSettings get case_sensitive=False and lower snake_case fields; every reader follows. Environment names do not change: alias equal to the upper-cased field name dropped, differing aliases kept for 111.11 (AWS, OpenAI) to delete; Notify, Trello, OpsGenie, MaxMind and Sentinel have no aliases (111.12 moves them onto the files). The derived AWSSettings.SERVICE_ROLE_MAP property becomes service_role_map (human decision 2026-10-21, PEP 8: only constants are upper case). Rows for the slices' doc-14 production names are added to the existing pin file. Carries a file-count gate exception approved by the human 2026-10-21 (about 18 reader files plus the one-token service_role_map readers, about 120 production LOC), as 111.5 did.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The seven vendor slices declare lower snake_case fields with case_sensitive=False and read the same environment names as before; only aliases equal to the upper-cased field name are dropped
- [ ] #2 No behaviour change: existing tests pass with attribute renames only
- [ ] #3 test_configuration_settings_production_names.py gains a row for every AWS, OpenAI, Notify, Trello, OpsGenie, MaxMind and Sentinel environment name in doc-14 and the deploy interface, each set to a non-default sentinel that reaches the renamed field
- [ ] #4 No reader in app/, bin/, terraform/ or .github/ uses an old attribute name (rg check recorded in the notes)
- [ ] #5 ruff, mypy (no new errors in touched files), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
- [ ] #6 AWSSettings.SERVICE_ROLE_MAP is renamed service_role_map and every reader follows; the role ARN each service gets is unchanged
<!-- AC:END -->

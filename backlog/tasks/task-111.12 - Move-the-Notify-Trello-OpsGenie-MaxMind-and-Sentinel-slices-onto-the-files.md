---
id: TASK-111.12
title: Move the Notify, Trello, OpsGenie, MaxMind and Sentinel slices onto the files
status: To Do
assignee: []
created_date: 2026-10-20 23:25
updated_date: '2026-10-23T17:10:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.3
  - TASK-111.4
  - TASK-111.6.2
  - TASK-111.16
  - TASK-111.17
references:
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1745
parent_task_id: TASK-111
type: feature
ordinal: 418000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Notify, Trello, OpsGenie, MaxMind and Sentinel slices (integrations/<vendor>/settings.py) move onto the files, one table each ([notify], [trello], [opsgenie], [maxmind], [sentinel]). The fields lose their vendor prefix to match the doc-14 rename map (notify_api_url -> api_url). Non-secret values (Notify API URL, Trello ATIP board, Sentinel customer id and log type) go in production.toml, the MaxMind database path default in base.toml. Credentials are read only under the published SecureString names: NOTIFY__SRE_USER_NAME, NOTIFY__SRE_CLIENT_SECRET, TRELLO__APP_KEY, TRELLO__TOKEN, OPSGENIE__INTEGRATIONS_KEY, SENTINEL__SHARED_KEY (no terraform change). extra=forbid. The unread OPSGENIE_KEY and MAXMIND_KEY names are not migrated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the five slices reads its non-secret values from the files and its credentials from <SLICE>__<FIELD> names
- [ ] #2 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

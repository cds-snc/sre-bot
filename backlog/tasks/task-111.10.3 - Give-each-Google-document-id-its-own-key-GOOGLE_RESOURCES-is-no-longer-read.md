---
id: TASK-111.10.3
title: Give each Google document id its own key; GOOGLE_RESOURCES is no longer read
status: To Do
assignee: []
created_date: '2026-10-26T18:55:00Z'
updated_date: '2026-10-26T21:45:00Z'
labels:
  - configuration
  - security
milestone: m-7
dependencies:
  - TASK-111.10.2
  - TASK-167
references:
  - decisions/configuration.md
parent_task_id: TASK-111.10
type: feature
ordinal: 448000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
GOOGLE_RESOURCES packs the incident, talent, AWS spending and calendar ids into one JSON value, a workaround for the SSM parameter size limit that no longer applies. Each id becomes its own key, never one JSON again. The ids are Drive and calendar item ids: non-public values (decisions/configuration.md, 2026-10-26), never in the public configuration files. Where each id's key lives and how its value is supplied follow TASK-167's ruling on document ids (deployment configuration through the secret pipe, or organisation content with its own source), so the incident, talent and AWS carriers (TASK-145.6, 145.7, 145.10, 145.12, 39, 88) and TASK-158 inherit it without a second move where possible. incident_drive_id and the blob's rep.g are unread and not carried. The GOOGLE_RESOURCES blob line stays for the rollback image until TASK-111.15.2. Plan written after TASK-167 rules. Split from TASK-111.10 on 2026-10-26.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GoogleResourcesConfig (or its replacement per TASK-167) reads one key per id, supplied as TASK-167 rules; GOOGLE_RESOURCES is no longer read; incident_drive_id is deleted and rep.g is not carried
- [ ] #2 No configuration file holds a Drive, document, sheet or calendar id
- [ ] #3 Each production value equals the id in the sre-bot-config GOOGLE_RESOURCES line it replaces (compared without printing it)
- [ ] #4 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
- [ ] #5 /sre incident product list opens a loading modal before the Drive read and fills it with views.update, so a cold Google call no longer outlasts Slack's 3-second trigger_id (expired_trigger_id seen after the 111.10.1 deploy)
<!-- AC:END -->

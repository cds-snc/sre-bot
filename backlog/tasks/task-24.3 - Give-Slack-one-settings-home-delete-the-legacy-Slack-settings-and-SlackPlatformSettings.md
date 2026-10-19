---
id: TASK-24.3
title: >-
  Give Slack one settings home: delete the legacy Slack settings and
  SlackPlatformSettings
status: To Do
assignee: []
created_date: '2026-10-19 17:18'
labels:
  - clients
  - phase-3
  - configuration
milestone: m-3
dependencies: []
references:
  - decisions/configuration.md
parent_task_id: TASK-24
priority: medium
ordinal: 401000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-24. Slack has three settings homes: app/integrations/slack/settings.py (kept), app/infrastructure/configuration/integrations/slack.py (bare names ENABLED, SOCKET_MODE, APP_TOKEN, SLACK_TOKEN; no production consumer) and SlackPlatformSettings in app/infrastructure/configuration/infrastructure/platforms.py (env_prefix SLACK_, reads the same names as the kept slice; no production consumer). Deleting the two dead homes leaves SLACK_ENABLED defined once (the interim transport switch until TASK-112, SLACK_TEAM_ID required when on).

INCIDENT_CHANNEL and SLACK_SECURITY_USER_GROUP_ID stay owned by the incident feature slice (infrastructure/configuration/features/incident.py), which moves with its rebuild.

Independent of Stack K: app/server/configured_systems.py (#1728) reads the kept slice. The Slack tenant entry is TASK-24.5.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/infrastructure/configuration/integrations/slack.py and SlackPlatformSettings are deleted; app/integrations/slack/settings.py is the only Slack vendor slice
- [ ] #2 SLACK_ENABLED, SLACK_SOCKET_MODE, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_SIGNING_SECRET, INCIDENT_CHANNEL and SLACK_SECURITY_USER_GROUP_ID are each read by exactly one settings class
- [ ] #3 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

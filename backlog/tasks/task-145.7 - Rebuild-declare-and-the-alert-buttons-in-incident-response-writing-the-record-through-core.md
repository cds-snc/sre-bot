---
id: TASK-145.7
title: >-
  Rebuild declare and the alert buttons in incident/response, writing the record
  through core
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.6
  - TASK-36.1
parent_task_id: TASK-145
priority: medium
type: feature
ordinal: 357000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer C1 of TASK-145, the first response slice: plugin incident.response. Rebuilds /incident, the declare modal, the locale toggle and the call-incident and ignore-incident buttons shown under alerts (fed into alert channels by product infrastructure or the SIEM through the webhooks pipeline), then cuts them over.

THIS SLICE
- response/entrypoints/slack.py and slack_views.py: the handlers above, each one service call, registered through the Slack registrar; the alert actions register into the webhooks capability's extension point when it exists, otherwise through the registrar with a later move.
- response/service.py declare flow: create the record through IncidentStore with severity and the declarer, create the conversation and set its purpose, create the report from the template and bookmark it, create the video call and bookmark it, create the canvas, bookmark the source alert when present, invite the on-call people (ProductCatalog schedule today; the on-call capability with TASK-146.3) and the configured groups, append the list projection row, post the announcement. Each reference is written to the record as it is created; a failed resource leaves the record with that reference empty and the recreate path (TASK-145.8) fills it.
- The video-call creator moves from features/incident/meet into core/adapters/google_meet.py; meet/ is deleted.
- The product picker reads ProductCatalog and respects Slack option limits.
- Legacy registration of these surfaces is removed from modules/incident in the same PR; names, fields, replies and i18n keys unchanged, pinned by TASK-36.1. Settings values move to the response slice of common/settings.py; environment variable names unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 features/incident/response/ is registered as incident.response and handles /incident, the declare modal, the locale toggle and the alert buttons; the legacy registrations are gone
- [ ] #2 The declare flow writes the record first and every resource reference as it is created; a failing resource is logged and leaves its reference empty without aborting the rest
- [ ] #3 features/incident/meet is deleted and the video-call adapter lives in core/adapters/
- [ ] #4 The pinned declare and alert-button behaviour passes unchanged
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

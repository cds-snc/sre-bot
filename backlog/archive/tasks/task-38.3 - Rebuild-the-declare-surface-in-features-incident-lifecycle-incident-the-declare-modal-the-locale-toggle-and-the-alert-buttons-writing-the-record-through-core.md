---
id: TASK-38.3
title: >-
  Rebuild the declare surface in features/incident/lifecycle: /incident, the
  declare modal, the locale toggle and the alert buttons, writing the record
  through core
status: To Do
assignee: []
created_date: '2026-10-02 16:43'
updated_date: '2026-10-09 17:00'
labels:
  - migration
  - phase-5
  - incident
  - superseded
milestone: m-5
dependencies:
  - TASK-36.1
  - TASK-37
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/migration.md
parent_task_id: TASK-38
priority: medium
ordinal: 308000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
SUPERSEDED (2026-10-09) by TASK-145.6: same slice, re-cut for the response | comms | postmortem subdomains, the interim store in packages/incident and the five roles. This task is kept as history and is not to be planned or implemented.

Slice 3 of TASK-38 (migrate, first lifecycle slice). Rebuilds the /incident command, the incident_view modal, the incident_change_locale action and the call-incident / ignore-incident alert buttons as features/incident/lifecycle/ (entry point incident.lifecycle), and cuts them over.

THIS SLICE
- lifecycle/entrypoints/slack.py: the handlers above, each one service call, registered through the Slack registrar contract; the alert actions are registered into the webhooks capability's extension point.
- lifecycle/service.py declare flow, in order: create the record through IncidentStore (the app id is the key), create the conversation and set its purpose, create the report from the template and bookmark it, create the video call and bookmark it, create the canvas, bookmark the source alert when present, invite on-call people (ProductCatalog schedule), the security group and the Notify management group under today's conditions, append the list projection row, post the announcement. Each resource reference is written to the record as it is created; a failed resource leaves the record with that reference empty and the failure reported, never a missing record.
- lifecycle/adapters/: the video-call creator (Google Meet, absorbing packages/incident/meet, which is deleted).
- The product picker reads ProductCatalog and paginates or filters within Slack limits (closes the TASK-81 shim for this surface; TASK-38 AC #13).
- The new-incident system policy setting (common/settings.py) selects the tenant for the report and the video call.
- Legacy registration of these surfaces is removed from modules/incident and the hard-coded list in the same PR; command names, modal fields, replies and i18n keys are unchanged, pinned by TASK-36.1.
- Settings: the lifecycle settings slice lives under features/incident/common/settings.py with values in the TOML files; environment variable names unchanged.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /incident, incident_view, incident_change_locale, call-incident and ignore-incident are handled by features/incident/lifecycle with one service call per handler; their legacy registrations are removed in the same PR
- [ ] #2 A declared incident exists in IncidentStore before any workplace resource is created, and each created resource is stored as a reference with system, tenant and id; a resource failure is reported and leaves the record with that reference empty
- [ ] #3 The product picker never truncates: long product lists paginate or filter within Slack block and option limits
- [ ] #4 packages/incident/meet no longer exists; the video-call adapter lives in lifecycle/adapters/ and returns a VideoCallReference
- [ ] #5 The TASK-36.1 pinning tests for these surfaces are green before and after the cutover with no assertion change; EN and FR replies unchanged
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; no baseline grew; import-linter ignore entries only shrank
<!-- AC:END -->

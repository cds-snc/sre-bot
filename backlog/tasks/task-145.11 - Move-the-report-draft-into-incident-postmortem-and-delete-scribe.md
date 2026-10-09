---
id: TASK-145.11
title: Move the report draft into incident/postmortem and delete scribe
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.10
  - TASK-145.9
parent_task_id: TASK-145
priority: medium
type: task
ordinal: 361000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer D2 of TASK-145. Mechanical move: /sre incident draft becomes a postmortem use case and features/incident/scribe is deleted.

THIS SLICE
- scribe/service.py's draft path becomes postmortem/report.py (fill the report for review) with postmortem/prompt.py (section prompts and metadata rules), the draft settings slice, the incident_draft catalogue and the IncidentDocumentStore use through core's IncidentReport. The command registers under incident.postmortem. It calls the Summarizer directly until TASK-25.10; TASK-134 then moves the generic answer parsing to the capability from here.
- Tests renamed test_incident_postmortem_report_*; mock patch strings rewritten.
- features/incident/scribe/ is deleted: entry point "incident.scribe" removed from pyproject, the integrations.openai ignore entry renamed to the module that now imports it (one entry, not two), the umbrella layers contract lists response | comms | postmortem above core above common, the umbrella README loses the scribe section.
- The report draft is also offered when the status reaches Ready to be Reviewed: response raises the transition through an extension point in common/ and postmortem registers the reaction at startup; no subdomain imports the other. Omit this bullet if it pushes the slice over the size gate and open a follow-up.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /sre incident draft is handled by postmortem/report.py; features/incident/scribe no longer exists and incident.scribe is not an entry point
- [ ] #2 The umbrella layers contract is response | comms | postmortem above core above common with exhaustive = true
- [ ] #3 The import-linter ignore list has not grown; every renamed entry maps to an existing module
- [ ] #4 The draft command's behaviour and output are unchanged (existing tests pass under their new names)
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

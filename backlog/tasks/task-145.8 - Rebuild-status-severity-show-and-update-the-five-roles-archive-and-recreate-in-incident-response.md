---
id: TASK-145.8
title: >-
  Rebuild status, severity, show and update, the five roles, archive and
  recreate in incident/response
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.7
parent_task_id: TASK-145
priority: medium
type: feature
ordinal: 358000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer C2 of TASK-145. Rebuilds the /sre incident subcommands and interactions that read and change an incident: status, the information display and update modals, roles, the folder-metadata interactions over ProductCatalog, archive, the confirm step and the recreate-missing-resources path.

RULES
- Every command resolves its incident through find_incident_for_conversation; only operations that write to the conversation call conversation_is_writable. A status, severity, timing or report update on an incident whose channel is archived succeeds and reports that the channel message was skipped.
- Status change fans out from the record: atomic field update, then the report's status text, then the list projection (write-only), then the channel message when writable.
- Severity is set at declare and changed from the update modal; it is a record field, never read from a document.
- The five roles (incident commander, operations lead, communications lead, policy lead, postmortem owner) are stored on the record and shown in the show modal; the report's Drive properties are no longer written. The roles command offers all five; only IC and OL are required.
- The show modal renders every link from the record's references through the owning adapter.
- Legacy registrations removed in the same PR; names, fields and replies unchanged apart from the three added role pickers, pinned by TASK-36.1.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every rebuilt command and interaction resolves its incident through find_incident_for_conversation; a write to an archived channel is skipped and reported, not failed
- [ ] #2 Severity and the five roles are read from and written to the record; no code path writes Drive properties for roles
- [ ] #3 Status change updates the record, the report text, the projection and the channel in that order, each failure logged and the rest continuing
- [ ] #4 The pinned behaviour of status, show, update, roles and archive passes unchanged
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

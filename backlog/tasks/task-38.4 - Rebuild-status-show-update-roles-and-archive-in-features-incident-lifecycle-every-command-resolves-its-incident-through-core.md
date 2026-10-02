---
id: TASK-38.4
title: >-
  Rebuild status, show, update, roles and archive in
  features/incident/lifecycle; every command resolves its incident through core
status: To Do
assignee: []
created_date: '2026-10-02 16:43'
labels:
  - migration
  - phase-5
  - incident
milestone: m-5
dependencies:
  - TASK-38.3
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/migration.md
parent_task_id: TASK-38
priority: medium
ordinal: 309000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-38 (migrate, second lifecycle slice). Rebuilds the /sre incident subcommands and interactions that read and change an incident: status updates (incident_status), the information display and update modals (information_display, information_update, update_incident_field, update_field_modal, incident_updates_view), roles (view_save_incident_roles, user_select_action), the folder-metadata interactions (add_folder_metadata, view_folder_metadata, view_folder_metadata_modal, add_metadata_view, delete_folder_metadata) over ProductCatalog, archive_channel, confirm_click, and the recreate-missing-resources path.

RULES
- Every command resolves its incident through find_incident_for_conversation; only operations that write to the conversation call conversation_is_writable. A status, severity, timing or report update on an incident whose channel is archived succeeds and reports that the channel message was skipped.
- Status change fans out from the record: IncidentStore atomic field update, then IncidentReport status text, then the list projection (status column), then the channel message when writable. The projection is write-only: nothing is read back from the sheet (closes TASK-73 on this path).
- Roles are stored on the record (incident commander, operations lead), no longer in the report's Drive properties; the channel purpose footer is kept.
- The show modal renders every link from the record's references through the owning adapter.
- Legacy registrations removed in the same PR; command names, modal fields and replies unchanged, pinned by TASK-36.1.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every rebuilt command resolves its incident through find_incident_for_conversation; conversation_is_writable is called only before a channel write; no handler or service re-implements the lookup
- [ ] #2 A status update on an incident whose channel is archived updates the record, the report and the projection and reports the skipped channel message
- [ ] #3 Roles are read from and written to the record; the report's Drive properties are no longer read for roles
- [ ] #4 The list projection is written and never read in this slice; the status column update uses the record's conversation reference, so the modal path and the command path write the same row
- [ ] #5 The TASK-36.1 pinning tests for these interactions are green before and after the cutover with no assertion change; legacy registrations are removed in the same PR
- [ ] #6 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; no baseline grew
<!-- AC:END -->

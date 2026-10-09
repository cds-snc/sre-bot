---
id: TASK-145.8
title: >-
  Rebuild status, severity, show and update, the five roles, archive and
  recreate in incident/response
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 18:22'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline plan grounded at main d2d973ae (2026-10-09) against the legacy module; re-ground at pickup (after TASK-145.7). SIZE GATE: proposed split into TASK-145.8.1 (status, severity, show and update fields; IncidentStore.update_field) and TASK-145.8.2 (five roles, archive and confirm, folder metadata, recreate missing resources, list), human decision before implementation.

## Discovered state
- modules/incident/incident_helper.py (720): /sre incident dispatcher handle_incident_command (198-437: help, create, close, show, list, schedule, channels, products, status, roles, updates pointer); registrations 151-167 (add_folder_metadata, view_folder_metadata, view_folder_metadata_modal, add_metadata_view, delete_folder_metadata, view_save_incident_roles, view_save_event, confirm_click, user_select_action, archive_channel, reactions, update_incident_field, update_field_modal); modules/sre/platforms/slack.py:16 routes /sre incident to it. incident_status.py (81): update_status, posts to channel (70). information_display.py (183): incident_information_view modal. information_update.py (330): update_field_modal and field views, posts (50, 264). incident_roles.py (145): save_incident_roles, Drive metadata ic_id/ol_id (20-21), posts (13). incident_conversation.archive_channel_action (433). incident_folder.py: metadata and sheet status update (314-328). db_operations.update_incident_field (121, list_append for activities). tests/modules/incident/test_recreate_missing_resources.py covers the recreate path.
- scribe registers its /sre incident subcommands under parent "sre.incident" through the registrar: response does the same, so the legacy dispatcher loses subcommands one by one.

## Steps
1. core/store.py: update_field(incident_id, field, value, *, expected=None) atomic, no read-modify-write; fake.
2. response/service.py: set_status (record, report status text, projection status cell, channel post when writable), set_severity, update_field (timing fields and text), show (every link rendered from references through the owning adapter), set_roles (five roles on the record; channel purpose footer kept; Drive properties no longer written), archive (writability check, archive through IncidentConversation, record status), recreate_missing_resources (fill empty references through the declare steps), list (store).
3. response/entrypoints: the subcommands status, show, roles, list, archive, products, channels under sre.incident; the information modal, update-field modal, roles modal (five pickers, IC and OL required), folder-metadata interactions, confirm_click; each one service call. Views in slack_views.py; keys in locales.
4. Legacy: the matching subcommands and registrations removed from incident_helper.py, incident_status.py, information_display.py, information_update.py, incident_roles.py in the same PR; pinned by TASK-36.1. modules/sre keeps routing only what remains.

## AC traceability
AC1: step 2 -> service tests with an archived conversation (write skipped and reported). AC2: steps 1-2 -> store update_field test; roles tests assert no Drive metadata call. AC3: step 2 -> fan-out order test with failing report/projection/channel stubs. AC4: pinned surfaces. AC5: gates.

## Test matrix
Status change: each fan-out step failing independently; archived channel. Severity set and shown. Roles: five set, IC/OL required, metadata adapter never called. Archive: not writable -> refusal; success. Recreate: each missing reference recreated once. List: active and stale.

## Assumptions and doubts
- The five-role picker is the only visible change; the handbook-style names come from common/vocabulary.
- Folder metadata stays a ProductCatalog concern through the Drive adapter until products become records (DRAFT-2).

## Size
Over the gate as one task (~800 lines); each half about 400.

## Blast radius and rollback
Each subcommand's legacy registration is removed with its rebuild; a revert restores it. Status fan-out is the riskiest path: it writes four systems.
<!-- SECTION:PLAN:END -->

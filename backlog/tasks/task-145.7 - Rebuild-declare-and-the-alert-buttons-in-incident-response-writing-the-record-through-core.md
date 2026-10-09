---
id: TASK-145.7
title: >-
  Rebuild declare and the alert buttons in incident/response, writing the record
  through core
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 19:36'
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
- The product picker reads ProductCatalog and respects Slack option limits. The severity picker offers none and SEV0 to SEV4 from common/vocabulary: SEV0 is the only new option, and the announcement's severity warning covers it as it covers SEV1 to SEV4.
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Outline plan grounded at main d2d973ae (2026-10-09) against the legacy module; re-ground at pickup (after TASK-36.1 pinning and TASK-145.6). SIZE GATE: the declare flow creates ten resources; proposed split into TASK-145.7.1 (modal, record, conversation, report, announcement, locale toggle) and TASK-145.7.2 (video call, canvas, bookmarks, invites including on-call, list projection row, alert buttons), human decision before implementation.

## Discovered state
- modules/incident/incident.py (481): /incident command (38), incident_view submission (39), incident_change_locale (40); i18n through python-i18n with app/locales/incident.{en-US,fr-FR}.yml (keys incident.modal.*, incident.submit, incident.locale_button). core.py (617): the creation workflow (channel, document from template, meet, bookmarks, canvas at 464, invites, list row, announcement). incident_alert.py (105): handle_incident_action_buttons (52) with call-incident (opens the declare modal) and ignore-incident (posts to the channel). on_call.py (41): get_on_call_users_from_folder over integrations.opsgenie. db_operations.create_incident (53) writes the item.
- Pinning: not yet for the declare modal and the alert buttons (TASK-36.1).
- After TASK-145.5 and TASK-145.6: IncidentStore read path, IncidentConversation, IncidentReport, ProductCatalog exist; IncidentStore.create arrives here.

## Steps
1. core/store.py: create(incident) with a conditional put on the id; adapter writes today's item shape (so the legacy module keeps reading it) plus the new fields; fake.
2. features/incident/response/: __init__.py (hookimpls register_slack_commands, register_i18n_resources), settings.py (slice of common settings: template id, folders, groups to invite, announcement channel), service.py declare(...) orchestrating in the order the coordinator fixes: record, conversation and purpose, report and bookmark, video call and bookmark, canvas, source-alert bookmark, invites (on-call through ProductCatalog's schedule reference and an interim core/adapters/opsgenie.py until TASK-146.3), groups, projection row, announcement; each reference written to the record as created; failures logged and left empty.
3. response/entrypoints/slack.py: /incident command and the declare modal submission, the locale toggle, the two alert buttons registered through the Slack registrar (or the webhooks extension point when it exists); one service call each. slack_views.py: the modal (product picker from ProductCatalog, severity picker from Severity, security flag), the announcement blocks. locales/incident_response.*.yml copying the keys the declare surface uses from app/locales/incident.*.yml.
4. meet/adapters/google_meet.py moves to core/adapters/google_meet.py behind a VideoCall interface; meet/ deleted.
5. Legacy registration of /incident, incident_view, incident_change_locale and handle_incident_action_buttons removed from modules/incident/incident.py and incident_alert.py in the same PR; names, fields, replies and keys unchanged (pinned).

## AC traceability
AC1: steps 2-3, 5 -> registration test, pinned declare and alert tests. AC2: step 2 -> declare service tests with fakes for every resource (record first, partial failures). AC3: step 4 -> `rg -l meet features/incident` shows core only. AC4: pinned surfaces green. AC5: gates.

## Test matrix
Declare: full success writes every reference; conversation creation failure aborts after the record exists and reports; report, video call, canvas, invite and projection failures each leave their reference empty and continue; security flag yes/no/unknown stored; severity stored; product without schedule invites nobody. Alert buttons: call-incident opens the modal with the source alert reference; ignore posts. Locale toggle re-renders.

## Assumptions and doubts
- The webhooks capability's extension point (TASK-37) may not exist; the coordinator's assumption registers through the Slack registrar and moves later.
- The projection row keeps using the legacy sheet writer until TASK-145.12; it is called through a narrow interface so the swap is one adapter.
- Re-ground the legacy declare flow's exact order and the group ids from core.py before writing the service.

## Size
Over the gate as one task (~700 lines); each proposed half about 350.

## Blast radius and rollback
Declare is the most-used surface; the legacy path is removed in the same PR, so a revert restores it. Deploy in a quiet window.
<!-- SECTION:PLAN:END -->

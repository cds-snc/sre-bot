---
id: TASK-145.8.5.3
title: >-
  Cut over archive and /sre incident close through one response service;
  close_incident and incident_status.py deleted
status: To Do
assignee: []
created_date: '2026-11-16T19:34:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.8.4
  - TASK-145.8.5.1
  - TASK-145.8.5.2
references:
  - decisions/incident-management.md
  - decisions/observability.md
  - decisions/migration.md
parent_task_id: TASK-145.8.5
priority: medium
type: feature
ordinal: 525000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L7a.3 (doc-11 row 18.L7a.3), stacked above L7a.1. Split from TASK-145.8.5 on 2026-11-16 (human, OQ1). response/service/archive.py archive_incident: find the incident (refusal decided by the record), join the channel, close through change_status (record first, report, list, channel notice), post the archived notice, archive, then one incident_channel_archived event with a minimal payload {incident_id, conversation_id, user_id, at} (OQ8). Serves the rebuilt `/sre incident close` and the stale notice's archive button (incident.response.archive with the archive_channel alias scoped to the archive value, TASK-145.8.5.2); ignore stays legacy until TASK-145.9.2, schedule_retro until TASK-145.10. Plan in full at pickup.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 archive_incident in incident.response: find (store down or not an incident: refusal, nothing written, no event), join, change_status(Closed) (a record failure stops it), archived notice, archive, then exactly one incident_channel_archived event with {incident_id, conversation_id, user_id, at} after a successful archive, sent through a response adapter tagged TODO(TASK-122)
- [ ] #2 The archive button is incident.response.archive with the archive_channel alias scoped to the archive value; /sre incident close is registered by incident.response on the same service (pinned first); close_incident, handle_close, its dispatcher entry, incident_status.py and test_incident_status.py are deleted; ignore and schedule_retro stay on the legacy listener
- [ ] #3 IncidentConversation gains async join (Slack conversations.join, already a member is success) on the adapter and the fake, held to the parity suite; incident-management.md (join is a write step, never the writability check) and observability.md (rebuilt surfaces send named events with minimal fields, never request bodies) carry dated Changes lines
- [ ] #4 The archive pins pass with fixtures rewired; the refusal pin presses in a channel with no record, citing the ruling (kind b); the double event and the event on a refusal are pinned as test_legacy_only_* and deleted (kind a); new tests assert one event and none on refusal; update_incident_document_status's owner note names TASK-145.8.3
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams, make check-settings-key-ownership and pytest tests --ignore=tests/smoke pass
- [ ] #6 The PR body lists each named change with its kind (Sentinel once and none on refusal: a; refusal by record, record failure stops, minimal event payload: b), the revert target (one git revert; the L5r guard) and the merge order (after L6b)
<!-- AC:END -->

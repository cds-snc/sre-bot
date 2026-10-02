---
id: DRAFT-5
title: Receive external-case events through the webhooks capability as re-read hints
status: Draft
assignee: []
created_date: '2026-10-02 16:44'
labels:
  - incident
  - later-wave
dependencies:
  - TASK-37
references:
  - decisions/incident-management.md
  - decisions/webhooks.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2; after the DFIR-IRIS adapter draft). DFIR-IRIS's native webhooks module posts on case, note, task and event hooks with undocumented auth and retry behaviour. This task registers an incident handler into the webhooks capability for those posts: it authenticates the delivery the way the capability prescribes, treats the payload as a hint (the external case id only), re-reads the case through ExternalCaseRecorder, and updates the record through IncidentStore. It never writes state from the payload. No polling is built.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The handler is registered into the webhooks capability's extension point by features/incident and verifies the delivery before acting
- [ ] #2 State changes come from a re-read through ExternalCaseRecorder, never from the webhook payload; a forged or replayed delivery changes nothing (test)
- [ ] #3 The handler is idempotent under redelivery through the coordination contract
<!-- AC:END -->

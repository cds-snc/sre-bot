---
id: TASK-145.7.9
title: >-
  Declare service in incident.response, unregistered, with the on-call invite
  through the capability
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-10T16:16:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.2
  - TASK-145.7.5
  - TASK-145.7.6
  - TASK-145.12.1
  - TASK-145.7.7
  - TASK-146.1
references:
  - decisions/incident-management.md
  - decisions/oncall.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 513000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L9a (approved program in TASK-145.7's plan, section 2; outline in the parent plan). response/service/declare.py orchestrates the declare flow over the core Protocols (TASK-145.7 plan section 6), including TASK-146.3: invites through capabilities.oncall.api with a ScheduleSource port whose interim adapter reads the placement folder's genie_schedule through the Drive gateway (read only, tolerated with owner TASK-165.1), and the Notify management invite triggered by [incident_response] notify_management_placement_id (tolerated, owner TASK-165.1). Unregistered.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Declare writes the record first (IncidentStore.create, the id derived from the declare's idempotency key), then creates the conversation and attaches it (attach_conversation), then the resources; full success writes every reference; a failing conversation leaves an open incident with no surface, reported and retriable, never rolled back; each later failure leaves its reference empty and continues; on-call people, the security group and the Notify management group are invited per the rules (tested; checks parent ACs #2, #14 and TASK-146.3's ACs)
- [ ] #2 decisions/incident-management.md lists the schedule-source adapter and the Notify trigger key as tolerated with owner TASK-165.1; no umbrella module imports integrations.opsgenie
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
- [ ] #4 The HTTP declare route POST /incidents runs the declare service (rides here per the TASK-145.7.7 ruling R6, 2026-11-10): Idempotency-Key required and mapped to the incident id, one router tag, explicit non-2xx mapping, declared permission (authorization.md); success and error-mapping tests; whether it registers here or with the 145.7.10 cutover is decided in this task's full plan
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10 (TASK-145.7.7 rulings R4-R6, decisions/incident-management.md Bindings): business features are API first; bindings are chat conversations only, zero or more per incident; declare writes the record first, then the conversation and attach_conversation, then resources, each a retriable step whose failure is reported (timeline entry once TASK-145.9) and never rolled back; the incident id is derived from the declare's idempotency key (uuid5 of the Slack request or alert id; the HTTP Idempotency-Key) so a retry reuses it and the orphan-incident residual stays theoretical; the HTTP declare route is folded in here (AC #4). Supersedes the plan's OQ9 'declare unavailable only when no working surface can be bound' and AC #1's 'a failing conversation writes nothing'. Full plan: check the size gate with the route included.
<!-- SECTION:NOTES:END -->

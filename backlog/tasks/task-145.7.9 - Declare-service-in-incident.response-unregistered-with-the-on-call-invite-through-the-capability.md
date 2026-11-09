---
id: TASK-145.7.9
title: >-
  Declare service in incident.response, unregistered, with the on-call invite
  through the capability
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
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
- [ ] #1 Full success writes every reference; a failing conversation writes nothing; each later failure leaves its reference empty and continues; on-call people, the security group and the Notify management group are invited per the rules (tested; checks parent ACs #2, #14 and TASK-146.3's ACs)
- [ ] #2 decisions/incident-management.md lists the schedule-source adapter and the Notify trigger key as tolerated with owner TASK-165.1; no umbrella module imports integrations.opsgenie
- [ ] #3 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

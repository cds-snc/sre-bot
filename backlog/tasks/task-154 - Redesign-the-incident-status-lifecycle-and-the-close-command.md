---
id: TASK-154
title: Redesign the incident status lifecycle and the close command
status: To Do
assignee: []
created_date: '2026-10-15 18:09'
updated_date: '2026-10-15 18:25'
labels:
  - incident
dependencies:
  - TASK-145.8
references:
  - 'https://github.com/cds-snc/sre-bot/issues/1720'
priority: medium
ordinal: 395000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Today `/sre incident close` closes all the incident's resources and archives the channel, which is not the wanted future behaviour, and the five statuses are confusing to responders. TASK-145.8 rebuilds status and close at parity; this task redesigns them afterwards.

SCOPE
- Decide the lifecycle states and the allowed transitions, and what close does (and does not do) to the channel and the other resources.
- Amend decisions/incident-management.md with the decision.
- Any data migration of stored status values follows the shared legacy backfill rule set in decisions/incident-management.md (Migration): runner pattern as TASK-145.5.7, a shared pure upgrade function, the record_version marker.

Standalone rather than a TASK-145 subtask: TASK-145 rebuilds legacy surfaces at parity, and this is new behaviour.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The lifecycle states, transitions and the behaviour of close are decided and recorded in a dated amendment to decisions/incident-management.md
- [ ] #2 Follow-up implementation tasks exist for the decided lifecycle, including any status data migration under the shared backfill rule set
<!-- AC:END -->

---
id: TASK-38.5
title: >-
  Rebuild timeline capture and the stale-channel nudge job in
  features/incident/lifecycle; incident leaves the provisional aws_platform
  DynamoDB adapter
status: To Do
assignee: []
created_date: '2026-10-02 16:43'
labels:
  - migration
  - phase-5
  - incident
milestone: m-5
dependencies:
  - TASK-38.4
  - TASK-36.3
  - TASK-64
references:
  - decisions/incident-management.md
  - decisions/feature-packages.md
  - decisions/migration.md
  - decisions/reliability.md
parent_task_id: TASK-38
priority: medium
ordinal: 310000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 of TASK-38 (migrate, third lifecycle slice). Rebuilds the floppy-disk reaction_added and reaction_removed handlers (message captured into the report's timeline and into the record's timeline entries; removal deletes both), the ack-only reaction fallbacks, and the notify_stale_incident_channels job, then deletes modules/incident/db_operations.py.

JOB: registered by lifecycle through the register_background_jobs hookimpl with its schedule, Tier-2 classification and lease TTL from the lifecycle settings slice (reliability.md, the TASK-65 pattern); the hand-import in app/jobs/scheduled_tasks.py is deleted. Stale detection reads the store (incidents with no timeline entry or status change for the configured window), not a channel-name regex; the nudge message carries the archive action id and the schedule-retro action id from common/vocabulary. Safe to run twice.

EXIT FROM aws_platform: after this slice no module under app/modules/incident imports db_operations or packages.aws_platform; the seam baseline entries for incident are removed, which is the condition TASK-88 needs to dissolve packages/aws_platform.

Legacy registrations and the job hand-import are removed in the same PR; pinned by TASK-36.1 (reactions) and TASK-36.3 (job).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 reaction_added and reaction_removed with the floppy-disk emoji write and delete a timeline entry on the record and the matching entry in the report; both are handled by features/incident/lifecycle
- [ ] #2 notify_stale_incident_channels is registered by a lifecycle register_background_jobs hookimpl with Tier-2 lease and TTL from the lifecycle settings slice; the hand-import in app/jobs/scheduled_tasks.py is gone; running the job twice in one window posts one nudge per incident
- [ ] #3 modules/incident/db_operations.py is deleted; no module under app/modules/incident imports packages.aws_platform; the aws_platform seam baseline has no incident entry
- [ ] #4 The TASK-36.1 and TASK-36.3 pinning tests for these surfaces are green before and after the cutover with no assertion change
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass; no baseline grew; the seam baseline only shrank
<!-- AC:END -->

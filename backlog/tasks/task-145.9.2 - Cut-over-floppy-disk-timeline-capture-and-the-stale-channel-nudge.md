---
id: TASK-145.9.2
title: Cut over floppy-disk timeline capture and the stale-channel nudge
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
updated_date: '2026-11-16T15:51:00Z'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.9.1
  - TASK-145.8.1
  - TASK-145.8.5
  - TASK-145.7.10
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.9
priority: medium
type: feature
ordinal: 517000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L10b. Reaction handlers registered by incident.response write timeline records through TASK-145.8's timeline store and report entries through L10a; the stale nudge registered by response's background-job hookimpl, posting the prefixed archive id; jobs/scheduled_tasks.py no longer imports it; incident_document.py deleted when no caller remains; the 36.1.5 pins rewired.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The capture and nudge pins pass with assertions unchanged; captured entries keep the same key on re-capture (checks parent ACs #1, #2, #5, #7, #8)
- [ ] #2 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-10: captured_entry_id is built here (uuid5 under TIMELINE_NAMESPACE in core/adapters/timeline_items.py from TASK-145.8.1); captured entries are TimelineEntry kind message with source_message, appended through TimelineStore.append.

2026-11-10 (TASK-145.8.7 planning): TimelineStore stays sync after TASK-145.8.7 because only the store bodies call it; when this task (or 145.9.1) gives it an async consumer, it becomes async def with its Record adapter offloading (decisions/outbound-clients.md async-port rule).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-16T15:51:00Z

---

2026-11-16 (human, TASK-145.8.4 OQ4): decisions/migration.md step 4 amended (rides with L6b): a cutover changes behaviour only as a named change of kind (a) legacy bug no pin asserts, (b) behaviour an accepted end-state ADR replaces, (c) expired deprecated form after a usage check, (d) retired surface; additions only by an explicit plan ruling. At planning, classify each behaviour change of this task by kind, pin it (test_legacy_only_* or edited pin citing the ruling) and list it in the PR body.

---
<!-- COMMENTS:END -->

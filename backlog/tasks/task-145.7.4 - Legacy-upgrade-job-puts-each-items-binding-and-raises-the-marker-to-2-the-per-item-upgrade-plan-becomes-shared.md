---
id: TASK-145.7.4
title: >-
  Legacy upgrade job puts each item's binding and raises the marker to 2; the
  per-item upgrade plan becomes shared
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.3
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 501000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L2b (approved program in TASK-145.7's plan, section 2; outline in the parent plan). core/legacy_upgrade.py: plan_item_upgrade becomes a public core function used by the job and by TASK-145.8's upgrade-on-write; END_STATE_VERSION 1 and RECORD_VERSION 2 in core/store.py; the job puts the binding (deterministic, from the conversation map, verified tenant) then raises the marker in one guarded update; report counts bindings_put, bindings_existing, marker_raised, binding_skipped. features/incident/README.md run procedure lists every legacy writer (legacy declare, recreate, modules/dev/incident.py:104, the sheet import) and the rerun rule. The job stays off in production.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A legacy item reaches marker 2 with its binding in one pass; a rerun changes nothing; a crash between the binding put and the update converges on rerun; an open item without a conversation fails the run before any write; a Closed one is only raised; dry run writes nothing (tested)
- [ ] #2 The README names every legacy writer and the rerun after the last one (Migration rule 6)
- [ ] #3 Checks the job part of parent AC #13
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

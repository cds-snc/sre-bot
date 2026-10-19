---
id: TASK-145.5.10
title: >-
  IncidentStore builder: the store from a resolved RecordStore, the incident
  core settings and the configured tenants
status: To Do
assignee: []
created_date: '2026-10-19 15:25'
labels:
  - incident
  - features
dependencies:
  - TASK-145.5.9
  - TASK-145.5.8
references:
  - decisions/incident-management.md
  - decisions/dependency-injection.md
  - decisions/workplace-systems.md
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 400000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 8 of Stack K (handoff doc-13), split out of TASK-145.5.5 (human, 2026-10-19). Added beside the legacy lookup and unused until the TASK-145.5.5 cutover, so no behaviour change.

THIS SLICE
- core/api.py: a builder that takes a resolved RecordStore and the configured-systems read (TASK-145.5.9) and returns the IncidentStore: incidents_table from the incident core settings table name, and the tenants mapping (system to tenant id) for the legacy item bridge (TASK-145.5.8) taken from the read. A plain function the entry point calls inside its service scope; no lru_cache provider (decisions/dependency-injection.md).
- The builder does not read the new-incident policy (human, 2026-10-19): the policy is resolved only on the path that creates a new incident (TASK-145.7), so lookups and updates of existing incidents never depend on it.
- A legacy item without record_version reads through the bridge with the configured tenants, tested end to end over the in-memory RecordStore.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 core/api.py builds the IncidentStore from a resolved RecordStore, the incident core table name and the tenants mapping taken from the configured-systems read; no lru_cache provider
- [ ] #2 The builder does not read INCIDENT_CORE__NEW_INCIDENT_SYSTEM
- [ ] #3 A legacy item without record_version reads through the bridge with the configured tenants, tested end to end over the in-memory RecordStore; a system missing from the read leaves its tenant out of the mapping (tested)
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

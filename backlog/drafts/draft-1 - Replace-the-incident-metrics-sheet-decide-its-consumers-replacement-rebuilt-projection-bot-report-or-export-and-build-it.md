---
id: DRAFT-1
title: >-
  Replace the incident metrics sheet: decide its consumers' replacement (rebuilt
  projection, bot report or export) and build it
status: Draft
assignee: []
created_date: '2026-10-02 16:44'
updated_date: '2026-10-09 17:14'
labels:
  - incident
  - later-wave
dependencies:
  - TASK-145.12
references:
  - decisions/incident-management.md
  - decisions/workplace-systems.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2 is finished; not before). decisions/incident-management.md keeps the incident list sheet as a write-only projection through the migration (TASK-145.11). This task decides and builds what the sheet's consumers get in the end state.

OPEN QUESTION FOR THE HUMAN before planning: who reads the sheet today (SRE leads, management, the GC Notify team, an audit function), how often and for what (counts by status and product, time to resolve, yearly roll-ups), and whether history must be backfilled into app storage or the old sheet stays a read-only archive. The answer picks among: keep the rebuilt projection; a /sre incident report command or scheduled channel post from the store; a periodic export. Whatever is chosen reads IncidentStore only.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The consumers of the incident metrics sheet and their needs are recorded on this task from the human answer before any build
- [ ] #2 The replacement reads IncidentStore only; if a sheet survives it is regenerated from the store and never read
- [ ] #3 EN and FR output; no vendor URL built by string formatting
<!-- AC:END -->

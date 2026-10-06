---
id: DRAFT-10
title: >-
  Per-product status-update profiles and status-page adapters for external
  incident status updates
status: Draft
assignee: []
created_date: '2026-10-06 19:05'
labels:
  - incident
  - later-wave
dependencies:
  - TASK-140
references:
  - decisions/incident-management.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after TASK-140). TASK-140 ships one default comms profile modelled on GC Notify's published incident history and a copy-ready StatusPagePublisher adapter in features/incident/scribe (decisions/incident-management.md, External status updates). This task lets each product (keyed by its ProductCatalog entry) carry its own profile: stage labels, public service names, layout, time format and publish target, so teams such as GC Notify and GC Sign In keep their current communication patterns. Profiles change rendering only, never the drafting prompt. Status-page publishing (for example GC Notify's GC Articles incident page) is one StatusPagePublisher adapter per target.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A product with a profile renders its approved updates with that profile; a product without one uses the default
- [ ] #2 Changing a profile changes no prompt and no stored StatusUpdate field
- [ ] #3 At least one status-page adapter publishes behind StatusPagePublisher, selected by the product's profile
<!-- AC:END -->

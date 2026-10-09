---
id: DRAFT-2
title: >-
  Products as app records: replace Drive folder metadata with a ProductCatalog
  store (product, on-call schedule, metadata)
status: Draft
assignee: []
created_date: '2026-10-02 16:44'
updated_date: '2026-10-09 17:14'
labels:
  - incident
  - later-wave
dependencies:
  - TASK-145.13
references:
  - decisions/incident-management.md
parent_task_id: TASK-97
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
EXPANSION (after doc-2). During the migration ProductCatalog (features/incident/core/api.py) is backed by Google Drive folders and their appProperties (TASK-145.5). This task gives it an app-storage implementation through the storage contract: products with their on-call schedule reference and metadata, administered through the existing folder-metadata interactions renamed to products, and the Drive-folders adapter is deleted. The product folder in Drive, if kept, becomes a collaboration space the product record references (workplace-systems.md rule 5).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ProductCatalog is implemented over the storage contract with an in-memory fake; the Drive-folders adapter is deleted
- [ ] #2 The declare modal and the on-call lookup read the product record; existing products are migrated by a one-shot idempotent job with a dry run
- [ ] #3 The metadata interactions keep their action ids and replies, pinned by the legacy_surface suite
<!-- AC:END -->

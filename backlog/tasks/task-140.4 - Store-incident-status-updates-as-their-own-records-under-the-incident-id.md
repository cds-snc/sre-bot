---
id: TASK-140.4
title: Store incident status updates as their own records under the incident id
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
updated_date: '2026-10-07 13:28'
labels:
  - incident
dependencies:
  - TASK-140.1
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 323000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
A frozen StatusUpdate record (incident id, sequence, state draft/approved/published, stage, EN and FR fields, author, approver, transcript cutoff, transcript fingerprint, timestamps) and a StatusUpdateStore interface in core/api.py, with an adapter over the StorageService contract (pattern: packages/access/sync/job_status_store.py). New DynamoDB table sre_bot_incident_status_updates in terraform/dynamodb.tf, PK INCIDENT#<uuid>, SK UPDATE#<iso timestamp>#<n>, like sre_bot_access_requests. Appends are conditional puts, never read-modify-write or list-append.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Terraform declares sre_bot_incident_status_updates with PK/SK string keys
- [ ] #2 The store appends with a conditional put and lists an incident's updates newest first; the latest update is one query
- [ ] #3 Records never touch the legacy incidents item or its incident_updates attribute
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Ordering: the sre_bot_incident_status_updates table must be applied in Terraform before TASK-140.5 is deployed.

2026-10-07 (from TASK-140.3 planning): the job_status_store.py pattern reaches StorageService by importing infrastructure.storage, which import-linter contract (b) no-host-imports forbids for packages; the packages.access entries are shrink-only seeded exemptions (pyproject.toml ignore_imports, 'never add one'), so packages.incident cannot copy it without a new exemption. Decide how the StatusUpdateStore obtains storage before implementing (TASK-108 moves the Protocol to contracts/, TASK-109 adds svcs injection; neither has started). For comparison, TASK-140.3 chose an interim direct adapter over integrations.aws in core/adapters/, behind a core/api.py Protocol.
<!-- SECTION:NOTES:END -->

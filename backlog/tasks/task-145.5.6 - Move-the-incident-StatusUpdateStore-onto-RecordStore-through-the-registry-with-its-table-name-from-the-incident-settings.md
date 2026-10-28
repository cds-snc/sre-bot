---
id: TASK-145.5.6
title: >-
  Move the incident StatusUpdateStore onto RecordStore through the registry,
  with its table name from the incident settings
status: To Do
assignee: []
created_date: 2026-10-14 23:09
updated_date: '2026-10-28T13:47:00Z'
labels:
  - incident
  - features
  - records
dependencies:
  - TASK-145.5.5
references:
  - app/features/incident/core/adapters/status_updates.py
  - decisions/cloud-portability.md
  - decisions/dependency-injection.md
  - https://github.com/cds-snc/sre-bot/issues/1695
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 392000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 10 of Stack K (handoff doc-13). Behaviour-preserving. After TASK-145.5.5 the status-update store is the last incident adapter on get_aws_client: core/adapters/status_updates.py:35,44,248, with the table name hard-coded as sre_bot_incident_status_updates.

THIS SLICE
- The DynamoDB status-update store is rebuilt over RecordStore: a status_updates RecordTable (partition and sort keys as provisioned), the conditional put through put_if_not_exists, and replace_draft guarded on state DRAFT through the expected-guard update (TASK-27.2). Item layout and behaviour unchanged.
- put_if_not_exists (TASK-103) stamps a hidden _rs_write_token attribute (about 45 bytes) on every item it writes and strips it from every read, so the unchanged item layout means the caller-visible attributes. Two concurrent writers of identical content get one created and one conflict, where the current equality check reports both as success; the replay of one caller's own write reports created.
- The table name comes from the incident core settings (TASK-145.5.3), with the provisioned table as default.
- Comms entry points resolve RecordStore through the ServiceScopeOpener and pass the built store, as TASK-145.5.5 does for IncidentStore; any cached provider for the store is deleted.
- InMemoryStatusUpdateStore stays as the consumer fake, and the Stubber tests move to InMemoryRecordStore-backed tests with the same cases.
- TASK-140.11 (a GSI on this table) builds on the new store.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The status-update store is implemented over RecordStore with the same item layout, conditional create and DRAFT-guarded replace; no module in core/ imports an AWS client
- [ ] #2 Its table name comes from the incident core settings with sre_bot_incident_status_updates as the default
- [ ] #3 Comms entry points build the store from a RecordStore resolved through the ServiceScopeOpener; no cached provider remains
- [ ] #4 The existing status-update behaviour tests pass unchanged against the new store, plus conditional-create and guard-lost cases
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-28T13:47:00Z

---

2026-10-28: decisions/configuration.md now makes every backing-resource name deployment configuration on the owning slice (one owning key, default in base.toml); STATUS_UPDATES_TABLE is listed as tolerated until this task.

---
<!-- COMMENTS:END -->

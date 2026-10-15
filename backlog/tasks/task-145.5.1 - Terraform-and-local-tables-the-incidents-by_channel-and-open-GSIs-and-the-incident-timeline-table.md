---
id: TASK-145.5.1
title: >-
  Terraform and local tables: the incidents by_channel and open GSIs and the
  incident timeline table
status: To Do
assignee: []
created_date: '2026-10-14 23:08'
labels:
  - incident
  - terraform
dependencies:
  - TASK-152
references:
  - terraform/dynamodb.tf
  - .devcontainer/dynamodb-create.sh
  - decisions/cloud-portability.md
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 387000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 2 of Stack K (handoff doc-13). Provisions the incident record layout decided on 2026-10-14 (TASK-145.5 plan). No application change.

THIS SLICE
- terraform/dynamodb.tf, incidents table (partition key id, unchanged):
  - GSI by_channel: partition channel_id (S).
  - Sparse GSI open: partition open_bucket (S, constant OPEN while the incident is open), sort opened_at (S, fixed-width ISO-8601 UTC with microseconds and +00:00). Items without open_bucket are absent from it.
  - Projection ALL on both. A KEYS_ONLY index would return key-only rows in production while InMemoryRecordStore returns full items, which breaks contract 4 of decisions/cloud-portability.md. Every existing GSI in the repo uses ALL.
  - Each GSI has its own read and write capacity, write capacity at least the table's (legacy logs appends are written to the index until TASK-145.9 moves the timeline out).
- New table sre_bot_incident_timeline: partition incident_id (S), sort entry_key (S) formatted '<posted_at ISO>#<entry_id>'. Added to the AWS Backup selection and to the task role's table ARNs.
- DynamoDB creates one GSI per UpdateTable call; if the provider does not sequence two in one apply, the slice applies them in two steps.
- .devcontainer/dynamodb-create.sh: creates the incidents table with both GSIs and the timeline table; for an existing local incidents table it adds the missing GSIs (update-table), because codespaces are not rebuilt. The script is run locally as part of this slice.
- Standalone merge; tf_apply (dev then prod) before TASK-145.5.5 merges.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 terraform/dynamodb.tf declares the by_channel and sparse open GSIs on incidents with projection ALL and their own capacity, and the sre_bot_incident_timeline table keyed (incident_id, entry_key)
- [ ] #2 The timeline table is in the backup selection and in the task role's table ARNs
- [ ] #3 tf_plan shows only these changes, and the apply sequence (one or two steps) is recorded in the notes
- [ ] #4 .devcontainer/dynamodb-create.sh creates both GSIs and the timeline table on a fresh run and adds the GSIs to an existing local incidents table; it was run locally and describe-table shows both indexes ACTIVE
<!-- AC:END -->

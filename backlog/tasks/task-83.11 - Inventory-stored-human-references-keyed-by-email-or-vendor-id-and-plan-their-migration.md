---
id: TASK-83.11
title: >-
  Inventory stored human references keyed by email or vendor id and plan their
  migration
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-10-15 18:10'
labels:
  - identity
dependencies:
  - TASK-83.4
references:
  - packages/access/request/store.py
  - terraform/dynamodb.tf
  - 'https://github.com/cds-snc/sre-bot/issues/1621'
parent_task_id: TASK-83
priority: low
ordinal: 178000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/people-and-accounts.md requires new records to reference humans by person id. Existing data does not. For example:
- access request decisions put actor_email in their sort key (packages/access/request/store.py);
- the audit trail table indexes user_email (terraform/dynamodb.tf);
- legacy incident and access code stores emails or Slack ids.

Migrating live DynamoDB data safely needs an inventory first, then one expand, backfill, switch-reads, contract plan per reference.

Each reference migration follows the shared legacy backfill rule set described in decisions/incident-management.md (Migration): expand, backfill, switch reads, contract; one pure upgrade function per record type shared by the read bridge and the backfill; the runner pattern of TASK-145.5.7 (an in-app leased job with an off / dry_run / apply mode, guarded writes, one report event per run, run per environment dry run then apply; no bin script or management command); and a record_version marker that writers stamp and the backfill uses to skip upgraded items.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every stored reference to a human by email, name or vendor user id is recorded in the task notes, with table, attribute and code location
- [ ] #2 No stored data is changed by this task
- [ ] #3 Each reference has a follow-up task describing its expand, backfill, switch-reads and contract steps under the shared backfill rule set (shared upgrade function, TASK-145.5.7 runner pattern, version marker)
<!-- AC:END -->

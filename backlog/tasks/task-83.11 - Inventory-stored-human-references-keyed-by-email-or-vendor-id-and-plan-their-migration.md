---
id: TASK-83.11
title: >-
  Inventory stored human references keyed by email or vendor id and plan their
  migration
status: To Do
assignee: []
created_date: '2026-09-10 16:18'
labels:
  - identity
dependencies:
  - TASK-83.4
references:
  - packages/access/request/store.py
  - terraform/dynamodb.tf
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
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Every stored reference to a human by email, name or vendor user id is recorded in the task notes, with table, attribute and code location
- [ ] #2 Each reference has a follow-up task describing its expand, backfill, switch-reads and contract steps
- [ ] #3 No stored data is changed by this task
<!-- AC:END -->

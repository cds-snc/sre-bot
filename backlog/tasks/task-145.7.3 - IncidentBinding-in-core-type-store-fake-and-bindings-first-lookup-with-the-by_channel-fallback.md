---
id: TASK-145.7.3
title: >-
  IncidentBinding in core: type, store, fake and bindings-first lookup with the
  by_channel fallback
status: To Do
assignee: []
created_date: '2026-11-09T19:06:00Z'
labels:
  - incident
  - features
dependencies:
  - TASK-145.7.1
references:
  - decisions/incident-management.md
parent_task_id: TASK-145.7
priority: medium
type: feature
ordinal: 500000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack L L2a (approved program in TASK-145.7's plan, section 2; outline in the parent plan). core/domain.py BindingKind and IncidentBinding; core/adapters/binding_items.py; RecordIncidentStore.find_by_conversation reads by_conversation first, then channel_id/by_channel (never merged; a binding whose record is missing is not an incident; bindings-table errors are classified failures); in-memory fake; [incident_core] bindings_table. Merges only after L0 has deployed. Behaviour unchanged while the table is empty.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Lookup cases tested: binding hit, fallback to by_channel, dangling binding, archived binding ignored, tenant mismatch dropped with a warning naming both tenants, two active bindings fail closed (AMBIGUOUS_INCIDENT_CONVERSATION), bindings-table error classified
- [ ] #2 A drift test proves the declared RecordTable keys and index equal terraform/dynamodb.tf; existing find_by_conversation tests pass unchanged
- [ ] #3 Checks parent AC #12
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports, make check-package-shape, make check-test-seams and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

---
id: TASK-140.3
title: >-
  Resolve a conversation to its incident id in packages/incident/core over the
  legacy incidents table
status: To Do
assignee: []
created_date: '2026-10-06 15:57'
labels:
  - incident
dependencies:
  - TASK-140.1
parent_task_id: TASK-140
priority: high
type: feature
ordinal: 322000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Core exposes find_incident_for_conversation (the name in decisions/incident-management.md) through core/api.py, returning the incident's existing UUID or a classified refusal. The interim adapter reads the legacy incidents table by channel id through the outbound DynamoDB client, paginating the scan (the legacy lookup reads only the first page); TASK-38.1's store later replaces the adapter behind the same interface. Packages never import modules/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 core/api.py exposes find_incident_for_conversation returning OperationResult with the incident UUID, or a classified not-an-incident refusal
- [ ] #2 The adapter pages through the whole scan and is unit-tested with botocore Stubber across two pages
- [ ] #3 lint-imports keeps packages from importing modules/; ruff, mypy (no new errors in touched files) and pytest pass
<!-- AC:END -->

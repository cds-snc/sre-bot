---
id: TASK-23
title: 'Resolve every _next.py twin: one canonical client per vendor module'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-08 16:57'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22
references:
  - decisions/outbound-clients.md
  - 'https://github.com/cds-snc/sre-bot/issues/1277'
priority: high
ordinal: 23000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/outbound-clients.md (Migration: "_next.py twins resolve into this shape"). Today app/integrations/ contains a fourth client generation: _next.py twins beside originals (aws/client_next.py, aws/dynamodb_next.py, aws/identity_store_next.py, google_workspace/google_directory_next.py, google_workspace/gmail_next.py, google_workspace/google_service_next.py).

Steps:
1. For each twin pair, diff the original vs _next and pick the survivor per the decided contract (clients raise typed SDK exceptions, SDK-native retry configured at construction, no hand-rolled retry, no OperationResult in clients).
2. Rename the survivor to the canonical name (no _next suffix), migrate its consumers, delete the loser. One vendor per PR.
3. Where neither twin matches the contract, converge on the closer one and fix it in the same PR (contract enforcement itself completes in task-25).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 find app/integrations -name "*_next.py" returns zero files
- [ ] #2 Each vendor module has exactly one client construction path
- [ ] #3 All consumers import the canonical module; tests pass per vendor PR
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 No behavior change observable from feature code (existing tests green)
- [ ] #2 PR series references decisions/outbound-clients.md
<!-- DOD:END -->

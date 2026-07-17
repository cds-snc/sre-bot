---
id: TASK-1.2.2
title: >-
  Migrate runtime infra environment gates to ENVIRONMENT (DynamoDB, startup,
  CORS)
status: To Do
assignee: []
created_date: '2026-07-17 19:44'
labels:
  - phase-0
milestone: m-0
dependencies:
  - TASK-1.2.1
references:
  - decisions/configuration.md
parent_task_id: TASK-1.2
priority: high
ordinal: 48000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-1.2. Replace PREFIX-based environment derivation in AWS DynamoDB client selection, scheduled-task startup gate, and CORS allow-origins selection. Three DynamoDB paths are independent entry-points that all set local endpoint when PREFIX is truthy; each must check ENVIRONMENT in (local, dev, ci) instead. Scheduled tasks currently skip when PREFIX != ''; must check ENVIRONMENT == production instead. server.py CORS currently uses not bool(PREFIX); must use ENVIRONMENT. is_production shim still NOT removed — that happens in TASK-1.2.3.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/aws/dynamodb.py local endpoint set only when ENVIRONMENT in (local, dev, ci); no PREFIX reference remains for environment decisions
- [ ] #2 integrations/aws/client_next.py get_aws_client DynamoDB local endpoint set only when ENVIRONMENT in (local, dev, ci); no PREFIX reference remains for environment decisions
- [ ] #3 modules/aws/aws_access_requests.py _get_dynamodb_client uses ENVIRONMENT in (local, dev, ci) for local endpoint; no PREFIX reference remains for environment decisions
- [ ] #4 server/lifespan.py _start_scheduled_tasks skips when ENVIRONMENT == production; no PREFIX reference remains
- [ ] #5 server/server.py CORS allow_origins computed from ENVIRONMENT == production not from bool(PREFIX); wildcard is returned for non-production, explicit list for production
- [ ] #6 Unit tests cover DynamoDB endpoint matrix: local/dev/ci get local URL; staging/production get None
- [ ] #7 Lifespan integration test updated: PREFIX-based skip test replaced with ENVIRONMENT-based skip test
- [ ] #8 Full non-smoke test suite passes
<!-- AC:END -->

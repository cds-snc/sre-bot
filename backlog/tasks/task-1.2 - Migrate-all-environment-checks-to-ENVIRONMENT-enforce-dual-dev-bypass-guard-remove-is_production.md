---
id: TASK-1.2
title: >-
  Migrate all environment checks to ENVIRONMENT; enforce dual dev-bypass guard;
  remove is_production
status: To Do
assignee: []
created_date: '2026-07-17 16:14'
updated_date: '2026-07-17 19:43'
labels:
  - phase-0
milestone: m-0
dependencies:
  - TASK-1.1
references:
  - decisions/configuration.md
  - decisions/security.md
parent_task_id: TASK-1
priority: high
ordinal: 46000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Migrate + contract phase for TASK-1. Replace every is_production and PREFIX-derived environment check across 9 production files with reads of AppSettings.ENVIRONMENT. Apply the dual dev-bypass guard in current_user.py (ENVIRONMENT != "production" AND DEV_BYPASS_ENABLED). Fix SNS validation gap (aws_sns.py skipped validation when not is_production — must validate in all environments). Set local DynamoDB endpoint for ENVIRONMENT in (local, dev, ci) only. Remove is_production shim. Update all test fixtures that mocked is_production.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 grep -rn "is_production" app/ --include="*.py" returns no hits outside test files that assert the property is gone
- [ ] #2 grep -rn "PREFIX\s*[!<>=]\|bool(PREFIX)\|if.*PREFIX\b" app/ --include="*.py" returns no environment-derivation hits (PREFIX may remain for URL-prefix use only)
- [ ] #3 current_user.py dev-bypass requires ENVIRONMENT != production AND DEV_BYPASS_ENABLED=true; either guard alone blocks bypass; each use is logged
- [ ] #4 dynamodb local endpoint activates only for ENVIRONMENT in (local, dev, ci); staging and production use real AWS
- [ ] #5 All existing tests plus new dual-guard tests pass
- [ ] #6 aws_sns.py validate_sns_payload skips validation when ENVIRONMENT != 'production' (local/dev/ci never receive real SNS payloads from the internet); validation is always enforced when ENVIRONMENT == 'production'
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
TASK-1.2 is further decomposed into three right-sized slices (single-PR gate re-triggered: 16 production files, 3 subsystem layers, mechanical + behavioral mixed).

SNS deviation: AC #6 reflects an approved operational deviation from decisions/security.md. Local/dev/ci instances are not internet-reachable and never receive real SNS payloads; production-only enforcement is the confirmed design. This deviation is explicit and recorded here.

Subtask execution order:
1. TASK-1.2.1 — Security/Auth + Transport: current_user.py dual-guard, aws_sns.py env-check, api_key_detected.py, notify/client.py
2. TASK-1.2.2 — Runtime Infra Gates: DynamoDB local endpoint, scheduled-tasks gate, CORS gate
3. TASK-1.2.3 — Legacy env branches + is_production contract removal: dev/platforms/slack.py, incident/core.py, incident_conversation.py, shim deletion from app.py/settings.py/logging/setup.py

TASK-1.2 ACs satisfied when all subtasks done:
- AC #1 (is_production gone) and AC #2 (PREFIX env-derivation gone) verified after TASK-1.2.3
- AC #3 (dual bypass guard) verified after TASK-1.2.1
- AC #4 (DynamoDB env matrix) verified after TASK-1.2.2
- AC #5 (tests pass) verified per slice
- AC #6 (SNS deviation) verified after TASK-1.2.1
<!-- SECTION:PLAN:END -->

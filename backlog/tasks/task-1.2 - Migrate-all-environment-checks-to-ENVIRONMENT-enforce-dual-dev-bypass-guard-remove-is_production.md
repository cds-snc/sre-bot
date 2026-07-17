---
id: TASK-1.2
title: >-
  Migrate all environment checks to ENVIRONMENT; enforce dual dev-bypass guard;
  remove is_production
status: To Do
assignee: []
created_date: '2026-07-17 16:14'
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
- [ ] #4 aws_sns.py validate_sns_payload validates in all environments (no is_production skip)
- [ ] #5 dynamodb local endpoint activates only for ENVIRONMENT in (local, dev, ci); staging and production use real AWS
- [ ] #6 All existing tests plus new dual-guard tests pass
<!-- AC:END -->

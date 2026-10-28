---
id: TASK-111.13.2
title: Delete the unused infrastructure/resilience package and RetrySettings
status: Done
assignee: []
created_date: '2026-10-28T13:46:00Z'
updated_date: '2026-10-28T15:03:00Z'
labels:
  - configuration
milestone: m-7
dependencies: []
references:
  - decisions/reliability.md
parent_task_id: TASK-111.13
type: task
ordinal: 456000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice B of TASK-111.13 (program-scope finding 2026-10-28). The retry store, retry worker, ResilienceService and circuit breaker have no production consumer; RetrySettings is deleted with them instead of moving onto the files. Supersedes TASK-59; durable retry is built on QueueService (TASK-34) when a consumer needs it (decisions/reliability.md).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 app/infrastructure/resilience/ and its tests are deleted and nothing imports infrastructure.resilience
- [x] #2 RetrySettings and infrastructure/configuration/infrastructure/retry.py are deleted, no [retry] table exists, and every RETRY_* name is in the env audit HINTS as deleted
- [x] #3 The import-linter source_modules and the fake-coverage baseline no longer name the resilience package, and make check-fake-coverage passes
- [x] #4 The sre_bot_retry_records table and its IAM grant are removed from terraform and the devcontainer table script after the human confirms the table is empty
- [x] #5 decisions/reliability.md and plugin-architecture.md no longer list the retry store or the resilience adapter
- [x] #6 ruff, mypy (no new errors), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-10-28 against main 83f895ab (program-scope finding F7 in TASK-111.13 planning, approved by the human 2026-10-28 as dead-code deletion).

Finding: app/infrastructure/resilience/ (retry store, DynamoDB retry store, RetryWorker, ResilienceService, circuit breaker; ~1930 LOC) has no production importer: get_resilience_service has no caller, nothing outside the package and its tests imports it, and the only circuit-breaker settings are in the dead groups slice (TASK-111.14 deletes it). RetrySettings (infrastructure/configuration/infrastructure/retry.py) is read only by it. The terraform table sre_bot_retry_records is never written by production.

Steps:
1. Delete app/infrastructure/resilience/ and its tests (tests/unit/infrastructure/resilience*, retry conftest), RetrySettings and infrastructure/configuration/infrastructure/retry.py; drop the RetrySettings export from infrastructure/configuration/__init__.py and test references (services/test_narrow_slice_providers.py, configuration tests).
2. app/pyproject.toml import-linter source_modules drops infrastructure.resilience; app/bin/baselines/fake_coverage.txt drops the RetryStore and RetryProcessor lines.
3. app/bin/audit_env_names.py HINTS: every RETRY_* name -> deleted.
4. terraform: delete aws_dynamodb_table.sre_bot_retry_records and its IAM statements in iam.tf (and any backup selection reference); .devcontainer/dynamodb-create.sh drops the table. Human first: confirm the table holds no items (read-only: aws dynamodb scan --table-name sre_bot_retry_records --select COUNT) and check deletion_protection in the plan; if not empty, the terraform part becomes its own follow-up.
5. Docs: decisions/reliability.md (amended 2026-10-28, rides here), plugin-architecture.md:13 hosting adapter list drops resilience; TASK-59 note (human closes it superseded).

Tests: a test asserts infrastructure.resilience and infrastructure.configuration.infrastructure.retry no longer import; rg sweep for resilience|RetrySettings|get_retry_settings outside backlog/ and decision history lines is empty.
Gates: ruff, mypy (baseline 47), pytest, make check-import-contracts, make check-settings-key-ownership, make check-fake-coverage, terraform fmt and validate.
Rollout: merge deploys and tf_apply destroys one empty table and its IAM grant; nothing in the running app reads either. Rollback: git revert restores code and recreates the empty table.
Independent of TASK-111.13.1; either may merge first. ~1930 LOC deleted across ~12 production files plus terraform; deletion only, no behaviour change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented 2026-10-28 on task-111.13.2-delete-resilience from main fe571ad2. Deleted infrastructure/resilience/ (retry store, DynamoDB store, worker, ResilienceService, circuit breaker), infrastructure/configuration/infrastructure/ (RetrySettings was its only module) and their tests; infrastructure/configuration/__init__ no longer exports RetrySettings. HINTS lists the nine RETRY_* names as deleted. import-linter source_modules and the fake-coverage baseline drop the package. Terraform drops aws_dynamodb_table.sre_bot_retry_records (no deletion_protection_enabled set), its ARN in local.dynamodb_table_arns (task role and backup selection) and its index ARN in the iam.tf Query statement; .devcontainer/dynamodb-create.sh no longer creates it. plugin-architecture.md drops resilience from the hosting adapters and the RetryStore from the tolerated list; reliability.md drops the RetryStore tolerance (the 2026-10-28 amendment from #1801 otherwise matches). Tests: test_infrastructure_resilience_removed.py (modules gone), RETRY_* HINTS cases in test_bin_audit_env_names_classify.py. Gates: ruff clean; mypy 43 errors (baseline 47, the 4 removed lived in deleted files, none in touched files); pytest 5879 passed; contracts 13 kept; key ownership OK; fake coverage OK (4 baselined); terraform fmt clean, validate OK. AC 4 verified 2026-10-28 (human): scan of sre_bot_retry_records returned Count 0, ScannedCount 0; no RETRY_* line in any .env* file; tf plan: delete aws_dynamodb_table.sre_bot_retry_records, update aws_iam_policy.sre-bot_secrets_manager (its document holds the DynamoDB statements), recreate aws_backup_selection.sre_bot_backup_selection (resources forces replacement; recovery points are kept, the selection is absent only for the seconds between delete and create). Merge destroys one empty table and its IAM grant; nothing in the running app reads either; git revert recreates an empty table.
<!-- SECTION:NOTES:END -->

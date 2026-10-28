---
id: TASK-111.13.3
title: >-
  Move the audit and coordination slices onto the files; delete
  InfrastructureSettings
status: Done
assignee: []
created_date: '2026-10-28T13:46:00Z'
updated_date: '2026-10-28T19:48:00Z'
labels:
  - configuration
milestone: m-7
dependencies:
  - TASK-111.13.1
  - TASK-111.13.2
references:
  - decisions/configuration.md
  - decisions/reliability.md
parent_task_id: TASK-111.13
type: feature
ordinal: 457000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice C of TASK-111.13. AuditSettings reads [audit] and ConditionalWriteSettings reads [coordination], with keys that do not repeat their table and the table names as deployment configuration (decisions/configuration.md, 2026-10-28). The coordination stores take their values as arguments, removing the unvalidated model_copy override. InfrastructureSettings goes once no slice inherits it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ConditionalWriteSettings reads [coordination] (table_name, record_ttl_seconds, in_progress_ttl_seconds) with extra=forbid and its defaults in base.toml; IDEMPOTENCY_TABLE and the IDEMPOTENCY_* names are no longer read
- [x] #2 The coordination stores take the table name and both TTLs as constructor arguments; the lease factory passes its TTL directly, with no model_copy
- [x] #3 AuditSettings reads [audit] table_name with extra=forbid and its default in base.toml; AUDIT_TABLE_NAME is no longer read
- [x] #4 InfrastructureSettings and the infrastructure/configuration/infrastructure package are deleted
- [x] #5 An unknown key in [audit] or [coordination] fails boot naming it
- [x] #6 bin/unlock-sync-job.sh takes the table name as an argument; the retired names are in the env audit HINTS
- [x] #7 ruff, mypy (no new errors), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Planned 2026-10-28 against main 83f895ab from the TASK-111.13 plan (slice B) with the human's 2026-10-28 rulings: a key does not repeat its table; backing-resource names are deployment configuration (decisions/configuration.md).

Findings: production sets none of the IDEMPOTENCY_* or AUDIT_TABLE_NAME names. The coordination stores read their TTLs from a settings object, and coordination/factory.py:17-19 overrides one with model_copy(update={"idempotency_in_progress_ttl_seconds": ...}), which does not validate (R1). The coordination table name is the constant IDEMPOTENCY_TABLE (coordination/dynamodb.py:25). No import-time reads.

Steps (tests first):
1. infrastructure/coordination/settings.py: ConditionalWriteSettings(ConfigurationSlice), ("coordination",), "COORDINATION__", extra forbid; table_name = "sre_bot_idempotency", record_ttl_seconds = 3600, in_progress_ttl_seconds = 300.
2. coordination/dynamodb.py and in_memory.py take table_name (DynamoDB only), record_ttl_seconds and in_progress_ttl_seconds as constructor arguments, not the settings object; IDEMPOTENCY_TABLE deleted; factory.py passes the override int directly (no model_copy); server/services.py:44 builds from the slice.
3. infrastructure/audit/settings.py: AuditSettings(ConfigurationSlice), ("audit",), "AUDIT__"; table_name = "sre_bot_audit_trail"; audit/service.py:263 reads table_name.
4. Delete InfrastructureSettings (infrastructure/configuration/base.py) and the infrastructure/configuration/infrastructure/ package.
5. server/configuration/host_configuration.py _validate_slices builds the audit and coordination slices so an invalid table fails boot.
6. app/config/base.toml: [coordination] and [audit] with the values above.
7. HINTS: IDEMPOTENCY_TTL_SECONDS, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS -> [coordination] keys; AUDIT_TABLE_NAME -> [audit] table_name.
8. app/bin/unlock-sync-job.sh takes the table name as an argument, defaulting to the base.toml name.
9. Docs: configuration.md tolerated item for IDEMPOTENCY_TABLE closed (dated line); reliability.md 2026-10-28 line rides here; doc-14 facts line.

Tests: test_coordination_settings_load.py and test_audit_settings_load.py (defaults from base.toml, file and env override, unknown key fails naming it, old names unread); store constructor tests take ints; the R1 factory tests assert the override reaches the store; ~20 call sites move from upper-case settings kwargs to constructor args; test_configuration_settings_structure.py (no InfrastructureSettings; the package does not import); lifespan hosting-slice validation test gains [audit] and [coordination].
Gates: ruff, mypy (baseline 47), pytest, make check-import-contracts, make check-settings-key-ownership.
Rollout: merge deploys; no terraform or SSM change; values equal today's defaults and table names. Circuit breaker and one git revert as rollback.
Waits on TASK-111.13.1 and TASK-111.13.2 (both touch base.toml, HINTS and the configuration package; InfrastructureSettings goes only once no slice inherits it). ~14 production files, ~200 LOC.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Plan approved 2026-10-28 (human). Implemented on task-111.13.3-audit-coordination-slices from main 4c914688, tests first.

ConditionalWriteSettings is a ConfigurationSlice on [coordination] (table_name, record_ttl_seconds, in_progress_ttl_seconds; COORDINATION__ prefix, extra forbid) and AuditSettings on [audit] (table_name; AUDIT__); both tables are in base.toml with today's values (sre_bot_idempotency, 3600, 300; sre_bot_audit_trail), and _validate_slices builds both, so an unknown key fails boot naming it. DynamoDBConditionalWriteStore and InMemoryConditionalWriteStore take table_name (DynamoDB) and both TTLs as keyword arguments; IDEMPOTENCY_TABLE is deleted; the lease factory passes the slice's table and record TTL and its own in-progress TTL directly (no model_copy); server/services.py builds the store from the slice. InfrastructureSettings is deleted (its package went with 111.13.2). HINTS map IDEMPOTENCY_TTL_SECONDS, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS and AUDIT_TABLE_NAME to their keys; bin/unlock-sync-job.sh takes --table (default the base.toml name). The mock-settings helpers' retired idempotency example key removed. Docs: configuration.md tolerated IDEMPOTENCY_TABLE and unlock-script items closed and a Changes line, reliability.md Changes line, doc-14 facts line (production sets none of the three names).

Tests: new test_coordination_settings_load.py and test_audit_settings_load.py replace test_coordination_settings.py and test_audit_settings_table_name.py; store, factory, lease and fixture call sites take plain arguments; the lifespan hosting-slice test covers [audit] and [coordination]; the checked-in files test pins both tables; the env-audit classifier pins the three hints; the production-names test drops the two slices (their case-insensitivity examples now use SentinelSettings).

Gates (2026-10-28): ruff All checks passed; mypy Found 43 errors in 15 files (= baseline after 111.13.2, none in touched files); pytest tests --ignore=tests/smoke 5900 passed; make check-import-contracts 13 kept, 0 broken; make check-settings-key-ownership OK; make check-fake-coverage OK (4 baselined gaps).

Rollout: merge deploys; no terraform or SSM change; values equal the former defaults and table names. Rollback: circuit breaker, or one git revert. After deploy: post (generic).
<!-- SECTION:NOTES:END -->

---
id: TASK-111.13.3
title: >-
  Move the audit and coordination slices onto the files; delete
  InfrastructureSettings
status: To Do
assignee: []
created_date: '2026-10-28T13:46:00Z'
updated_date: '2026-10-28T13:46:00Z'
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
- [ ] #1 ConditionalWriteSettings reads [coordination] (table_name, record_ttl_seconds, in_progress_ttl_seconds) with extra=forbid and its defaults in base.toml; IDEMPOTENCY_TABLE and the IDEMPOTENCY_* names are no longer read
- [ ] #2 The coordination stores take the table name and both TTLs as constructor arguments; the lease factory passes its TTL directly, with no model_copy
- [ ] #3 AuditSettings reads [audit] table_name with extra=forbid and its default in base.toml; AUDIT_TABLE_NAME is no longer read
- [ ] #4 InfrastructureSettings and the infrastructure/configuration/infrastructure package are deleted
- [ ] #5 An unknown key in [audit] or [coordination] fails boot naming it
- [ ] #6 bin/unlock-sync-job.sh takes the table name as an argument; the retired names are in the env audit HINTS
- [ ] #7 ruff, mypy (no new errors), pytest tests --ignore=tests/smoke, make check-import-contracts and make check-settings-key-ownership pass
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

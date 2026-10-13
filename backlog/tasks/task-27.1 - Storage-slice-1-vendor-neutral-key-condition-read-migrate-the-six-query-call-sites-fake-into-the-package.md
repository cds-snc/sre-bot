---
id: TASK-27.1
title: >-
  Records slice 1: vendor-neutral key-condition read, migrate the six query call
  sites, fake into the package
status: Done
assignee:
  - '@me'
created_date: '2026-09-16 13:57'
updated_date: '2026-10-13 18:59'
labels:
  - infrastructure
  - phase-4
  - portability
milestone: m-4
dependencies:
  - TASK-27.4
references:
  - app/infrastructure/records/protocol.py
  - app/infrastructure/audit/service.py
  - app/packages/access/request/store.py
  - decisions/cloud-portability.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-27
priority: high
ordinal: 219000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-27 (see the coordinator plan). Pulled forward: this slice is disjoint from TASK-25.2.5 (different files) and can run in parallel with it rather than waiting for the rest of m-4.

WHY NOW. RecordStore.query(table, key_condition: str, ...) leaks DynamoDB KeyConditionExpression through a Path A Protocol, the counterexample decisions/cloud-portability.md contract 4 names by hand. It has exactly six call sites today, in four files, and neither consumer is live in production: infrastructure/audit's service has no importer outside its own package (integrations/sentinel/client.py imports only audit.models), and packages/access is not enabled yet (TASK-25.2 scope note). This is the cheapest this change will ever be, and it gets more expensive with every new consumer: TASK-32, TASK-60, TASK-83, TASK-83.2, TASK-37.1 and TASK-145 all write against this Protocol.

THE SIX CALL SITES (read 2026-09-16)
- infrastructure/audit/service.py:151 resource_id = :rid, plus an optional AND timestamp_correlation_id < :ts; Limit, ScanIndexForward=False
- infrastructure/audit/service.py:192 user_email = :ue, plus an optional AND timestamp < :ts; IndexName user_email-timestamp-index, Limit, ScanIndexForward=False
- infrastructure/audit/service.py:221 correlation_id = :cid; IndexName correlation_id-index, Limit=1
- packages/access/request/store.py:133 PK = :pk AND begins_with(SK, :prefix)
- packages/access/request/store.py:183 PK = :pk
- packages/access/sync/store.py:72 PK = :pk; ScanIndexForward=False, Limit

SURFACE. Partition-key equality plus an optional sort-key condition, an optional index name, a limit and a forward flag. Sort conditions with a real consumer today are eq, lt and begins_with. gt and between are NOT added here: no caller needs them, and decisions/plugin-architecture.md bars building Path A surface speculatively. between is what audit's currently unimplemented end_time parameter would need, so record it against audit rather than adding it blind.

NOT IN THIS SLICE. Atomic update, numeric increment and the bounded full-table list are TASK-27.2, which lands with its first consumer (TASK-37.1). Path A fake coverage for directory and audit plus the CI fake-coverage check are TASK-27.3.

FAKE. Move the InMemoryRecordStore test fake (TASK-27.4) out of app/tests/unit/infrastructure/records/ into the records package itself (app/infrastructure/records/in_memory.py), mirroring infrastructure/idempotency/in_memory.py, so the CI check TASK-27.3 wires reads the package tree. Update its importers (its own tests under tests/unit/infrastructure/records/, the records integration conftest, tests/unit/infrastructure/audit/test_service.py and anything the re-grep finds).

SIZE. About 165 production LOC: protocol.py ~35, service.py query ~40 changed, the six call sites ~50, the fake ~40 changed. Three directories (infrastructure/records, infrastructure/audit, packages/access), which is at the edge of the two-subsystem rule; if review wants it tighter, split expand/migrate/contract, remembering the TASK-27 decision that no compat overload is retained in the end state.

LANDED SHAPE (app/infrastructure/records/protocol.py). Each repository builds its RecordTable once: the key layout (KeySchema, indexes) is declared in code next to the item layout, and the table name comes from the owning package's settings with the provisioned table as default. RecordTable(name, key: KeySchema(partition, sort), indexes: logical name -> RecordIndex(physical_name, key)). Every RecordStore method takes that table: put, put_if_not_exists (no pk_attribute; the guard covers the full table.key), get, query(table, RecordQuery(partition, sort: SortCondition, index, limit, order)) and delete; limit is a total cap and None returns every match.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The RecordStore read operation takes a typed, vendor-neutral key-condition spec (partition-key equality, optional sort-key condition, optional logical index name resolved through the table's declared key layout, limit, ASC/DESC sort order) and no signature on the Protocol contains a DynamoDB expression string, ExpressionAttributeValues or any other vendor type
- [x] #2 Only sort-key conditions with a real consumer are implemented (eq, lt, begins_with); gt and between are recorded as deferred with the consumer that would need them, per decisions/layers.md on speculative Path A surface
- [x] #3 All six existing call sites are migrated (infrastructure/audit/service.py x3, packages/access/request/store.py x2, packages/access/sync/store.py x1) and the raw-string query signature is deleted outright, with no compatibility overload retained
- [x] #4 No RecordStore Protocol signature, in-memory fake or RecordStore caller carries a DynamoDB expression string; within app/infrastructure/records/, rg for KeyConditionExpression or ExpressionAttributeValues hits only service.py and its own tests
- [x] #5 InMemoryRecordStore lives in the records package (mirroring infrastructure/idempotency/in_memory.py), honours the new spec, and every former importer of the test-tree fake is repointed
- [x] #6 The conformance suite runs the same cases against the fake and the moto-backed DynamoDB implementation and passes on both
- [x] #7 limit is a total cap on returned items in both the DynamoDB store and the fake; limit=None returns every match
- [x] #8 The fake honours the table key schema: put overwrites an item with the same full key and put_if_not_exists guards the full key, matching DynamoDB, with conformance cases on both stores
- [x] #9 ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass, with the commands and their output recorded in notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SIZE GATE: passes. About 7 production files (records/protocol.py, records/service.py, records/in_memory.py new, audit/service.py, access/request/store.py, access/sync/store.py, access/sync/job_status_store.py) plus one deleted test-tree file; about 230-260 production LOC; two subsystems (infrastructure, packages/access); one git revert restores the old signatures. Expand/contract is not usable because the end state allows no compat overload, so this is one flag-day change over 14 call sites in 4 files. Behaviour changes inside functions already being rewritten (limit as a total cap, fake keyed by full key) are called out in the PR description and have their own tests. Imports: no new import-linter ignore entries; the spec types live in infrastructure/records/protocol.py, whose edges from packages.access.* are already allowed.

TYPES (all in app/infrastructure/records/protocol.py; frozen dataclasses with slots, no Pydantic)
- type KeyValue = str | int
- KeySchema(partition: str, sort: str | None = None)
- RecordIndex(physical_name: str, key: KeySchema)
- RecordTable(name: str, key: KeySchema, indexes: Mapping[str, RecordIndex] = field(default_factory=lambda: MappingProxyType({}), hash=False)). Indexes are keyed by a logical name such as "by_user"; the DynamoDB adapter maps it to physical_name. hash=False keeps the frozen dataclass hashable despite the mapping field.
- SortOperator(StrEnum): EQ, LT, BEGINS_WITH. SortOrder(StrEnum): ASC, DESC.
- SortCondition(operator: SortOperator, value: KeyValue)
- RecordQuery(partition: KeyValue, sort: SortCondition | None = None, index: str | None = None, limit: int | None = None, order: SortOrder = SortOrder.ASC). __post_init__ raises ValueError when BEGINS_WITH has a non-str value or limit < 1. Ordering is always on the effective sort key (the table's, or the index's); there is no order-by field. gt and between are deferred (between would serve audit's unimplemented end_time); the Protocol docstring notes begins_with lowers to a key range on DynamoDB tables and Firestore, STARTSWITH on Cosmos and LIKE on Postgres.
- resolve_query_key(table: RecordTable, spec: RecordQuery) -> KeySchema, a pure helper in protocol.py shared by both implementations. It returns the effective KeySchema (table.key, or table.indexes[spec.index].key) and raises ValueError when spec.index is not in table.indexes or when spec.sort is set and the effective key has no sort attribute. ValueError, not OperationResult: the schema and query are static caller code, so a mismatch is a programming error that must fail in every test, while OperationResult errors are reserved for runtime backend failures. One helper means the fake and DynamoDB cannot disagree.
- RecordStore (every method takes table: RecordTable): put(table, item), put_if_not_exists(table, item) with no pk_attribute (guard derived from table.key), get(table, key), query(table, spec: RecordQuery), delete(table, key).

TABLE SOURCING (amended after review, reviewer decision): hardcoding table names in code is an anti-pattern, so each repository keeps its key layout in code and takes its table name from settings with today's table as the default: AuditSettings.AUDIT_TABLE_NAME (new infrastructure/audit/settings.py), ACCESS_REQUESTS_TABLE_NAME, ACCESS_SYNC_TABLE_NAME and ACCESS_SYNC_JOB_STATUS_TABLE_NAME (access settings slices). Each module exposes <name>_table(name) -> RecordTable and the provider passes the configured name. The layouts below were the original constants; names now default to the same values. audit/service.py: AUDIT_TABLE = RecordTable("sre_bot_audit_trail", KeySchema("resource_id", "timestamp_correlation_id"), {"by_user": RecordIndex("user_email-timestamp-index", KeySchema("user_email", "timestamp")), "by_correlation": RecordIndex("correlation_id-index", KeySchema("correlation_id"))}). access/request/store.py: RecordTable("sre_bot_access_requests", KeySchema("PK", "SK")). access/sync/store.py: RecordTable("sre_bot_access", KeySchema("PK", "SK")). access/sync/job_status_store.py: RecordTable("sre_bot_idempotency", KeySchema("idempotency_key")). Layouts verified against terraform/dynamodb.tf. The class attribute TABLE is replaced by the constant.

STEPS (TDD: tests first, red, then production)
1. Tests first:
   a. NEW tests/unit/infrastructure/records/test_records_query_spec.py: RecordQuery validation, resolve_query_key outcomes (table key, index key, unknown index, sort condition on a key with no sort attribute), hashability of RecordTable, no vendor vocabulary in the protocol module (mirrors tests/unit/infrastructure/idempotency/test_idempotency_store_protocol.py).
   b. EDIT tests/unit/infrastructure/records/test_records_dynamodb_store_operations.py: all calls take a RecordTable; query tests (lines 186-290) assert #pk/#sk placeholders in KeyConditionExpression and ExpressionAttributeNames (reserved word `timestamp` safe), serialized values, IndexName = physical_name, ScanIndexForward from order, PaginationConfig from limit, error propagation; put_if_not_exists asserts attribute_not_exists on the partition key placeholder.
   c. EDIT tests/unit/infrastructure/records/test_records_in_memory_store_operations.py and test_records_store_protocol_conformance.py: import from the package, pass RecordTable.
   d. NEW tests/integration/infrastructure/records/test_records_store_query_conformance.py: one parametrized fixture (in_memory, dynamodb via moto), identical cases on both: partition equality; eq/lt/begins_with; ASC and DESC; limit as a total cap, including DESC returning the newest N; index query via logical name with a `timestamp` sort attribute; items missing the index attribute excluded; empty partition returns []; lt exclusive; put overwrites an item with the same full key; put_if_not_exists succeeds for a new sort key under an existing partition and is rejected for the same full key; get/delete by full key. Extend tests/integration/infrastructure/records/conftest.py with a GSI and the param fixture. Move the put/get/put_if_not_exists/delete/query cases that overlap out of test_records_dynamodb_store_conformance.py so no case is duplicated; keep only DynamoDB-specific ones there.
   e. EDIT tests/unit/infrastructure/audit/test_service.py (lines 57 and 150-290): query cases seeded through InMemoryRecordStore and asserted on behaviour (newest first, start_time exclusive, cap 100, index selection, limit 1); MagicMock only for put and error stubs.
   f. EDIT tests/unit/packages/access/sync/test_job_status_store.py (lines 28 and 50: table is now the RecordTable). NEW tests/unit/packages/access/request/test_access_request_store_queries.py (get_decisions prefix filter and SK order, get_request_with_decisions) and tests/unit/packages/access/sync/test_access_sync_run_store_recent.py (get_recent_runs newest first, capped at limit), both on InMemoryRecordStore.
2. protocol.py: add the types, resolve_query_key, the new Protocol signatures and docstrings.
3. NEW infrastructure/records/in_memory.py (moved from tests/unit/infrastructure/records/in_memory_record_store.py, mirroring infrastructure/idempotency/in_memory.py; not re-exported). Items are stored per table.name keyed by the full key tuple from table.key: put overwrites, put_if_not_exists is rejected only for the same full key, get/delete by full key, an item missing a key attribute returns a permanent error. query resolves the effective key with resolve_query_key, filters on its partition attribute, applies the sort condition on its sort attribute, stable-sorts by it, reverses for DESC, truncates to limit, deep-copies; items missing the partition or sort attribute are excluded (sparse index). Delete the test-tree fake and repoint its importers.
4. records/service.py: every method takes RecordTable and uses table.name; put_if_not_exists uses ConditionExpression attribute_not_exists(#pk) with ExpressionAttributeNames from table.key.partition (on a composite-key table this guards the full key coordinate); query builds KeyConditionExpression from #pk/#sk placeholders and ExpressionAttributeNames of the effective key, IndexName from the index's physical_name, ScanIndexForward from order, and PaginationConfig {"MaxItems": limit, "PageSize": limit} when limit is set. BUG FIX: today Limit is only the per-page size and every page is aggregated, so audit, sync get_recent_runs and the correlation lookup return all matches; limit becomes a total cap. limit=None stays unbounded aggregation (the bounded list is TASK-27.2).
5. Migrate all 14 call sites: audit/service.py:103 (put), :151, :192, :221 (queries: resource_id with LT on timestamp_correlation_id when start_time, DESC, limit min(limit,100); index by_user with LT on timestamp, DESC; index by_correlation, limit 1); access/request/store.py:86, :123, :161 (put), :96 (get), :133 (partition PK, BEGINS_WITH SK "DECISION#"), :183 (partition PK); access/sync/store.py:56 (put), :72 (partition, DESC, limit); access/sync/job_status_store.py:37 (put), :43 (get).
6. Gates from app/: ruff check ., lint-imports, mypy (0 errors in touched files), pytest tests --ignore=tests/smoke; grep touched files for function-level imports and __import__/importlib.

AC TRACEABILITY
- AC1: steps 2, 4; tests 1a, 1b, 1d. AC2: step 2 (SortOperator has three members; deferral comment); test 1a. AC3: steps 2, 5; tests 1e, 1f (scope now all 14 RecordStore call sites, six of them queries). AC4: steps 2-5; verified by rg for KeyConditionExpression|ExpressionAttributeValues|key_condition|expression_values over app/infrastructure/records and the callers. AC5: step 3; tests 1c, 1d. AC6: test 1d. AC7: step 4 and fake truncation; tests 1b, 1d, 1e, 1f. AC8: step 3 and step 4 (put_if_not_exists guard); test 1d. AC9: step 6.

TEST MATRIX: happy (partition, eq, lt, begins_with, index query, overwrite put); boundary (lt exclusive, limit 1, limit equal to count, limit above count, empty partition, new sort key under existing partition); failure (invalid spec, unknown index, sort condition on a sort-less key, duplicate full key rejected, SDK ClientError mapped, missing index attribute); ordering (ASC, DESC, DESC with limit). Authorization/idempotency: not applicable.

ASSUMPTIONS AND DOUBTS
A1. Moto honours ExpressionAttributeNames in KeyConditionExpression, a GSI, and PaginationConfig MaxItems with ScanIndexForward=False. Verify in the conformance run.
A2. attribute_not_exists on the partition key attribute guards the full composite key for a put (DynamoDB evaluates the condition against the item with that full primary key). Verify with the conformance case for a new sort key under an existing partition.
A3. The four tables' key layouts match terraform/dynamodb.tf (verified when planning); app/bin/db.sh and unlock-sync-job.sh use the table names only.
A4. No RecordStore caller exists outside the four files (rg RecordStore|get_record_store over app/ excluding tests shows only those plus providers and the records package).
A5. job_status_store shares sre_bot_idempotency with infrastructure/idempotency; its RecordTable declares only the key attribute, so both stay compatible.

BLAST RADIUS AND ROLLBACK: neither consumer is live in production (audit has no importer outside its package; access is not enabled), so a wrong ship breaks no running path. One git revert restores the previous signatures, fake location and tests; no data, config, terraform or ordering constraints. Result counts for audit and sync change from all matches to at most limit, which is the intended behaviour.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
What changed
- infrastructure/records/protocol.py: vendor-neutral value types, frozen dataclasses: KeyValue, KeySchema, RecordIndex, RecordTable (key layout and logical indexes declared once per table), SortOperator (EQ, LT, BEGINS_WITH), SortOrder (ASC, DESC), SortCondition, RecordQuery (partition, sort, index, limit, order), and resolve_query_key (shared by both stores; raises ValueError for an undeclared index or a sort condition on a key without a sort attribute). Every RecordStore method takes table: RecordTable; query(table, spec: RecordQuery) replaces the raw-string signature with no overload; put_if_not_exists drops pk_attribute (guard derived from table.key). gt and between deferred in the SortOperator docstring (between would serve audit's unimplemented end_time), which also records how begins_with lowers on Azure Table/Firestore (range), Cosmos (STARTSWITH) and Postgres (LIKE).
- Shape decided after industry research (Go CDK docstore binds the key layout per collection; docstore, Dapr, Firestore and Spring express direction as ASC/DESC; none repeat key names per query).
- infrastructure/records/in_memory.py: InMemoryRecordStore moved out of the test tree, keyed by each table's full key: put overwrites, put_if_not_exists guards the full key, delete of a missing item succeeds (matches DeleteItem), missing key attributes are a permanent error, queries honour sort conditions, order, limit and sparse indexes. infrastructure/records/__init__.py exports the value types.
- infrastructure/records/service.py: query builds #pk/#sk placeholders with ExpressionAttributeNames (reserved words like timestamp are safe), maps logical index to physical_name, order to ScanIndexForward, limit to PaginationConfig and truncates to it. Bug fix: limit was only a per-page size, so audit, sync recent runs and the correlation lookup returned every match; it is now a total cap.
- Callers migrated (all 14 RecordStore call sites, six of them queries): infrastructure/audit/service.py (AUDIT_TABLE with by_user and by_correlation indexes; start_time docstring corrected to the actual exclusive upper bound), packages/access/request/store.py (ACCESS_REQUESTS_TABLE; docstring named the wrong table), packages/access/sync/store.py (SYNC_RUNS_TABLE), packages/access/sync/job_status_store.py (JOB_STATUS_TABLE). No import-linter entries added.
- Tests: new tests/unit/infrastructure/records/test_records_query_spec.py, tests/integration/infrastructure/records/test_records_store_query_conformance.py (21 cases parametrized over the fake and moto, GSI with a timestamp sort attribute in conftest.py), tests/unit/packages/access/request/test_access_request_store_queries.py, tests/unit/packages/access/sync/test_access_sync_run_store_recent.py; DynamoDB unit query tests rewritten; audit query tests now assert behaviour over the fake; fake unit tests pin fake-only behaviour; test-tree fake deleted.

TDD: tests were written first and failed with ModuleNotFoundError: No module named 'infrastructure.records.in_memory' before the production change.

Evidence (from app/)
- uv run ruff check . -> All checks passed!
- uv run lint-imports -> Contracts: 10 kept, 0 broken.
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 48 errors in 19 files; 0 in touched files (all pre-existing elsewhere).
- uv run pytest tests --ignore=tests/smoke -> 4676 passed.
- uv run pytest tests/integration/infrastructure/records -> 43 passed (21 shared cases x 2 stores + 1 DynamoDB-only round-trip).
- AC4: rg KeyConditionExpression|ExpressionAttributeValues|key_condition|expression_values|pk_attribute over the records package, audit, access and their tests -> only infrastructure/records/service.py, its unit tests and the vocabulary assertion in test_records_query_spec.py.

Left for the human: code review. Behaviour changes to call out in the PR: limit is a total cap; the fake is keyed by the full key. Table names, Terraform and settings are unchanged.

Review follow-up (PR #1584)
- MAX_QUERY_LIMIT (100) moved from infrastructure/audit/service.py to infrastructure/audit/protocol.py: it is a documented contract bound of the audit reads, now owned by the Protocol (defaults and docstrings reference it).
- decisions/cloud-portability.md: the line naming RecordStore.query(key_condition: str) as the counterexample now describes the landed RecordQuery/RecordTable shape; changelog entry added.
- Table names moved from code to settings (reviewer decision: hardcoded table names are an anti-pattern). New infrastructure/audit/settings.py (AUDIT_TABLE_NAME); access settings gain requests.table_name (ACCESS_REQUESTS_TABLE_NAME), sync.table_name (ACCESS_SYNC_TABLE_NAME) and sync.job_status_table_name (ACCESS_SYNC_JOB_STATUS_TABLE_NAME). Defaults are today's tables, so no Terraform or SSM change. Repositories take table_name; each module exposes <name>_table(name) -> RecordTable with the key layout in code; providers pass the configured name. Access request README notes the setting.
- Tests: new tests/unit/infrastructure/audit/test_audit_settings_table_name.py and tests/unit/packages/access/common/test_access_settings_table_names.py (defaults, env overrides, provider-built repositories write to the configured table over the in-memory store); existing constructor call sites updated.
- Still hardcoded, outside this PR: infrastructure/idempotency/dynamodb.py IDEMPOTENCY_TABLE, features/incident/core/adapters/{legacy_incidents,status_updates}.py (direct boto3; move with TASK-145.5), bin/unlock-sync-job.sh, frozen modules/.
- Gates after the follow-up (from app/): ruff check . -> All checks passed!; lint-imports -> 10 kept, 0 broken; mypy -> 48 errors in 19 files, 0 in touched files; pytest tests --ignore=tests/smoke -> 4685 passed.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-24 20:11
---
2026-09-24 citation fix: decisions/layers.md, capability-packages.md and events.md were deleted and replaced by decisions/plugin-architecture.md (six layers: server, features, capabilities, infrastructure, integrations, contracts). Read those references in this task as plugin-architecture.md. Path A infrastructure capabilities are now split: hosting contracts (storage, coordination, queue, secrets) live in app/contracts/ with implementations in app/infrastructure/; workplace systems and shared business engines live in app/capabilities/. Path B adapters are unchanged (outbound-clients.md). After this slice the StorageService Protocol moves to app/contracts/ (TASK-108).
---

created: 2026-10-13 17:30
---
Plan review proposals (not applied). (1) AC4 is unachievable as written: KeyConditionExpression/ExpressionAttributeValues also appear in infrastructure/resilience/retry/dynamodb_store.py, infrastructure/idempotency/dynamodb.py, features/incident/core/adapters/{status_updates,legacy_incidents}.py and modules/slack/webhooks.py, none of which use RecordStore. Suggested wording: 'No RecordStore Protocol signature, fake or RecordStore caller contains a DynamoDB expression string; within the records package they appear only in records/service.py and its tests.' (2) Add an AC: 'limit is a total cap on returned items in both the fake and the DynamoDB store (today Limit is a per-page size and every page is aggregated)'. (3) AC2 and the description cite decisions/layers.md; read as decisions/plugin-architecture.md.
---
<!-- COMMENTS:END -->

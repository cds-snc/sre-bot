---
id: TASK-58.1
title: >-
  Move the conditional-write Protocol into contracts/coordination and its
  implementations into infrastructure/coordination
status: Done
assignee: []
created_date: '2026-10-14 17:45'
updated_date: '2026-10-14 18:31'
labels:
  - infrastructure
  - reliability
  - plugin-architecture
milestone: m-7
dependencies:
  - TASK-102
parent_task_id: TASK-58
priority: medium
ordinal: 380000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-58 (Stack C layer 2). Mechanical move and rename, no behaviour change. The old app/infrastructure/idempotency/ path is deleted outright, with no shim or re-export.

Decided 2026-10-14 (human, TASK-58 split approval):
- IdempotencyStore becomes ConditionalWriteStore in app/contracts/coordination/ (store.py plus an __init__.py re-exporting the surface), with ClaimResult and ClaimOutcome. TASK-102's claim_token and ownership-checked complete/release carry over unchanged. The DynamoDB own-replay branch stays inside the adapter, off the Protocol.
- The DynamoDB store, the in-memory fake (still in an in_memory.py module), factory, settings and lease.py move to app/infrastructure/coordination/. Both store classes keep explicitly subclassing ConditionalWriteStore, so make check-fake-coverage stays green with no baseline change.
- The settings class becomes ConditionalWriteSettings; the IDEMPOTENCY_* environment variable names stay (deploy interface). The DynamoDB table sre_bot_idempotency and its key are not renamed: no data migration.
- get_idempotency_store and reset_idempotency_store are renamed here, keeping this slice mechanical; TASK-58.2 deletes them.
- Consumers (Access Sync job_runner, ingress, platform_lock, providers; jobs/scheduled_tasks) move to the new paths and stay on provider functions. Nothing is registered in a registry (TASK-109 has not merged).
- import-linter: the ingress and job_runner ignore entries are removed. The platform_lock and providers entries are re-pointed to infrastructure.coordination: platform_lock's is removed by TASK-58.2, providers' by TASK-124.1 (Access Sync moves to features/).
- The conformance fixture mapping and its enrollment test (TASK-27.3) move to tests/integration/infrastructure/coordination/, mirroring TASK-108's records move.
- Accepted as one PR although it touches about 18 production files: nearly all are moves and import-line edits, as in TASK-108, and splitting it would leave an intermediate state that does not import.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ConditionalWriteStore, ClaimResult and ClaimOutcome live in app/contracts/coordination/ and import only the standard library and contracts; the DynamoDB and in-memory classes live in app/infrastructure/coordination/, explicitly subclass it, and behave exactly as after TASK-102 (the conformance suite passes unchanged on both)
- [x] #2 No infrastructure.idempotency import path remains (a test asserts importlib.util.find_spec('infrastructure.idempotency') is None); no alias or shim is left behind
- [x] #3 The conformance fixture mapping and enrollment test live in tests/integration/infrastructure/coordination/; make check-fake-coverage and lint-imports pass, with the ingress and job_runner ignore entries removed and the platform_lock and providers entries naming the task that removes them
- [x] #4 The table sre_bot_idempotency, its key and the IDEMPOTENCY_* environment variable names are unchanged
- [x] #5 decisions/ cross-references to the old module path are updated in the same PR: reliability.md (the lease.py path and the Migration line), lifecycle.md, plugin-architecture.md and feature-packages.md
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SCOPE
Layer 2 of Stack C, after TASK-102 (committed first; this plan is written against the working tree that includes it). Pure move and rename: no behaviour change, no new behaviour tests. The old app/infrastructure/idempotency/ package is deleted outright, no shim or re-export. Out of scope: facades, ClaimResult.INDETERMINATE, the read-failure policy enum and facade names (TASK-58.2); registry registration (TASK-109); deleting get/reset singletons (58.2).

DESIGN DECISIONS
D1. Names. IdempotencyStore -> ConditionalWriteStore (ClaimResult, ClaimOutcome keep their names). DynamoDBIdempotencyStore -> DynamoDBConditionalWriteStore; InMemoryIdempotencyStore -> InMemoryConditionalWriteStore. IdempotencySettings -> ConditionalWriteSettings; get_idempotency_settings -> get_conditional_write_settings. Constructor kwarg idempotency_settings -> settings (every call site is already edited for its import). Factory: get_idempotency_store -> get_conditional_write_store, build_idempotency_store -> build_conditional_write_store, reset_idempotency_store -> reset_conditional_write_store. lease.py keeps acquire_lease, release_lease, get_lease_store, run_if_leased with unchanged bodies; only imports and type hints change.
D2. Unchanged on purpose: IDEMPOTENCY_* env names and their Field aliases, table sre_bot_idempotency, key idempotency_key (constants IDEMPOTENCY_TABLE and PARTITION_KEY keep their values), log event names. Only the structlog component binds change: idempotency.dynamodb -> coordination.dynamodb, idempotency.factory -> coordination.factory. Assumes no dashboard or alert filters on those component values (verify: rg the repo and terraform; operators to confirm for external log queries).
D3. Contract package. contracts/coordination/store.py holds the Protocol, ClaimResult, ClaimOutcome, with the TASK-102 ownership docstrings carried over (docstrings say ConditionalWriteStore). contracts/coordination/__init__.py re-exports the three names with __all__, as contracts/records/__init__.py does. It imports only stdlib; no logging or third-party import.
D4. infrastructure/coordination/__init__.py: re-exports as the old __init__ did (implementations, factory functions, lease helpers, settings), but no longer re-exports the contract names (no re-export of contracts from infrastructure); consumers import ConditionalWriteStore, ClaimResult, ClaimOutcome from contracts.coordination. Its docstring usage example is updated to the new names and imports.
D5. Own-replay branch stays inside DynamoDBConditionalWriteStore.claim, not on the Protocol (claim body untouched).
D6. Fake coverage. check_fake_coverage treats a contracts/ Protocol as a hosting contract when an infrastructure class explicitly subclasses it, and requires an in_memory.py class that does too. Both new classes subclass ConditionalWriteStore imported from contracts.coordination, and the fake stays infrastructure/coordination/in_memory.py. Baseline file needs no edit (no idempotency entry exists).
D7. import-linter (app/pyproject.toml, contract no-host-imports): remove "packages.access.sync.interactions.ingress -> infrastructure.idempotency" (:288) and "packages.access.sync.job_runner -> infrastructure.idempotency" (:290): both now import only contracts.coordination. Re-point "...platform_lock -> infrastructure.idempotency" (:291) and "...providers -> infrastructure.idempotency" (:295) to infrastructure.coordination (platform_lock still imports acquire_lease/release_lease; providers still imports build_conditional_write_store). Extend the shrink-only comment (:265-266) the way TASK-108 did: approved entries named with their remover, platform_lock -> infrastructure.coordination removed by TASK-58.2, providers -> infrastructure.coordination removed by TASK-124.1. unmatched_ignore_imports_alerting=error makes stale entries fail, so lint-imports proves the list.

FILE MOVES (human runs git; the agent creates the targets as plain file moves and edits them, renames are detected at commit). Source -> target, all under /workspace/app:
Production
- infrastructure/idempotency/protocol.py -> contracts/coordination/store.py
- (new) contracts/coordination/__init__.py
- infrastructure/idempotency/dynamodb.py -> infrastructure/coordination/dynamodb.py
- infrastructure/idempotency/in_memory.py -> infrastructure/coordination/in_memory.py
- infrastructure/idempotency/factory.py -> infrastructure/coordination/factory.py
- infrastructure/idempotency/settings.py -> infrastructure/coordination/settings.py
- infrastructure/idempotency/lease.py -> infrastructure/coordination/lease.py
- infrastructure/idempotency/__init__.py -> infrastructure/coordination/__init__.py
- infrastructure/idempotency/ directory removed (including __pycache__)
Tests, integration (mirrors tests/integration/infrastructure/records/)
- tests/integration/infrastructure/idempotency/__init__.py -> tests/integration/infrastructure/coordination/__init__.py
- .../idempotency/conftest.py -> .../coordination/conftest.py (IDEMPOTENCY_STORE_FIXTURES -> CONDITIONAL_WRITE_STORE_FIXTURES, fixtures renamed conditional_write_store*, STORE_TEST_TABLE_NAME and the moto table schema unchanged)
- .../idempotency/test_idempotency_store_conformance.py -> .../coordination/test_coordination_store_conformance.py
- .../idempotency/test_idempotency_store_conformance_enrollment.py -> .../coordination/test_coordination_store_conformance_enrollment.py
Tests, unit contract
- tests/unit/infrastructure/idempotency/test_idempotency_store_protocol.py -> tests/unit/contracts/coordination/test_coordination_store_protocol.py (+ __init__.py)
- (new) tests/unit/contracts/coordination/test_coordination_contracts_imports.py
Tests, unit infrastructure (tests/unit/infrastructure/idempotency/ -> tests/unit/infrastructure/coordination/, bodies kept, imports and renamed symbols edited)
- __init__.py
- test_dynamodb_store.py -> test_coordination_dynamodb_store_operations.py
- test_idempotency_dynamodb_ownership.py -> test_coordination_dynamodb_ownership.py
- test_in_memory_store.py -> test_coordination_in_memory_store_operations.py
- test_lease.py -> test_coordination_lease_helpers.py
- test_factory.py -> test_coordination_store_factory.py
- test_idempotency_settings.py -> test_coordination_settings.py
- test_idempotency_legacy_stack_contract.py: not moved; replaced by (new) tests/unit/infrastructure/coordination/test_coordination_legacy_path_removed.py (see TDD step 1) and the old file deleted.

TDD STEPS
1. Write the failing tests first (red = ImportError/ModuleNotFoundError or failed assertion).
   a. tests/unit/contracts/coordination/test_coordination_contracts_imports.py, mirroring the records test: contracts.coordination.__all__ == {"ConditionalWriteStore","ClaimResult","ClaimOutcome"}, every name resolves, and an AST scan of the package shows only stdlib and contracts imports.
   b. tests/unit/infrastructure/coordination/test_coordination_legacy_path_removed.py: importlib.util.find_spec("infrastructure.idempotency") is None, plus the two legacy cache/service module names stay absent (kept from the old legacy-stack-contract test); infrastructure.coordination does not export the contract names (no re-export).
   c. Moved conformance suite and enrollment test in tests/integration/infrastructure/coordination/ importing from contracts.coordination and infrastructure.coordination, parametrized over both implementations, bodies otherwise unchanged. The enrollment test compares CONDITIONAL_WRITE_STORE_FIXTURES with concrete_production_subclasses(ConditionalWriteStore).
   d. Moved unit tests and Protocol shape test with new import paths. These carry TASK-102's ownership assertions unchanged (claim_token on NEW only, foreign-token release/complete refused, release never deletes COMPLETED, stale holder refused).
   e. Edit test_bin_fake_coverage_check.py (below). Confirm red.
2. Create contracts/coordination/ (store.py, __init__.py) per D1/D3.
3. Create infrastructure/coordination/ files per D1, D2, D4; edit class names, imports, settings class, factory function names, kwarg rename, component binds. Delete infrastructure/idempotency/.
4. Migrate consumers (call sites below), edit pyproject (D7), edit decisions (below).
5. Green run, then the gates.

CALL-SITE EDITS (app/ relative)
- packages/access/sync/job_runner.py:27 `from infrastructure.idempotency import IdempotencyStore` -> `from contracts.coordination import ConditionalWriteStore`; annotations :58, :141, :252, :300 -> ConditionalWriteStore. Import order kept ruff-clean.
- packages/access/sync/interactions/ingress.py:18 same import change; annotations :57, :141.
- packages/access/sync/platform_lock.py:5 split into `from contracts.coordination import ConditionalWriteStore` and `from infrastructure.coordination import acquire_lease, release_lease`; annotations :20, :42.
- packages/access/sync/providers.py:5 -> `from contracts.coordination import ConditionalWriteStore` plus `from infrastructure.coordination import build_conditional_write_store`; :25 return annotation; :27 call.
- jobs/scheduled_tasks.py:12 -> `from infrastructure.coordination import get_lease_store, run_if_leased` (usage at :84 and :87 unchanged).
- packages/access/sync/job_status_store.py:21 comment "infrastructure/idempotency" -> "infrastructure/coordination".
- Not edited: packages/access/common/settings.py:64,73 and job_status_store.py:22 (table name and key unchanged, AC4); bin/db.sh:28, bin/unlock-sync-job.sh:6,14,15 (table name only, no module path); terraform/iam.tf:57, dynamodb.tf:103-112,265 (table only). Verified no IDEMPOTENCY_* var in terraform, .github or Makefile.
- Test import edits: tests/unit/jobs/test_scheduled_tasks.py:12, :238, :253, :272, :392; tests/unit/packages/access/sync/test_platform_lock.py:11-19; test_access_sync_routes.py:11, :65-67; test_access_sync_ingress_lock_token.py:13, :26-28 (settings kwarg is now settings=); test_providers.py:94, :127 patch target -> packages.access.sync.providers.build_conditional_write_store (check mocked return values/lines nearby); tests/unit/infrastructure/configuration/test_settings_structure.py:46, :173; test_settings_delegation.py:33, :54, :74; tests/unit/infrastructure/logging/test_settings.py:3 docstring path; tests/integration/conftest.py:130 key "idempotency.IDEMPOTENCY_TTL_SECONDS" unchanged (env names stay) but confirm it is not an import path.
- tests/unit/bin/test_bin_fake_coverage_check.py:206-209 synthetic tree -> contracts/coordination/store.py (PROTOCOL_SOURCE name ConditionalWriteStore) plus infrastructure/coordination/dynamodb.py-style implementer and in_memory.py fake importing from contracts.coordination, so the test exercises the contracts rule; keep the test name accurate if it asserted the infrastructure-location rule (re-check the neighbouring tests and keep one that still covers a Protocol defined under infrastructure/ using another name); :325 docstring; :330 assertion -> "contracts/coordination/store.py:ConditionalWriteStore" not in current.
- Final sweep: rg -n "infrastructure[./]idempotency|IdempotencyStore|IdempotencySettings|get_idempotency|build_idempotency|reset_idempotency|idempotency_settings" app (excluding .venv) must return nothing except legitimate table/key/env strings.

DECISIONS EDITS (AC5)
- decisions/reliability.md:16 "is being renamed to a coordination-shaped ConditionalWriteStore with idempotency and leasing as thin facades (TASK-58)" -> states the Protocol is ConditionalWriteStore in contracts/coordination implemented in infrastructure/coordination, facades follow in TASK-58.2.
- reliability.md:32 lease-helper sentence: IdempotencyStore.claim/release -> ConditionalWriteStore.claim/release, build_idempotency_store -> build_conditional_write_store, path -> app/infrastructure/coordination/lease.py. Keep the "never reimplement" clause.
- reliability.md:49 Migration: drop the tolerated "idempotency-named module path and its lease.py home (renamed by TASK-58)"; keep the tolerated "features importing infrastructure.coordination directly instead of resolving the contract from the registry"; ticket list entry for TASK-58 adjusted; add a Decision log entry dated 2026-10-14 (path rename, class names, env names and table unchanged). reliability.md:12/18/22 use "idempotency" as the use-case name and stay.
- decisions/lifecycle.md:20 and :80 "from the idempotency store" -> "from the coordination contract" (line 73 TASK-58 ticket text checked).
- decisions/plugin-architecture.md:13 hosting adapters list: "idempotency" -> "coordination".
- decisions/feature-packages.md:84 example `IdempotencyStore` -> `ConditionalWriteStore`.
- cloud-portability.md: grep shows no module path or class name; untouched (verify).

TEST MATRIX
Unchanged behaviour is proven by the existing suites at their new locations: conformance on both stores (happy: owner release/complete; boundary: expired-not-taken-over release, replayed complete; failure/ownership: stale holder, wrong token, release never deletes COMPLETED), Stubber-based DynamoDB ownership tests (condition expressions, False mapping, RuntimeError on classified error, unclassified propagation), in-memory unit tests, lease helper tests, Access Sync tests. New tests: contracts import surface, legacy path removed, no contract re-export, fake coverage on the contracts rule. No new behaviour is added so none is tested.

AC TRACEABILITY
AC1: steps 1a, 1c, 1d, 2, 3 (tests: test_coordination_contracts_imports.py, test_coordination_store_conformance.py both params, test_coordination_store_protocol.py, enrollment test). AC2: steps 1b, 3 (test_coordination_legacy_path_removed.py, final rg sweep). AC3: steps 1c, 1e, 4, D6, D7 (enrollment test, test_bin_fake_coverage_check.py, make check-fake-coverage, lint-imports). AC4: D2 and the not-edited list (test_coordination_settings.py asserts the IDEMPOTENCY_* aliases and defaults 3600/300 unchanged; test_coordination_dynamodb_store_operations.py asserts default table name sre_bot_idempotency and key idempotency_key). AC5: decisions edits above, checked by rg over decisions/.

ASSUMPTIONS AND DOUBTS
- TASK-102 is committed before this branch is cut; verify git state at start (uncommitted idempotency edits must already be in main).
- Env aliases survive a class rename because each Field sets alias explicitly; verify with test_coordination_settings.py and test_settings_structure.py (the latter may list settings classes by name or by env-file key: check it for string names).
- test_settings_structure.py:173 and integration/conftest.py:130 might key on a settings-attribute name "idempotency" in a root aggregator; verify with rg infrastructure/configuration (earlier grep found only a docstring at base.py:38).
- Import cycle: infrastructure/coordination/__init__.py importing lease and factory as before; verify no cycle with contracts (contracts imports nothing from app).
- mypy: explicit subclassing of the Protocol continues to type-check; check Stubber unit tests still type.
- The old tests/unit/infrastructure/idempotency/__pycache__ and the old directory must be gone, or find_spec can still see a namespace package; confirm the directories are deleted, not just emptied.
- Log component rename (D2) may affect external queries.

GATES (from app/)
uv run ruff check . ; uv run ruff format --check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' (0 errors in touched files, repo-wide errors elsewhere ignored); uv run pytest tests --ignore=tests/smoke ; make check-fake-coverage (expect OK with 6 baselined gaps, no baseline edit) ; uv run lint-imports (expect fewer ignores, 0 broken, no unmatched-ignore error). Record outputs in notes.

BLAST RADIUS AND ROLLBACK
Touches the Access Sync lock path and the three Tier-2 scheduler leases (import paths only). A wrong import fails at import time and is caught by app startup and tests, not silently at runtime. No data, schema, terraform or env change. One git revert restores everything. Ordering: TASK-102 first; TASK-58.2 and TASK-124.1 depend on the renamed paths and are the named removers of the re-pointed ignore entries. Open TASK-64 and TASK-65 work only needs their import line adjusted.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per the approved plan; no deviations in behaviour or scope.
Created: app/contracts/coordination/{__init__,store}.py; app/infrastructure/coordination/{__init__,dynamodb,in_memory,factory,settings,lease}.py; tests under tests/unit/contracts/coordination (imports + protocol), tests/unit/infrastructure/coordination (dynamodb ops, ownership, in-memory, lease, factory, settings, legacy_path_removed), tests/integration/infrastructure/coordination (conftest, conformance, enrollment). Deleted app/infrastructure/idempotency/ and both old test dirs entirely (incl. __pycache__).
Edited: job_runner, ingress, platform_lock, providers, job_status_store (comment), jobs/scheduled_tasks, app/pyproject.toml (ingress and job_runner ignores removed; platform_lock and providers re-pointed to infrastructure.coordination; shrink-only comment names TASK-58.2 and TASK-124.1), the consumer tests, test_bin_fake_coverage_check.py, decisions/{reliability,lifecycle,plugin-architecture,feature-packages}.md.
Small additions: the failed_to_read_idempotency_key warning now carries key and operation; factory build logs a debug event with in_progress_ttl_seconds. Log event names and error-message strings unchanged. Structlog components now coordination.dynamodb and coordination.factory (rg of repo found no dashboard or alert filter on the old values; external log queries unverified).
Test notes: legacy-path test checks find_spec('infrastructure.idempotency') is None and cache/service absent under infrastructure.coordination only (find_spec on an old-path submodule raises ModuleNotFoundError because the parent is gone). Fake-coverage test: the old idempotency synthetic test was replaced by an infrastructure-defined (AuditTrailService) case plus two contracts/coordination cases (passes with subclassing fake, violation without).
Gates (from app/): ruff check: All checks passed! | ruff format --check: 910 files already formatted | pytest tests --ignore=tests/smoke: 4838 passed, 2627 warnings in 100.71s (no SNS/google-directory order failures seen) | make check-fake-coverage: OK: every covered Protocol has an in-memory fake (6 baselined gap(s) remain) | lint-imports: Contracts: 10 kept, 0 broken (no unmatched-ignore error) | mypy: Found 48 errors in 19 files, all pre-existing under modules/ (webhooks, incident, role); 0 errors in touched files. Final rg sweep for old names returned nothing.

Layer discovery (2026-10-14, human-approved): decisions/plugin-architecture.md amended in this PR. contracts/ may hold pure, I/O-free @final facades over its own Protocols under five criteria (no I/O, stdlib/typing/contracts imports only, shared semantics, tested against the fake and conformance suite, public API); orchestration stays in server/. The risk mitigation, a review check and a 2026-10-14 change entry were added. First users: LeaseStore and IdempotencyStore in TASK-58.2. TASK-100 descriptions and references re-pointed to infrastructure/coordination.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-14 17:54
---
2026-10-14 (human): plan approved. The constructor parameter is settings. Log component binds are renamed to coordination.*; any change that adds debugging context to these log events (key, operation, table) is welcome.
---
<!-- COMMENTS:END -->

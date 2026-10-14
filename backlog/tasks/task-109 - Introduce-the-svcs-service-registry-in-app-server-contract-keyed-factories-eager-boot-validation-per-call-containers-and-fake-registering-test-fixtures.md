---
id: TASK-109
title: >-
  Introduce the svcs service registry in app/server/: contract-keyed factories,
  eager boot validation, per-call containers and fake-registering test fixtures
status: Done
assignee: []
created_date: '2026-09-24 19:58'
updated_date: '2026-10-14 19:25'
labels:
  - plugin-architecture
  - dependency-injection
milestone: m-7
dependencies:
  - TASK-108
  - TASK-58
  - TASK-58.2
  - TASK-92
references:
  - decisions/dependency-injection.md
  - decisions/lifecycle.md
  - decisions/testing.md
  - 'https://svcs.hynek.me/'
priority: high
type: feature
ordinal: 251000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/dependency-injection.md replaces cached module-level provider functions with a type-keyed svcs registry. This is the "separate ticket, still to create" its Migration names. It supersedes TASK-29 (an lru_cache @provider registry with a global cache-clearing fixture), which built the pattern the record now replaces.

Decision points implemented here:
- At startup app/server/ registers one factory per contracts Protocol (records, coordination to start). The Protocol is the key; the concrete class appears only in the host's registration code.
- Eager validation: lifespan resolves every registered service once from a startup container. The boot check is construction plus static validation of the settings slice, with no network I/O (decisions/dependency-injection.md, lifecycle.md phase 2). A missing setting or a failing constructor aborts boot before yield. A factory may register an svcs ping for diagnostics; pings never run at boot or behind the platform health checks.
- HTTP routes use the svcs FastAPI integration (DepContainer, await services.aget(Protocol)).
- Slack handlers, webhook consumers and jobs open a container per invocation and close it when the invocation ends.
- Only entry points touch a container. Services receive their dependencies through their constructor.
- Tests build a registry and register Protocol-conforming fakes. No test clears global caches.
- Adds the import-linter forbidden contract "nothing outside server/ imports provider modules or infrastructure implementations", seeded with today's violations as ignore entries.

Out of scope: moving each consumer off its infrastructure get_* provider. Each package does that when it moves to app/features/ or app/capabilities/, so no package runs half on providers and half on the registry. TASK-92 decided the boot-check rule (2026-09-25): construction and static validation only; no vendor or dependency call at boot or in readiness.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 svcs is a runtime dependency (app/pyproject.toml and uv.lock); app/server/services.py registers a factory for RecordStore and ConditionalWriteStore, and concrete class names appear only there (AST test)
- [x] #2 A registered factory that raises aborts lifespan before yield, and lifespan phase 2 runs before plugin loading (boot tests)
- [x] #3 A route on a test app resolves a service through svcs.fastapi.DepContainer, and a Slack-style handler and a job-style function each resolve through a per-invocation container that is closed afterwards, including when they raise; no production caller resolves from the registry in this task
- [x] #4 tests/fixtures/service_registry.py registers the in-memory fakes under the contracts Protocol keys; no new test clears a cache for a registry-resolved service
- [x] #5 Import-linter contract (k) forbids infrastructure.records and infrastructure.coordination outside server/, seeds the current violations as ignore entries that each name their removing task, and has unmatched_ignore_imports_alerting = error
- [x] #6 dependency-injection.md Migration and Changes record the registry for records and coordination; testing.md (Substitution and the provider-clearing tolerance) and lifecycle.md Migration match; ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
- [x] #7 Boot test: with static AWS credentials and the instance metadata endpoint disabled, resolving every registered service opens no outbound connection (socket.connect spy); the ambient-credential case is TASK-149
- [x] #8 Contract (b)'s shrink-only comment names no TASK-145.5/TASK-109 exception; if TASK-145.5 landed first with a get_record_store ignore entry, that wiring resolves RecordStore from the registry and the entry is removed
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SCOPE
Layer 4 (last) of Stack C, after TASK-58.2. Adds svcs as a runtime dependency. Creates app/server/services.py, which registers RecordStore and ConditionalWriteStore by contract. Runs lifecycle phase 2 (resolve every registered service once: construction only, no network I/O) in the lifespan, before plugin loading. Converts the lifespan to svcs.fastapi.lifespan so HTTP routes can take svcs.fastapi.DepContainer. Adds a fake-registering test fixture. Adds import-linter contract (k) for provider modules, seeded with today's violations.

No consumer moves off its get_* provider: each package moves with TASK-124.x, TASK-64 or TASK-37.2. No facade is registered.

Out of scope:
- lease TTL on the call (TASK-148);
- network-free ambient credential resolution (TASK-149);
- svcs pings;
- registering other contracts (directory, events, i18n, drive, security);
- deleting providers;
- the audit move (TASK-122);
- TASK-145.5.

Runtime behaviour is unchanged for every existing route, Slack handler and job. The only new boot work is building one RecordStore and one ConditionalWriteStore.

DECISIONS (human, 2026-10-14)
- Registry holds the primitive only: RecordStore and ConditionalWriteStore, at the settings-default in-progress TTL. Consumers build LeaseStore and IdempotencyStore with their own read-failure policy, following dependency-injection.md's feature-local wiring. TASK-37.2 builds IdempotencyStore(FAIL_CLOSED) over the resolved store, and TASK-100 flips only the lease's policy at its construction site. Facade registration and a LeaseStoreFactory contract were rejected.
- Lease TTL stays a construction parameter here. TASK-148 moves it onto the claim call, ahead of TASK-124.1 and TASK-64. Until then build_lease_store and get_lease_store remain for non-default TTLs.
- Lifetime is a singleton through a closure built inside register_core_services, with no module-level cache.
- Credentials: building a boto3 client with only ambient credentials contacts the instance-metadata endpoint. The no-network boot test, and tests/api, therefore set static AWS credentials plus AWS_EC2_METADATA_DISABLED=true. TASK-149 removes that workaround and establishes ECS behaviour.
- Contract (k) uses the strict reading: every source outside server/, packages and features included, even where that duplicates contract (b) entries. Each seed names its removing task.

DESIGN
D1. Dependency. app/pyproject.toml [project].dependencies gains "svcs>=26.2". 26.2.0 adds get_registry and DepRegistry; PyPI 2026-08-24; Python >=3.10. uv.lock is regenerated and make lock-check passes.

D2. Registration module. New server/services.py.
- A module constant CORE_SERVICES is a tuple of frozen-dataclass entries (contract: type, factory: Callable[[], object]). It is the one table that registration and the boot check both iterate, because svcs cannot enumerate its registrations.
- register_core_services(registry: svcs.Registry, services=CORE_SERVICES) -> None calls registry.register_factory(entry.contract, entry.factory) for each entry.
- Concrete classes (DynamoDBRecordStore, DynamoDBConditionalWriteStore) are imported and named only here (AC1).
- Factories are sync, because jobs on scheduler threads use the sync Container.get. They take no arguments and make no network call.

D3. Lifetime. A private helper _once(build) returns a factory that builds on its first call and returns that instance afterwards. Each registration gets its own helper instance, created inside register_core_services, so a new registry builds fresh instances and tests clear nothing. This keeps today's lru_cache lifetime (one client per process) and avoids building a boto3 client and resolving credentials on every request.

D4. Factories.
- RecordStore: DynamoDBRecordStore(get_aws_client("dynamodb")).
- ConditionalWriteStore: DynamoDBConditionalWriteStore(get_aws_client("dynamodb"), settings=get_conditional_write_settings()).
- Settings come from the existing settings singletons.
- infrastructure/coordination/factory.py and infrastructure/records get_record_store stay untouched for the consumers still on providers.

D5. Boot check. async def initialize_core_services(registry, logger, services=CORE_SERVICES) -> None, in server/services.py.
- It registers the services, then resolves each entry: async with svcs.Container(registry) as container, then await container.aget(entry.contract).
- A raising factory propagates, so the lifespan aborts before yield (AC2).
- It logs phase="core_services": one event per service, naming the contract, and one on completion. No secrets.
- No ping is registered.

D6. Lifespan (server/lifespan.py).
- Replace @asynccontextmanager with @svcs.fastapi.lifespan. The signature becomes async def lifespan(app: FastAPI, registry: svcs.Registry) -> AsyncIterator[None].
- The name lifespan is kept, so server/server.py:14 and every existing async with lifespan(FastAPI()) test are unchanged.
- Call await initialize_core_services(registry, logger) after _list_configs_from_sections (:248) and before _initialize_security_services (:256). Phase 2 precedes plugin loading.
- Drop the unused asynccontextmanager import.

D7. Entry-point convention. No production helper is added.
- HTTP: a services: svcs.fastapi.DepContainer parameter, then await services.aget(Contract).
- Slack handlers and jobs: async with svcs.Container(registry). On scheduler threads, a sync with block and container.get. The registry comes from svcs.fastapi.get_registry(app).
- Only entry points touch a container. Services receive their dependencies through constructors.
- No production caller resolves from the registry in this PR; tests prove the convention with reference entry points.

D8. Test fixture (AC4). New tests/fixtures/service_registry.py, hooked up the same way as the other tests/fixtures modules.
- The service_registry fixture builds svcs.Registry() and registers InMemoryRecordStore and InMemoryConditionalWriteStore under the RecordStore and ConditionalWriteStore keys, overridable per test.
- It yields the registry and closes it afterwards.
- No new test calls cache_clear for a registry-resolved service.

D9. Import-linter contract (k).
- id "no-provider-imports"; name "(k) Nothing outside server imports provider modules or infrastructure implementations"; type forbidden.
- forbidden_modules = ["infrastructure.records", "infrastructure.coordination"]. The other infrastructure families join with their own contract tasks.
- source_modules: every top-level package except server (packages, features, jobs, api, modules, models, utils, integrations, ...), plus the infrastructure subpackages other than records and coordination, listed explicitly. A source of "infrastructure" itself would flag intra-package imports.
- unmatched_ignore_imports_alerting = "error".
- Shrink-only seeds, each with its removing task in the comment:
  - packages.access.request.providers -> infrastructure.records (TASK-124.1)
  - packages.access.sync.providers -> infrastructure.records (TASK-124.1)
  - packages.access.sync.providers -> infrastructure.coordination (TASK-124.1)
  - jobs.scheduled_tasks -> infrastructure.coordination (TASK-64, which moves run_if_leased and deletes _tier2)
  - infrastructure.audit.service -> infrastructure.records (TASK-122)
- Contract (b)'s shrink-only comment (:264-268): drop the TASK-145.5/TASK-109 named exception, since no such entry exists (AC8). Keep the TASK-58.1 -> TASK-124.1 sentence.

D10. Decision records.
- dependency-injection.md: the Migration says the registry exists for records and coordination (boot check, route and invocation convention, fixture, contract (k)). The tolerated list narrows to consumers still on get_* providers and contracts not yet registered. Add a dated Changes entry.
- testing.md: the Substitution paragraph names the service_registry fixture for registry-resolved services. Reword the :45 tolerance "no provider-clearing fixture (blocked on registry)": cache clearing remains only for providers not yet on the registry.
- lifecycle.md: the Migration narrows the "lazy first-call construction" tolerance, since phase 2 is real for records and coordination. Record the ambient-credential gap with TASK-149.

FILE CHANGES (all under /workspace/app; the human runs git)
Production, new:
- server/services.py (D2-D5, ~75 LOC)

Production, edited:
- server/lifespan.py (D6, ~+20/-3)
- pyproject.toml (D1 dependency; D9 contract (k) with seeds; contract (b) comment)
- uv.lock (regenerated)

Docs:
- decisions/dependency-injection.md, decisions/testing.md, decisions/lifecycle.md (D10)

Tests, new:
- tests/fixtures/service_registry.py, plus the conftest hookup
- tests/unit/server/test_server_services_registration.py
- tests/unit/server/test_server_services_entry_points.py
- tests/unit/server/test_server_services_fixture.py
- tests/integration/server/test_lifespan_core_services.py

Tests, edited:
- tests/integration/server/test_lifespan_plugin_loading.py:62 (_stub_startup), test_lifespan_slack_start_log.py:37 and test_lifespan_legacy_slack_commands_registration.py:41: patch server.lifespan.initialize_core_services.
- tests/api/conftest.py: an autouse monkeypatch sets AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and AWS_EC2_METADATA_DISABLED=true, so the real lifespan builds the stores without contacting the metadata endpoint (TASK-149 removes it).

Size gate: about 100 production Python LOC in 7 production, config and doc files, all in one subsystem (server/), with no mechanical-plus-behaviour mix. The gate passes as one PR, and one git revert restores everything.

TDD STEPS
1. Write the failing tests first (red = ImportError or a failed assertion):
   a. test_server_services_registration.py:
      - a fresh svcs.Registry resolves a RecordStore and a ConditionalWriteStore by Protocol key;
      - two containers return the same instance (D3);
      - a new registry builds a new instance;
      - registry.register_value after registration replaces the factory with a fake;
      - an AST scan finds no DynamoDBRecordStore or DynamoDBConditionalWriteStore name in server/ outside services.py.
   b. test_lifespan_core_services.py:
      - AC2: with CORE_SERVICES patched to include a raising factory, async with lifespan(FastAPI()) raises and the body never runs;
      - AC7: with static AWS credentials and AWS_EC2_METADATA_DISABLED=true set by monkeypatch, and socket.socket.connect replaced by a recording spy, initialize_core_services over the real CORE_SERVICES records zero connects;
      - the core_services phase logs before plugin loading starts.
   c. test_server_services_entry_points.py (AC3):
      - a test FastAPI app uses svcs.fastapi.lifespan with register_core_services, and its fakes are registered after startup;
      - a route taking svcs.fastapi.DepContainer resolves RecordStore through await services.aget;
      - a Slack-style handler and a job-style function each open a per-invocation container and resolve a ConditionalWriteStore;
      - a generator-factory cleanup spy shows the container closed after each invocation, including when the handler raises.
   d. test_server_services_fixture.py: the service_registry fixture resolves the in-memory fakes under the Protocol keys, with no cache_clear (AC4).
   e. Edit the three lifespan stubs and tests/api/conftest.py. Confirm the new tests are red.
2. Production code: the svcs dependency (pyproject and lock), then server/services.py, then server/lifespan.py.
3. Add contract (k) with its seeds and run lint-imports until it reports 0 broken and no unmatched-ignore error. Edit the contract (b) comment.
4. Decision records (D10).
5. Run green, then the gates.

CALL-SITE EDITS (app/ relative)
- server/lifespan.py:4: drop the asynccontextmanager import and add import svcs.
- server/lifespan.py:235-236: becomes @svcs.fastapi.lifespan / async def lifespan(app: FastAPI, registry: svcs.Registry) -> AsyncIterator[None].
- server/lifespan.py: the phase-2 call goes after :248-254 and before :256; the yield at :328 is unchanged.
- server/server.py: no edit.
- Consumers: no edit (packages/access/request/providers.py:32, packages/access/sync/providers.py:28,51,57, jobs/scheduled_tasks.py:83-87, infrastructure/audit/service.py:263).
- Final sweep:
  - rg -n "svcs" app --glob '!tests' shows only server/services.py, server/lifespan.py and pyproject.toml;
  - rg -n "DynamoDBRecordStore|DynamoDBConditionalWriteStore" app/server shows only server/services.py.

TEST MATRIX
- Happy: both contracts resolve by Protocol key through the host registration; a route resolves through DepContainer; a handler and a job resolve through per-invocation containers; the fixture registers fakes and resolves them.
- Boundary: a second container returns the same instance; a new registry returns a new instance; a fake registered after startup replaces the real factory.
- Failure: a raising factory aborts the lifespan before yield; resolving an unregistered contract raises ServiceNotFoundError; a handler or job that raises still closes its container.
- No network: the socket.connect spy over initialize_core_services, with static credentials and metadata disabled, sees zero connects.
- Lifecycle order: phase 2 logs before plugin loading.
- Isolation: no new test calls cache_clear for a registry-resolved service.
- Static checks: lint-imports keeps contract (k) with 0 broken and unmatched alerting on; check-runtime-imports passes with svcs declared; check-fake-coverage is unchanged (6 baselined gaps).
- Routes: no production route changes, so no production route tests. The route test is a reference entry point on a test app.

AC TRACEABILITY
- AC1: D1, D2; steps 1a and 2 (registration test, AST concrete-name scan, lock-check).
- AC2: D5, D6; step 1b (raising-factory lifespan test, phase order).
- AC3: D7; step 1c (reference route, handler and job tests with the cleanup spy).
- AC4: D8; step 1d.
- AC5: D9; step 3 (uv run lint-imports).
- AC6: D10, plus the gates.
- AC7: D5; step 1b (socket.connect spy).
- AC8: D9 (the contract (b) comment).

ASSUMPTIONS AND DOUBTS
- Assumes TASK-58.2 and the lower layers are committed on the branch below before implementation starts. Verify git state at start.
- Consumers stay on get_* providers. Verify with the final sweep.
- mypy accepts Protocols as svcs keys without ignores: verified for svcs 26.2.0 with mypy on 3.14. Re-run mypy on the touched files.
- Existing async with lifespan(FastAPI()) tests keep working, because svcs.fastapi.lifespan.__call__ is an asynccontextmanager. Verify by running tests/integration/server.
- The decorator's registry is process-global and closed on every exit, and repeated lifespan entries re-register. HTTP-level tests register fakes after startup. Verify in step 1c.
- The infrastructure subpackage source list in contract (k) avoids intra-package false positives. Verify with lint-imports and adjust the list.
- TASK-145.5 is To Do, so no get_record_store ignore entry exists, and AC8 is the comment edit only. If 145.5 lands first and adds an entry, this PR migrates that wiring to the registry and removes the entry.
- At implementation, check whether ECS container-credential resolution at client construction can raise, which would make boot abort on state that changes without a deploy. Record the finding on TASK-149.
- CLAUDE.md names infrastructure/services/providers.py and dependencies.py, which do not exist. Not touched here.

GATES (from app/)
- uv run ruff check .
- uv run ruff format --check .
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)': 0 errors in touched files; repo-wide errors elsewhere are ignored.
- uv run pytest tests --ignore=tests/smoke
- uv run lint-imports: contract (k) kept, 0 broken, no unmatched-ignore error.
- make check-runtime-imports
- make check-fake-coverage: OK, 6 baselined gaps.
- make lock-check

Record the outputs in the implementation notes.

BLAST RADIUS AND ROLLBACK
- This touches the whole app's lifespan. A factory or registry defect aborts boot before yield, by design. A wrong decorator or signature fails at import time or in the existing lifespan tests, not silently.
- Boot now builds one RecordStore and one ConditionalWriteStore, so a deploy-coupled defect surfaces at startup instead of on first use. Ambient credential resolution at boot is the open risk (TASK-149).
- No data, schema, terraform or env change, and no consumer behaviour change.
- The svcs dependency and lock land in this PR, since CI installs with uv sync --locked.
- Later work consumes the registry and removes the seeded entries: TASK-148, then TASK-124.x and TASK-64; also TASK-37.2, TASK-118 and TASK-122.
- One git revert restores everything.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per the approved plan (TDD: the new tests were red on ModuleNotFoundError server.services first).

What changed
- app/pyproject.toml + uv.lock: svcs>=26.2 (26.2.0 installed).
- server/services.py (new): CoreService (frozen dataclass: contract, build); CORE_SERVICES for RecordStore and ConditionalWriteStore (DynamoDB stores, default in-progress TTL); _once gives each registration a lock-guarded build-once factory, so each registry builds its own instances; register_core_services(registry); async initialize_core_services(registry, logger) registers, resolves each contract through a container, logs phase=core_services. The functions read CORE_SERVICES at call time.
- server/lifespan.py: @svcs.fastapi.lifespan, signature (app, registry) -> AsyncGenerator[None]; phase 2 runs after config listing and before security, directory, Slack and plugin loading. The name lifespan is kept, so server.py and existing tests are unchanged.
- pyproject contract (k) no-provider-imports: forbidden infrastructure.records and infrastructure.coordination; sources = every root package except server, plus the infrastructure subpackages other than records and coordination (notifications and operations are leftover directories, not packages, so they are left out). 5 seeds, each naming its remover: access request/sync providers (TASK-124.1, x3), jobs.scheduled_tasks (TASK-64), infrastructure.audit.service (TASK-122). Contract (b)'s comment no longer names the TASK-145.5/109 exception (145.5 has not landed, so no entry existed).
- decisions: dependency-injection.md (In place paragraph, tolerances incl. TASK-148/149, Changes), testing.md (Substitution, tolerance, Changes), lifecycle.md (tolerances, Changes). plugin-architecture.md:122 already states the target check; no edit.

Tests
- New: tests/fixtures/service_registry.py (build_fake_service_registry), service_registry and static_aws_credentials fixtures in tests/conftest.py; tests/unit/server/test_server_services_registration.py (resolution, singleton per registry, new registry new instances, late fake overrides, AST scan for concrete names outside infrastructure/), test_server_services_fixture.py, test_server_services_entry_points.py (route via DepContainer on a test app; Slack-style and job-style per-invocation containers with a generator-cleanup spy, incl. raising; unregistered contract raises ServiceNotFoundError); tests/integration/server/test_lifespan_core_services.py (raising factory aborts before yield; phase 2 before plugin loading; socket.connect spy sees zero connects).
- Edited: the three lifespan stub tests patch server.lifespan.initialize_core_services; tests/api/conftest.py autouses static_aws_credentials; tests/integration/conftest.py app_with_lifespan requests it.
- Finding: with no credential files (as in CI), phase 2's boto3 clients make 2 connects to 169.254.169.254. A temporary connect-spy plugin (scratchpad, not committed) showed 6 test files newly reaching it; after the fixes only tests/integration/jobs/test_scheduled_tasks_integration.py does, and it did so before this change (left alone). Recorded on TASK-149. Locally ~/.aws credentials hide this.

Gates (2026-10-14, from app/)
- uv run ruff check . : All checks passed. ruff format --check: clean after formatting one new test.
- uv run pytest tests --ignore=tests/smoke : 4885 passed.
- uv run mypy . : 48 errors in 19 files, 0 in touched files (same set as layer 3).
- uv run lint-imports : 11 kept, 0 broken; (k) KEPT (5 ignored imports), no unmatched-ignore error.
- make check-runtime-imports : OK. make check-fake-coverage : OK, 6 baselined gaps. make lock-check : Resolved 191 packages.
- Sweep: svcs appears only in server/services.py, server/lifespan.py and pyproject.toml outside tests; the concrete store names appear in server/ only in services.py.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-14 18:02
---
2026-10-14 (human): TASK-109 is the last layer of Stack C (TASK-102 -> TASK-58.1 -> TASK-58.2 -> TASK-109), after the coordination facades. It registers both contracts it names: records (RecordStore) and coordination (ConditionalWriteStore, the primitive TASK-58.1 moves to app/contracts/coordination/). Consumers still move off their get_* providers when their package moves (out of scope here). Note for planning: TASK-58.1 re-points the providers import-linter ignore entry to infrastructure.coordination, removed by TASK-124.1, not by this task.
---

created: 2026-10-14 19:08
---
2026-10-14 (human): plan approved as one PR.
---
<!-- COMMENTS:END -->

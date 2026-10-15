---
id: TASK-145.5.2
title: >-
  Per-invocation service scopes for non-HTTP entry points: a ServiceScopeOpener
  on the Slack and background-job registrars
status: To Do
assignee: []
created_date: '2026-10-14 23:08'
updated_date: '2026-10-15 13:43'
labels:
  - plugin-architecture
  - dependency-injection
  - slack
dependencies: []
references:
  - decisions/dependency-injection.md
  - decisions/plugin-architecture.md
  - app/server/services.py
  - 'https://svcs.hynek.me/en/stable/why.html'
  - 'https://svcs.hynek.me/en/stable/integrations/custom.html'
parent_task_id: TASK-145.5
priority: medium
type: task
ordinal: 388000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer 3 of Stack K (handoff doc-13). decisions/dependency-injection.md:30-33 says Slack and Teams handlers, webhook consumers and jobs open a container per invocation, and only entry points touch a container. TASK-109 built the registry, but a feature cannot reach it: features may not import server/, and the registry only lives on the FastAPI app (svcs.fastapi.get_registry). dependency-injection.md:61 lists per-call containers as in place, which overstates it. TASK-145.5.5 is the first feature consumer; jobs (TASK-145.5.7, TASK-64, TASK-140.11), webhook strategies (TASK-37.x) and approvals (TASK-60) need the same thing.

DECIDED (human, 2026-10-14)
- One role-named Protocol, ServiceScopeOpener, in app/contracts/services/: open() returns a context manager yielding a ServiceResolver (get(contract: type[T]) -> T). svcs stays out of contracts/ (plugin-architecture.md:42); svcs.Container satisfies the resolver structurally.
- Exposed by the Slack registrar (SlackCommandRegistrar and PluginSlackRegistrar) and by BackgroundJobRegistry, so every non-HTTP entry point uses the same mechanism.
- The server implementation in server/ opens an svcs.Container over the app registry per invocation and closes it on exit, including when the handler raises.
- Sync now: registrar handlers and scheduler jobs are sync until TASK-33 (async Bolt), which adds an async variant.
- Handlers are closures built in register(registrar): open a scope, resolve contracts, build services through the feature's provider functions (which take resolved contracts as arguments), call one service method, close the scope. The container is never handed to a service (svcs: resolving at the entry point is dependency injection; resolving in services is service location).
- decisions/dependency-injection.md records the mechanism and fixes the in-place line.

ALTERNATIVE CONSIDERED, kept for a later review
- A host Bolt middleware opens the container per request and places it in the Bolt context (the svcs custom-integration pattern; the resolved-caller precedent in decisions/platform-entrypoints.md:40). Pros: native for block actions and view listeners, no registrar API change. Cons: does not cover background jobs; host-routed commands would need it threaded through CommandPayload (TASK-141 undecided); a second mechanism beside the job one. Revisit if TASK-141 or TASK-33 changes how Slack listeners are registered.

No feature uses it in this slice; a reference test drives a handler and a job through it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/contracts/services/ defines ServiceScopeOpener and ServiceResolver with no svcs import; contracts/ still imports only what plugin-architecture.md allows
- [ ] #2 SlackCommandRegistrar and BackgroundJobRegistry expose the opener, and the server implementation opens one svcs container per invocation and closes it on success and on raise
- [ ] #3 Resolving an unregistered contract through the opener fails with the registry's not-found error; tests use the fake-registering service_registry fixture
- [ ] #4 decisions/dependency-injection.md records the opener, the resolve-then-pass rule and the middleware alternative, and its in-place line is accurate
- [ ] #5 The lifespan injects one opener into the Slack provider and the scheduled-task registry, and in tests a feature-style Slack listener and a job resolve a core contract through it and close their scope
- [ ] #6 lint-imports forbids svcs in contracts/, and a Protocol class such as RecordStore can be passed to ServiceResolver.get without a mypy type-abstract error
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Layer 3 of Stack K. Additive and behaviour-preserving: no feature consumes the opener in this slice. Decisions (human, 2026-10-14) are in the description; this plan fixes how they are built.

Size and gate: about 165 production lines across 12 files (2 new in contracts/services/, 6 Python files with diffs of 5 to 25 lines, pyproject.toml, decisions/dependency-injection.md, decisions/plugin-architecture.md). One subsystem (host wiring and the DI decision record), purely additive, so the gate passes; the file count is just over the limit and is judged acceptable because most diffs are a property or a parameter and two are one-paragraph ADR edits (human, 2026-10-15). One git revert restores the previous behaviour.

Call sites (verified 2026-10-15)
- Protocols that gain `scopes`: app/contracts/slack/registrar.py:18 (SlackCommandRegistrar), app/contracts/scheduler/registry.py:8 (BackgroundJobRegistry).
- Implementations of SlackCommandRegistrar: app/integrations/slack/provider.py:160 (SlackPlatformProvider, set_translator at :348 is the injection precedent), app/server/plugins/slack_registrar.py:20 (PluginSlackRegistrar; built per plugin at app/server/plugins/manager.py:111).
- Implementation of BackgroundJobRegistry: app/jobs/scheduled_tasks.py:29 (_ScheduleBackgroundJobRegistry), built at :117 inside init (:92).
- Host wiring: app/server/lifespan.py:257 (phase 2 builds the registry contents), :262 and :271 (provider created and given its translator), :276-280 (register_feature_integrations, where plugins receive registrars), :117-130 (_start_scheduled_tasks calls scheduled_tasks.init), :304 (its only call site).
- Registry factory home: app/server/services.py (CORE_SERVICES at :43, initialize_core_services at :69).
- Test fakes and callers that change in place: app/tests/factories/slack.py (FakeSlackRegistrar), app/tests/unit/jobs/test_scheduled_tasks.py:198,210,221,325, app/tests/integration/jobs/test_scheduled_tasks_integration.py:33,49,76, app/tests/integration/server/test_lifespan.py:181,185, app/tests/unit/server/test_server_services_entry_points.py (its async Slack-style and job-style functions hand-open containers; they are superseded).
- Other BackgroundJobRegistry fakes (oncall_sync and access/sync tests, test_server_plugins_register_background_jobs.py) never read `scopes`; they stay as they are.
- decisions/dependency-injection.md:61 (in-place line) and :32 (entry-point bullet).

Steps (tests first within each step, TDD)
1. app/contracts/services/scope.py and __init__.py (new). ServiceResolver Protocol: `get[T](self, contract: type[T]) -> T`. ServiceScopeOpener Protocol: `open(self) -> AbstractContextManager[ServiceResolver]`. Imports only contextlib and typing. Docstrings carry the rule: resolve at the entry point, build services from the resolved contracts, never hand the resolver to a service; sync until TASK-33 adds an async variant. (AC 1)
2. app/contracts/slack/registrar.py and app/contracts/scheduler/registry.py: add a read-only `scopes` property returning ServiceScopeOpener to both Protocols. (AC 2)
3. app/server/services.py: add SvcsServiceScopeOpener(registry). `open()` is a @contextmanager that opens `svcs.Container(registry)` per call, yields it as the ServiceResolver, and closes it on exit including when the body raises. The class docstring names it the only place a container is opened for non-HTTP entry points. (AC 2, 3)
4. app/server/plugins/slack_registrar.py: PluginSlackRegistrar.scopes returns the host registrar's `scopes` unchanged. (AC 2)
5. app/integrations/slack/provider.py: `set_scope_opener(scopes)` beside set_translator; the `scopes` property returns it and raises RuntimeError when the host has not set it, so a feature can never get a silent default. Imports contracts only (contract (d)). Also fix the docstring example at :896, whose `from integrations.slack.parser Argument, ArgumentType` is missing `import`. (AC 2)
6. app/jobs/scheduled_tasks.py: _ScheduleBackgroundJobRegistry takes `scopes` in its constructor and exposes it; `init(bot, register_plugin_jobs, scopes)` passes it on. jobs/ imports only the contracts Protocol. (AC 2)
7. app/server/lifespan.py: after phase 2, build one SvcsServiceScopeOpener(registry); call `slack_provider.set_scope_opener(scopes)` before register_feature_integrations (next to set_translator); pass `scopes` through _start_scheduled_tasks into scheduled_tasks.init. No existing log event changes. (AC 5)
8. app/pyproject.toml: add contract (l) "contracts imports no svcs" (type forbidden, source contracts, forbidden svcs; include_external_packages is already on), and set mypy `disable_error_code = ["type-abstract"]` with a comment (mypy rejects a Protocol class passed where type[T] is expected, which `services.get(RecordStore)` does; svcs.Container.get has no such error). The setting is repo-wide (human, 2026-10-15). It is proven in checked code by the entry-point test, which calls the resolver with RecordStore; no scratch module. (AC 1, 6)
9. decisions/dependency-injection.md: rewrite the entry-point bullet at :32 to say Slack and Teams handlers and jobs open a scope with `ServiceScopeOpener.open()` obtained from their registrar (`registrar.scopes`, `registry.scopes`), resolve contracts there, build services through the feature's provider functions from the resolved contracts, and call one service method; the resolver is never given to a service; sync now, async variant with TASK-33; the Protocols live in contracts/services with svcs out of contracts. Add an "Alternative considered" paragraph: a host Bolt middleware that opens the container per request and puts it in the Bolt context, with its pros (native for block actions and view listeners, no registrar API change) and cons (no coverage of jobs, host-routed commands need it threaded through CommandPayload while TASK-141 is undecided, a second mechanism beside the job one), and the revisit trigger (TASK-141 or TASK-33 changing how Slack listeners are registered). Fix the in-place line at :61: the registry, phase 2 and the fixture are in place, the opener and registrar exposure are in place (TASK-145.5.2), and no production route or handler resolves from a container yet (the old text claimed both; no route takes DepContainer outside a reference test). Add a dated Changes entry. (AC 4)
10. decisions/plugin-architecture.md: add contracts/services (ServiceScopeOpener, ServiceResolver; no svcs) to the contracts list and a dated Changes entry (human, 2026-10-15). (AC 4)
11. Tests (below). Run ruff, mypy scoped to the touched files (record 0 errors in them), lint-imports, pytest tests --ignore=tests/smoke.

Assessment of the Bolt middleware alternative against the end state
- Jobs and webhook-style consumers (TASK-145.5.7, TASK-64, TASK-140.11, TASK-37.x) never pass through Bolt, so middleware cannot be the single mechanism; the registrar approach covers the Slack path and the job path with one Protocol.
- Platforms stay independent (platform-entrypoints.md rule 4): a Teams registrar exposes the same `scopes`, where middleware would be rebuilt per SDK.
- TASK-33 (async Bolt) adds an async variant of the opener beside `open()`; the registrar surface stays. TASK-141 changes only how commands are routed, not how a handler obtains its scope.
- Verdict: keep the registrar opener; the alternative stays recorded in the ADR for review as the description states.

Test matrix (all under app/tests/unit or app/tests/integration)
- unit/contracts/services/test_contracts_services_scope_protocols.py: svcs.Container and SvcsServiceScopeOpener satisfy the Protocols (annotated assignment); the contracts/services module source contains no svcs import (AST check, backing lint-imports). AC 1.
- unit/server/test_server_services_scope_opener.py (service_registry fixture): resolves the in-memory RecordStore and ConditionalWriteStore fakes; an unregistered contract raises svcs.exceptions.ServiceNotFoundError (AC 3); with a cleanup-tracking registry, the scope closes on success, closes when the body raises and the exception propagates, and two opens produce two independent containers each closed once; concurrent opens from worker threads each close once. AC 2, 3.
- unit/server/test_server_services_scope_entry_points.py (service_registry fixture): a feature-style `register(registrar)` closure registered on FakeSlackRegistrar(scopes=opener) opens a scope, resolves RecordStore, builds a small service from it and calls one method, and the scope closes when the listener raises; a job registered through a recording BackgroundJobRegistry fake does the same. AC 5.
- unit/server/plugins/test_server_plugins_slack_registrar_scopes.py: PluginSlackRegistrar.scopes is the host registrar's opener (identity). AC 2.
- unit/integrations/slack/test_slack_provider_scope_opener.py: `scopes` raises RuntimeError before set_scope_opener and returns the opener after. AC 2.
- unit/jobs/test_scheduled_tasks.py (edited in place): the three registry tests construct the registry with a scopes argument; a new case asserts `registry.scopes` is that opener; the init test passes `scopes` and asserts the registry given to the plugin callback carries it. AC 2.
- integration/jobs/test_scheduled_tasks_integration.py and integration/server/test_lifespan.py (edited in place): pass `scopes`; the lifespan test asserts init is called with (bot, register_background_jobs, scopes). AC 5.
- integration/server/test_lifespan_scope_opener.py (new): real lifespan with later phases stubbed; set_scope_opener is called once with an SvcsServiceScopeOpener over the lifespan's registry, before register_feature_integrations. AC 5.
- unit/server/test_server_services_entry_points.py (edited in place): remove the async Slack-style and job-style raw-container functions and tests, now covered through the opener, and correct the module docstring; the route and unregistered-contract tests stay.
- tests/factories/slack.py: FakeSlackRegistrar takes an optional `scopes` and raises RuntimeError from the property when absent, like the provider.
- Gates: lint-imports (contract (l) and all existing contracts), ruff, mypy on touched files (the entry-point test exercises get(RecordStore)), pytest.

AC traceability: AC 1 steps 1, 8, protocol test; AC 2 steps 2-7, opener, registrar, provider and jobs tests; AC 3 step 3, opener test with the service_registry fixture; AC 4 steps 9-10 (reviewed by reading); AC 5 steps 6-7, reference and lifespan tests; AC 6 step 8, lint-imports and the scratch mypy check. Every step maps to an AC.

Assumptions and doubts (verify)
- svcs.Container satisfies ServiceResolver structurally under mypy: confirmed in a scratch module on 2026-10-15; re-checked against the real Protocol by mypy on the entry-point test.
- Disabling type-abstract repo-wide hides nothing already reported: run mypy before and after and compare counts on touched files.
- Bolt sync listeners run on worker threads, so each open() must build its own container and the registry is only read after boot (the host's _once factories hold the lock): covered by the concurrent-open test.
- get_slack_provider is @cache, so an injected opener outlives one test: tests build their own provider or fake registrar; verify by running the full suite in one process (see the known TASK-90 order failures, which are unrelated).
- Jobs are registered only in production (lifespan.py:117-130), so the job path runs in tests only until TASK-145.5.7; verify by reading that gate.
- Other BackgroundJobRegistry fakes lack `scopes` and never read it: verify by running the oncall_sync and access/sync package tests.

Blast radius and rollback: nothing reads `scopes` in production after this slice, so a wiring mistake surfaces only as a RuntimeError for the first consumer (TASK-145.5.5), not as a runtime change today; the only signature changes are scheduled_tasks.init and _start_scheduled_tasks, each with one production caller. The mypy option change affects the whole repo's checks but only for type[T] with abstract classes. No config, Terraform or deploy ordering. One git revert restores the previous state. Layers 6, 7 and 9 consume the opener.

Out of scope (human, 2026-10-15): webhook sink handlers (TASK-37.5) and approval effect handlers (TASK-60) obtain an opener from their own registration points; settled when each is planned.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-10-15 13:43
---
Plan approved by the human in chat, 2026-10-15. Decisions: mypy type-abstract disabled repo-wide, proven by the entry-point test calling get(RecordStore) (no scratch check); import-linter contract (l) forbids svcs in contracts/; plugin-architecture.md gains a contracts/services line and Changes entry; TASK-37.5 and TASK-60 openers settled when those tasks are planned.
---
<!-- COMMENTS:END -->

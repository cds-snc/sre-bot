---
adr_id: ADR-0083
title: "Event Dispatcher Library Adoption"
status: Accepted
decision_type: Library Adoption Decision
tier: Tier-5
governance_domain: application
primary_domain: Runtime and Lifecycle
secondary_domains:
  - Dependency and Composition
  - Package and Plugin Architecture
owners:
  - SRE Team
date_created: 2026-05-04
last_updated: 2026-05-04
last_reviewed: 2026-05-04
next_review_due: 2026-09-01
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0054
  - ADR-0056
  - ADR-0065
  - ADR-0077
  - ADR-0079
impacts: []
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0046
  - ADR-0058
  - ADR-0059
  - ADR-0067
  - ADR-0076
  - ADR-0078
related_packages:
  - app/infrastructure/events
  - app/packages/access
---

# Event Dispatcher Library Adoption

## Context

- Problem statement: The application is an operational orchestrator (SRE Bot) undergoing a structural migration from legacy `app/modules/` to `app/packages/`. Eight feature domains (incident, sre, atip, secret, aws, role, webhooks, dev) will migrate to independent packages, and `packages/access` — a complex multi-sub-package domain (request, sync, common) — is greenfield but not yet enabled in production. The legacy `modules/groups/` is deprecated dead code, replaced by `packages/access`.

  This migration creates genuine cross-cutting event notification needs across 8+ packages: audit logging (Sentinel), multi-platform notifications (Slack, Teams, Discord per ADR-0078), and telemetry. Direct-call wiring for these cross-cutting concerns across all packages would create O(packages × concerns) coupling. An in-process event system decouples emitters from consumers, allowing packages to evolve independently per ADR-0059.

  The existing event dispatcher (`app/infrastructure/events/`) is a **Tier 3 (custom implementation)** consisting of ~200 lines of hand-rolled registry, dispatch loop, and threading code. ADR-0045 Principle 7 mandates that infrastructure concerns use the highest applicable delegation tier: managed cloud service → industry library → custom implementation. The custom dispatcher violates this by implementing Tier 3 when Tier 2 alternatives exist.

  A duplicate event system exists in `modules/groups/events/system.py` — a parallel implementation with its own `EVENT_HANDLERS` dict, `dispatch_event()`, and `ThreadPoolExecutor`. This duplication is one instance of a broader anti-pattern: `modules/groups` was implementing reusable infrastructure concepts at the feature scope rather than at the application level. This misplacement — reusable cross-feature capabilities embedded inside a single feature module — was the root cause that triggered the entire ADR review and application refactoring program. The event system duplication is a direct, observable symptom of that architectural decision.

  The codebase is currently synchronous but targeting async migration. The event infrastructure must support both sync and async handlers during the transition period.

- Business/operational drivers:
  - **Migration infrastructure**: The `modules/` → `packages/` migration requires decoupled cross-cutting event notification. The `modules/groups` deprecation — the catalyst for this entire refactoring program — revealed a pattern of reusable, cross-feature infrastructure concepts being implemented inside feature modules. The event system (`modules/groups/events/system.py`) is one of those concepts. Without a governed app-level event infrastructure, migrated packages will repeat this pattern: either hardwiring cross-cutting calls (coupling) or re-implementing ad-hoc notification mechanisms (duplication).
  - **Choreography saga support**: `packages/access` models a bidirectional workflow — request approved → sync executes → sync result flows back to update request state. This is a choreography saga pattern where each sub-package reacts to the other's domain events without direct imports, maintaining package isolation per ADR-0048.
  - **ADR-0045 P7 compliance**: Replace Tier 3 (custom) in-process event dispatch with Tier 2 (industry library).
  - **Async readiness**: The chosen library must support async coroutine handlers natively for the planned sync → async migration, without requiring a separate library swap later.
  - **ECS multi-task constraint**: The application runs with `desired_count = 2` in ECS Fargate. In-process events are isolated per task. This ADR governs only the in-process concern; cross-task delivery requires SQS/SNS per ADR-0079 Standard 1.

- Constraints:
  - ADR-0045 Principle 7: In-process pub/sub has no managed cloud service equivalent (it is inherently in-process), so Tier 2 (library) is the highest applicable tier.
  - ADR-0048 Boundary 4: No import-time side effects. Handler registration must happen during lifespan startup, not at import time via decorators.
  - ADR-0049 Standard 7: Zero-touch extension. Feature packages register handlers via pluggy hookspecs.
  - ADR-0054: Dev/test parity. The library must work identically in all environments without special configuration.
  - ADR-0056 Standard 1: The `EventDispatcher` service receives narrow dependencies, not full Settings objects.
  - ADR-0065: `Event` payloads are frozen dataclasses (internal domain data). Handler function signatures follow typing conventions.
  - ADR-0077: `EventDispatcher` is Category B (shared utility, concrete OK). Reclassify to Category A if migrated to a durable broker per ADR-0079 Phase 2.
  - ADR-0079 Standard 2: Startup-driven handler registration via pluggy hookspecs is unchanged. This ADR governs the dispatch mechanism underneath.

- Non-goals:
  - This ADR does not govern cross-process event delivery. Cross-task delivery requires SQS/SNS per ADR-0079 Standard 1.
  - This ADR does not change the `Event[T]` dataclass model. The domain event model is independent of the dispatch mechanism.
  - This ADR does not prescribe feature-level event type definitions. Each package defines its own event constants per existing convention.
  - This ADR does not govern Slack Bolt's `.command()/.view()/.action()` transport-layer event registration. Slack Bolt handler registration is a transport concern governed by ADR-0067; it operates at a different architectural layer than in-process domain events.

## Decision

- Chosen approach: Adopt `blinker` (1.9+) as the industry-standard library (Tier 2) for in-process event dispatch. The `EventDispatcher` service class is retained as a thin facade providing error-isolated dispatch, background execution, and async bridging over blinker signals, preserving the existing DI injection surface (`EventDispatcherDep`).

- Why this approach: `blinker` is the most established Python in-process signaling library. It is maintained by the Pallets Community Ecosystem (Flask/Jinja maintainers), provides a minimal API surface (`Signal`, `connect`, `send`, `send_async`), supports both sync and async receivers natively, and imposes no threading or event loop opinions — making it compatible with FastAPI's uvicorn loop and the sync → async migration path.

### Standard 1: Library Adoption

The custom `EventHandlerRegistry` class, `@register_event_handler` decorator, and module-level `EVENT_HANDLERS` dict are deprecated. In-process event dispatch must use `blinker.Signal` instances managed by the `EventDispatcher` facade.

1. **`blinker` as dispatch library**: The `EventDispatcher` facade uses blinker `Signal` objects as the handler registry. Handler registration uses `signal.connect()`. The custom dispatch loop, wildcard handler merging, and discovery mechanisms are eliminated.
2. **`EventDispatcher` facade retained**: The facade wraps blinker signals, the background executor, and error isolation logic. It preserves the DI injection surface (`EventDispatcherDep`) so that feature packages are insulated from the library choice. Feature packages interact with `EventDispatcher`, not with `blinker` directly.
3. **Custom registry deprecated**: The `EventHandlerRegistry` class (from `feat/infra-event-dispatcher`), the module-level `EVENT_HANDLERS` dict, and the `@register_event_handler` import-time decorator are all deprecated.

### Standard 2: Event Type Ownership

Each package defines its domain event type constants as strings in `<package>/events.py`. Signals are created and owned by the `EventDispatcher` facade.

1. **Event type constants**: Packages declare event types as string constants (e.g., `REQUEST_SUBMITTED = "access_requests.request_submitted"`). This is the existing convention and remains unchanged.
2. **Signal creation is facade-internal**: The `EventDispatcher` creates `Signal` instances lazily when handlers register or events dispatch. Packages do not create or import `blinker.Signal` directly — this keeps the library choice an infrastructure implementation detail.
3. **Naming convention**: Event type strings use dotted namespace format (`<domain>.<entity>.<action>`) for traceability and structured logging continuity.

### Standard 3: Handler Registration at Startup

Handlers connect to signals during lifespan startup, not at import time.

1. **Pluggy hookspec**: The `register_event_handlers(dispatcher: EventDispatcher)` hookspec (ADR-0079 Standard 2, point 2) is the registration entry point. Feature packages implement this hookspec to register their handlers during lifespan phase 4 (feature activation).
2. **No import-time `signal.connect()`**: Calling `signal.connect()` at module scope or via a decorator at import time violates ADR-0048 Boundary 4. All connections must happen inside the pluggy hook implementation.
3. **Registration via facade**: Handlers register through `dispatcher.register_handler(event_type, handler)`, which internally calls `signal.connect()`. This preserves structured logging of handler registration (handler name, event type, handler count) and allows the facade to enforce registration-time invariants.

### Standard 4: Error-Isolated Dispatch

The `EventDispatcher` facade MUST isolate handler failures. One handler exception must not prevent other handlers from executing.

1. **Facade-owned dispatch loop**: The facade MUST NOT delegate dispatch to `signal.send()` or `signal.send_async()` directly, because blinker propagates the first exception and skips remaining receivers. Instead, the facade iterates `signal.receivers_for(sender)` and invokes each receiver individually within a try/except block.
2. **Error logging**: Handler exceptions are caught and logged with structured context: handler name, event type, correlation ID, error message, and traceback. Logging uses `structlog` per ADR-0054.
3. **No exception propagation to emitters**: The `dispatch()` and `dispatch_background()` methods never raise handler exceptions to the calling service. Emitters fire events and continue; handler failures are operational concerns, not business logic failures.
4. **blinker value despite facade-owned dispatch**: Although the facade owns the dispatch loop, blinker provides: (a) thread-safe receiver storage with weak references, (b) automatic cleanup of garbage-collected handlers, (c) named signal deduplication via `Namespace`, (d) `muted()` and `connected_to()` context managers for testing, (e) `receivers_for()` generator that handles weak-ref liveness checks. These capabilities replace ~200 lines of custom registry code.

### Standard 5: Async Readiness

The dispatch layer must support async handlers for the planned sync → async migration.

1. **Current state (sync)**: The facade dispatches synchronously. `dispatch_background()` submits dispatch work to a `ThreadPoolExecutor`. The executor lifecycle is unchanged: start during lifespan phase 5 (transport), stop during shutdown step 2 per ADR-0058.
2. **Async migration target**: When services migrate to async, the facade adds a `dispatch_async()` method that iterates `signal.receivers_for(sender)` and `await`s each async handler with per-handler error isolation (same pattern as Standard 4, but with `await`). blinker's `send_async(_sync_wrapper=...)` can bridge sync receivers during the transition.
3. **Mixed sync/async transition**: During migration, both sync and async handlers may coexist. The facade detects handler type (`asyncio.iscoroutinefunction()`) and dispatches appropriately. blinker's `_sync_wrapper` and `_async_wrapper` parameters provide native support for mixed receiver types.
4. **`dispatch_background()` evolution**: When the codebase is fully async, `dispatch_background()` evolves from `ThreadPoolExecutor.submit()` to `asyncio.create_task()`, eliminating the thread pool for event dispatch. The executor may be retained for CPU-bound work per ADR-0058.

### Standard 6: Cross-Process Event Boundary

blinker is in-process only. Any operation requiring delivery across ECS tasks must use a managed queue service.

1. **In-process signals and cross-process queues are complementary**: blinker handles task-local side effects (notifications, audit, state transitions). SQS/SNS (ADR-0079 Standard 1) handles cross-task delivery (cache invalidation, sync coordination).
2. **No cross-process pretense**: The `EventDispatcher` facade must not attempt cross-process delivery. If a feature requires cross-task eventing, it must use the queue service directly (ADR-0079 Phase 2).
3. **ECS constraint**: The application runs with `desired_count >= 2`. In-process events are isolated per ECS task. This boundary is documented for feature teams.

### Standard 7: Deprecated Code Inventory

| Component | Location | Disposition |
|-----------|----------|-------------|
| `EventHandlerRegistry` class | `infrastructure/events/registry.py` | **Delete** — replaced by blinker `Signal` via facade |
| `@register_event_handler` decorator | `infrastructure/events/dispatcher.py` | **Delete** — replaced by `dispatcher.register_handler()` |
| `EVENT_HANDLERS` global dict | `infrastructure/events/dispatcher.py` | **Delete** — replaced by blinker signal internals |
| `_discover_handlers_recursive()` | `infrastructure/events/discovery.py` | **Delete** — pluggy hookspec replaces auto-discovery |
| `get_event_registry()` singleton | `infrastructure/events/registry.py` | **Delete** — blinker signals are the registry |
| Parallel event system | `modules/groups/events/system.py` | **Delete** — duplicate dispatcher eliminated with `modules/groups` deprecation |
| Import-time handler decorators | `modules/groups/events/handlers.py` | **Delete** — deprecated with `modules/groups` |
| `feat/infra-event-dispatcher` branch | Branch | **Abandoned** — custom registry refactoring superseded by library adoption |

Retained components:

| Component | Location | Reason |
|-----------|----------|--------|
| `EventDispatcher` service class | `infrastructure/events/service.py` | DI facade over blinker + executor + error isolation |
| `Event[T]` dataclass | `infrastructure/events/models.py` | Domain model, library-independent (ADR-0065) |
| ThreadPoolExecutor lifecycle | `infrastructure/events/service.py` | Background execution concern (ADR-0058) |
| Event type string constants | `packages/<feature>/events.py` | Package-owned domain contracts |

### Retirement Criteria

This Tier-5 ADR retires when:

1. `blinker` is added to `requirements.txt`.
2. `EventDispatcher` facade wraps blinker signals with error-isolated dispatch.
3. Custom `EventHandlerRegistry`, `@register_event_handler`, and `EVENT_HANDLERS` global are removed.
4. `modules/groups/events/system.py` parallel dispatcher is deleted (with `modules/groups` deprecation).
5. At least one feature package registers handlers via pluggy hookspec.
6. All tests pass with blinker-backed dispatch.

**Target retirement date:** 2026-09-01.

## Alternatives Considered

1. **Delete event system entirely — no library, no events**:
   - Pros: Simplest option. Current event system has zero production consumers (the only handlers are in deprecated `modules/groups`). Access package dispatch calls are dead letters with no registered handlers. Eliminates all event infrastructure code and maintenance.
   - Cons: The `modules/` → `packages/` migration creates 8+ feature packages with shared cross-cutting concerns (audit, notifications, telemetry). Without an event bus, each package hardwires cross-cutting calls, creating O(packages × concerns) coupling — the service method becomes `do_work() + audit() + notify() + telemetry()`. The access package's choreography saga (request↔sync) would require direct cross-sub-package imports, violating package isolation (ADR-0048). The current zero-consumer state reflects a pre-migration snapshot, not the final architecture.
   - Why not chosen: The migration ahead creates the use case. Building event infrastructure now — while the packages layer is greenfield — is cheaper than retrofitting it after 8 packages have hardwired direct calls.

2. **Keep custom implementation and refactor**:
   - Pros: No new dependency. `feat/infra-event-dispatcher` branch work is partially done.
   - Cons: Violates ADR-0045 P7 — maintains Tier 3 when Tier 2 is available. The custom code reimplements what blinker provides (handler registry, weak references, signal deduplication, test utilities). No async support — would require adding coroutine dispatch, mixed handler detection, and sync/async bridging as custom code.
   - Why not chosen: ADR-0045 P7 mandates the highest applicable delegation tier. Custom implementation with async support would be ~400 lines of custom pub/sub code when blinker provides it in ~600 lines of battle-tested library.

3. **Use PyPubSub instead of blinker**:
   - Pros: Native error isolation ("A listener that raises an exception does not prevent remaining listeners from receiving the message"). Topic-based messaging. Active maintenance (Dec 2025 release).
   - Cons: **No native async support** — would require wrapping every async handler, creating a custom bridging layer. Heavier API surface (topic validation, message data specification, listener lifecycle). Smaller community (211 stars vs blinker's 2.1k).
   - Why not chosen: The async migration requirement disqualifies PyPubSub. blinker's `send_async()` and `_sync_wrapper`/`_async_wrapper` provide native mixed sync/async support. The facade-owned error isolation (Standard 4) eliminates PyPubSub's native error isolation advantage.

4. **Use pymitter instead of blinker**:
   - Pros: EventEmitter2 port with wildcards, TTL, and `emit_async`.
   - Cons: Smallest community (~149 stars, 4 contributors). Node.js design heritage. Last release Jul 2025 (10 months).
   - Why not chosen: Community size and Node.js design heritage increase maintenance risk.

5. **Use pyee instead of blinker**:
   - Pros: `AsyncIOEventEmitter` subclass. Active (Feb 2026 release). 427 stars.
   - Cons: Node EventEmitter port — base emitter does not isolate errors. Requires Python >= 3.12. Subclass-based design (choose emitter type at construction time) is less flexible than blinker's single `Signal` with mixed sync/async support.
   - Why not chosen: Subclass-locked dispatch model is less suitable for a codebase transitioning from sync to async — you'd need to swap the emitter subclass during migration. blinker's single `Signal` with `send()` and `send_async()` handles the transition natively.

6. **Use pluggy hookspecs for both registration AND dispatch**:
   - Pros: Single library (pluggy already a dependency).
   - Cons: Pluggy is a plugin framework, not a pub/sub library. Hookspecs create compile-time contracts (one hook per event type) instead of runtime named events. No async dispatch support. Using pluggy for dispatch conflates plugin lifecycle with event notification.
   - Why not chosen: Pluggy governs *when* handlers register (ADR-0049). blinker governs *how* events are dispatched. These are separate concerns.

7. **Skip to SQS/SNS (Tier 1)**:
   - Pros: Highest delegation tier. Solves cross-process delivery.
   - Cons: Premature — SQS adds infrastructure complexity (IAM, VPC endpoints, DLQ, CloudWatch) for concerns that are task-local side effects. In-process notification has no managed cloud service equivalent.
   - Why not chosen: Tier 2 is the highest applicable tier for in-process dispatch. Cross-process delivery is a separate concern governed by ADR-0079.

## Consequences

- Positive impacts:
  - Complies with ADR-0045 P7 by replacing Tier 3 (custom) with Tier 2 (library).
  - Eliminates ~200 lines of custom registry, dispatch loop, and discovery code.
  - Provides migration infrastructure for 8+ feature packages with cross-cutting event notification.
  - Supports choreography saga pattern in `packages/access` without cross-sub-package imports.
  - Native sync/async support via `send()` and `send_async()` bridges the async migration.
  - The `EventDispatcher` facade insulates feature packages from the library choice.
  - blinker's `muted()` and `connected_to()` simplify test isolation (ADR-0062).
  - Eliminates the `modules/groups/events/system.py` duplication — one governed infrastructure replaces the feature-scoped re-implementation that was the canonical example of the anti-pattern driving this refactoring program.
- Tradeoffs accepted:
  - New direct dependency (`blinker`). Acceptable — stable, well-maintained, minimal footprint (~600 lines, no transitive dependencies), MIT license.
  - Facade-owned dispatch loop (Standard 4) means blinker is used primarily as a registry, not a dispatcher. This is an acceptable tradeoff — blinker's registry capabilities (weak refs, thread safety, signal deduplication, test utilities) still replace significant custom code. The dispatch loop itself is ~10 lines of facade code.
  - `feat/infra-event-dispatcher` custom registry work is deprecated (sunk cost).
- Risks introduced:
  - blinker maintenance discontinuation. Mitigation: Pallets Community Ecosystem maintenance model (Flask, Jinja, Werkzeug). 2.1k stars. Last release Nov 2024. The facade allows library substitution without feature code changes.
  - Event type string collisions across packages. Mitigation: dotted namespace convention (`<domain>.<entity>.<action>`) and package-owned constants in `events.py`.
  - Over-reliance on fire-and-forget dispatch masking failures. Mitigation: Standard 4 mandates structured error logging for every handler failure. Operational alerting can key on `event_handler_failed` log events.

## Compliance and Boundaries

- Package/infrastructure boundary impact: `EventDispatcher` remains infrastructure-owned (`app/infrastructure/events/`). Feature packages consume it via `EventDispatcherDep` (ADR-0048 B2). Feature packages do not import `blinker` directly.
- Type boundary impact: `Event[T]` frozen dataclass is unchanged (ADR-0065). `EventDispatcher` remains a concrete class (Category B per ADR-0077).
- Startup/plugin registration impact: `register_event_handlers(dispatcher: EventDispatcher)` pluggy hookspec is unchanged (ADR-0079 Standard 2, point 2). Registration happens during lifespan phase 4.
- Settings partitioning impact: None — blinker requires no configuration settings.
- DI alias ceremony impact: `EventDispatcherDep` alias is unchanged.
- Service contract impact: `EventDispatcher` remains Category B per ADR-0077 (shared utility, concrete OK). Reclassify to Category A if migrated to durable broker (ADR-0079 Phase 2).
- Managed service delegation impact: Moves event dispatcher from Tier 3 (custom) to Tier 2 (library) per ADR-0045 P7.
- Slack Bolt boundary: Slack Bolt's `.command()/.view()/.action()` transport-layer registration (ADR-0067) is a distinct mechanism at the transport layer. ADR-0083 governs application-layer domain events only. The two systems are complementary and independent.

## Codebase Audit (2026-05-04)

### Current Production State

The event system is **structurally present but functionally hollow**:

- **Zero active production consumers**: The only registered handlers are in deprecated `modules/groups/events/handlers.py` (3 handlers). `modules/groups` is dead code, candidate for deletion.
- **Dead-letter emitters**: `packages/access/request` emits 10+ event types and `packages/access/sync` emits 5 event types via `dispatch_background()`, but no handlers are registered for any `access_*` event. Every dispatch call fires into the void.
- **Aspirational cross-package contract**: `packages/access/common/events.py` declares `REQUEST_APPROVED`, `SYNC_COMPLETED`, and `SYNC_FAILED` as cross-sub-package event contracts, with comments documenting the intended choreography. The contract is declared but not wired.
- **Duplicate dispatcher**: `modules/groups/events/system.py` contains a parallel event system with its own `EVENT_HANDLERS` dict and `ThreadPoolExecutor`, separate from `infrastructure/events/`. This is the event system manifestation of the `modules/groups` anti-pattern: a reusable, cross-feature infrastructure concern built inside a feature module. It is one of multiple such concepts discovered during the groups deprecation that triggered the broader refactoring program.

This state reflects a pre-migration snapshot. The event infrastructure will become load-bearing as packages are enabled and `modules/` features migrate.

### Migration Scope

| Current `modules/` | Target `packages/` | Cross-Cutting Event Needs |
|--------------------|--------------------|--------------------------|
| `incident/` | `packages/incident` | Audit (Sentinel), notifications (Slack), Google Drive |
| `sre/` | `packages/sre` | Multi-platform notifications (Slack, Teams, Discord) |
| `atip/` | `packages/atip` | Notifications (Slack) |
| `secret/` | `packages/secret` | Audit logging |
| `aws/` (non-sync) | `packages/aws` | Notifications (Slack), IAM audit |
| `role/` | `packages/role` | Notifications (Slack) |
| `webhooks/` | `packages/webhooks` | Channel routing, audit |
| `dev/` | `packages/dev` | Multi-platform notifications |
| `groups/`, `provisioning/`, aws-sync | Replaced by `packages/access` | Choreography saga, audit, notifications |

### Event Emitters (Current)

| Package | Event Types | Dispatch Method | Has Consumers? |
|---------|------------|-----------------|----------------|
| `packages/access/request` | `access_requests.*` (8 types) | `dispatch_background()` | **No** — no handlers registered |
| `packages/access/sync` | `access_sync.*` (5 types) | `dispatch_background()` | **No** — no handlers registered |
| `modules/groups` (deprecated) | `group.*` (3 types) | `dispatch_background()` | **Yes** — 3 handlers in deprecated code |

## Implementation Guidance

- Required changes:
  1. Add `blinker>=1.9` to `app/requirements.txt`.
  2. Rewrite `EventDispatcher` to use blinker `Signal` objects as internal registry.
  3. Implement error-isolated dispatch loop per Standard 4 (iterate `receivers_for()`, try/except each).
  4. Add `register_event_handlers` pluggy hookspec per ADR-0079 Standard 2.
  5. Remove `EventHandlerRegistry`, `@register_event_handler`, `EVENT_HANDLERS` global, `discovery.py`.
  6. Delete `modules/groups/events/system.py` (parallel dispatcher) with `modules/groups` deprecation.

- Validation and quality gates:
  - `python -m mypy .` — type-check blinker integration
  - `python -m flake8` — lint compliance
  - `python -m black --check .` — formatting
  - `python -m pytest app/tests --ignore=app/tests/smoke -x` — all tests pass

- Test strategy and acceptance criteria impact:
  - Test error-isolated dispatch: register 3 handlers, second raises, verify first and third still called.
  - Test `register_handler()` → `signal.connect()` integration.
  - Test background dispatch submits to executor correctly.
  - Test `muted()` context manager for test isolation.
  - Test `dependency_overrides[get_event_dispatcher]` works for route-level test isolation.
  - Test mixed sync/async handler dispatch (when async migration begins).

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Tier-5 Library Adoption Decision. Adopts blinker for in-process event dispatch, replacing custom Tier 3 implementation per ADR-0045 P7. Provides migration infrastructure for 8+ feature packages with cross-cutting event notification and choreography saga support for `packages/access`. Constrained by ADR-0044, ADR-0045, ADR-0048, ADR-0049, ADR-0054, ADR-0056, ADR-0065, ADR-0077, ADR-0079. Target retirement 2026-09-01.
- Follow-up actions:
  - Amend ADR-0079 Standard 2 to reference this ADR for library delegation.
  - Amend ADR-0077 Category B table entry for `EventDispatcher`.
  - Amend ADR-0045 Compliance section for event dispatcher delegation.

## Change Log

- 2026-05-04: Created as Draft. Full rewrite from initial version. Rescoped from narrow "replace custom registry with blinker" to "establish event infrastructure for modules → packages migration." Added: async readiness standard (S5), facade-owned error-isolated dispatch (S4), choreography saga rationale, migration scope table, "delete event system entirely" as alternative considered. Removed: assumption that blinker `send()` could be used directly (Round 1 review blocker — blinker propagates exceptions). Extended retirement date from 2026-07-01 to 2026-09-01 to align with migration timeline.
  - Add `blinker` to `requirements.txt` and implement migration.

## Source References

1. Source title: blinker — Fast, simple object-to-object and broadcast signaling
   - URL: <https://pypi.org/project/blinker/>
   - Publisher/maintainer: Pallets Community Ecosystem
   - Accessed date (YYYY-MM-DD): 2026-05-04
   - Relevance summary: Industry-standard Python signaling library. Minimal API (`Signal`, `connect`, `send`). Maintained by Flask ecosystem. 1.7k GitHub stars.
2. Source title: blinker Documentation
   - URL: <https://blinker.readthedocs.io/>
   - Publisher/maintainer: Pallets Community Ecosystem
   - Accessed date (YYYY-MM-DD): 2026-05-04
   - Relevance summary: API reference for `Signal`, `connect`, `send`, sender filtering, and weak reference behavior.
3. Source title: PyPubSub — Python Publish-Subscribe Package
   - URL: <https://pypi.org/project/PyPubSub/>
   - Publisher/maintainer: Oliver Schoenborn
   - Accessed date (YYYY-MM-DD): 2026-05-04
   - Relevance summary: Alternative considered. Topic-based pub/sub with debugging tools. Heavier API surface than blinker.
4. Source title: pymitter — Python EventEmitter2 port
   - URL: <https://pypi.org/project/pymitter/>
   - Publisher/maintainer: Marcel Rieger
   - Accessed date (YYYY-MM-DD): 2026-05-04
   - Relevance summary: Alternative considered. Wildcards, TTL, async support. Smaller community.
5. Source title: ADR-0045 — Core Architectural Principles, Principle 7
   - URL: docs/decisions/adr/0045-core-architectural-principles.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-05-04
   - Relevance summary: Managed Service Delegation Hierarchy — managed cloud service → industry library → custom implementation.
6. Source title: ADR-0079 — Queueing and Message-Broker Architecture Standard, Standard 2
   - URL: docs/decisions/adr/0079-queueing-and-message-broker-architecture-standard.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-05-04
   - Relevance summary: Event dispatcher remediation standard. Governs startup-driven registration via pluggy hookspecs. This ADR governs the dispatch mechanism underneath.
7. Source title: Cosmic Python Ch. 11 — Event-Driven Architecture
   - URL: <https://www.cosmicpython.com/book/chapter_11_external_events.html>
   - Publisher/maintainer: Harry Percival, Bob Gregory
   - Accessed date (YYYY-MM-DD): 2026-05-04
   - Relevance summary: Message bus abstraction, handler registration vs. dispatch separation. Supports the facade-over-library pattern.

## Change Log

| Date | Section | Change Summary |
|------|---------|----------------|
| 2026-05-04 | All | Initial Draft — blinker library adoption for in-process event dispatch, deprecating custom EventHandlerRegistry. |

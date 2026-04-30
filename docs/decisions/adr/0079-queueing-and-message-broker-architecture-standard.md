---
adr_id: ADR-0079
title: "Queueing and Message-Broker Architecture Standard"
status: Draft
decision_type: Standard
tier: Tier-2
primary_domain: Runtime and Lifecycle
secondary_domains:
 - Dependency and Composition
 - Package and Plugin Architecture
 - Observability and Operations
owners:
 - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-30
last_reviewed: 2026-04-30
next_review_due: 2026-08-28
constrained_by:
 - ADR-0044
 - ADR-0045
 - ADR-0046
 - ADR-0048
 - ADR-0049
 - ADR-0050
 - ADR-0052
 - ADR-0054
 - ADR-0055
 - ADR-0056
 - ADR-0057
 - ADR-0058
 - ADR-0077
impacts:
 - ADR-0059
supersedes: []
superseded_by: []
review_state: current
related_records:
 - ADR-0045
 - ADR-0046
 - ADR-0049
 - ADR-0053
 - ADR-0057
 - ADR-0058
 - ADR-0076
 - ADR-0078
related_packages:
 - app/infrastructure/events
 - app/infrastructure/resilience
 - app/jobs
---

# Queueing and Message-Broker Architecture Standard

## Context

- Problem statement: The application has three distinct asynchronous execution mechanisms — each addressing a different concern, but none governed by a unified queueing architecture standard:

  1. **Retry queue** (`app/infrastructure/resilience/retry/`): A multi-backend retry store (in-memory for dev, DynamoDB for production) with `RetryStore` and `RetryProcessor` Protocols already implemented. The configuration declares an `sqs` backend option that is not yet implemented.
  2. **Event dispatcher** (`app/infrastructure/events/`): An in-process handler registry using a global `EVENT_HANDLERS` dict with `@register_event_handler` decorators. Handlers are registered at import time (violating ADR-0048 Boundary 4 — no import-time side effects). Dispatch supports synchronous and asynchronous modes (ThreadPoolExecutor with 4 workers).
  3. **Background job scheduler** (`app/jobs/`): A `schedule`-library-based scheduler with pluggy-based job registration via `BackgroundJobRegistry`. Jobs run in a non-daemon thread, production-only, with `safe_run()` exception swallowing.

  No legacy ADR governs queueing or message-broker architecture. ADR-0058 (Background Execution and Worker Isolation Standard) governs the colocated scheduled worker model and explicitly defers the evolution path to queue-driven workers. This record defines that evolution path: the architectural standards for queue abstractions, consumer lifecycle, delivery semantics, and the boundary between the current in-process model and future queue-backed processing.

- Business/operational drivers:
- Define the architectural boundary between in-process async execution (current) and durable queue-backed execution (future), so that the codebase can evolve without ad-hoc queue integrations.
- Establish queue service Protocol contracts per ADR-0077 so that the retry store's planned SQS backend and any future queue consumers have a clean abstraction layer.
- Fix the event dispatcher's import-time side effect violation (ADR-0048 B4) by mandating startup-driven handler registration.
- Define delivery semantics (at-least-once), dead-letter handling, and poison-message policy before the first durable queue integration is implemented.
- Establish consumer lifecycle integration with ADR-0046 (transport phase) and ADR-0057 (graceful shutdown) so that queue consumers start and stop within the lifespan model.
- Define queue consumer registration via pluggy hooks (ADR-0049 alignment) to maintain the zero-touch extension model.
- Constraints:
- ADR-0046 Invariant 2: Queue consumers start during lifespan phase 5 (transport phase), after configuration, infrastructure, discovery, and feature activation are complete.
- ADR-0046 Invariant 4: Queue consumers stop during shutdown step 2 (reverse of phase 5 — background stops first in step 1, then transport stops in step 2), before features, infrastructure, and configuration are torn down.
- ADR-0048 Boundary 4: No import-time side effects. Event handler registration and queue consumer registration must happen during lifespan startup, not at import time.
- ADR-0049 Standard 7: Zero-touch extension — queue consumers must be discoverable via pluggy hooks, not hard-coded.
- ADR-0050 Standard 1: Queue consumer operations that cross integration boundaries must return `OperationResult`.
- ADR-0052: Queue configuration (endpoint URLs, queue names, region, DLQ settings) must be release-phase bound — environment variables, not runtime-fetched.
- ADR-0054: Queue consumer execution must emit structured logs with correlation context. Message payloads must not contain credentials or PII in log events.
- ADR-0055 Standard 1: Queue-specific settings must have independent `BaseSettings` classes (e.g., `SQSSettings`, `EventSettings`).
- ADR-0056 Standard 1: Queue services must receive narrow settings slices, not the full Settings object.
- ADR-0057 Standard 2: Queue consumers must respect shutdown timeout budgeting — stop polling, drain in-flight messages within the shutdown window.
- ADR-0058 Standard 4: The two-tier concurrency classification (singleton-lock for single-instance vs. idempotent for multi-instance) applies to queue consumers when multiple ECS tasks consume the same queue.
- ADR-0077: Queue service abstractions must be classified (Category A or B).
- Non-goals:
- This record does not prescribe a specific message broker (SQS, Redis, RabbitMQ). Broker selection is an infrastructure decision; the standards are broker-agnostic.
- This record does not define one-off task execution or CLI commands.
- This record does not define the retry store implementation (governed by the existing retry infrastructure). It governs the architectural relationship between the retry queue and the broader queueing model.
- This record does not mandate migrating the current `schedule`-based background job model to a queue-driven model. ADR-0058 governs the current model; this record defines the target architecture for when the evolution is triggered.

## Decision

- Chosen approach: Establish a Tier-2 architectural standard that defines queue abstractions, consumer lifecycle, delivery semantics, and the phased evolution from in-process async to durable queue-backed processing. Fix the event dispatcher's import-time side effect violation. Classify queue services per ADR-0077.
- Why this approach: The codebase already has three async mechanisms. Without a governing standard, future queue integrations (SQS backend for retry, event-driven processing) will be implemented ad-hoc. A proactive architectural standard prevents drift and ensures all queue infrastructure follows the established DI, lifecycle, and observability patterns.

### Standard 1: Queue Integration Standard

When the application adopts a managed queue service (SQS, Azure Service Bus, etc.) per ADR-0045 P7 (Tier 1 — managed cloud service preferred), the integration must follow these rules:

1. **Thin SDK wrapper behind Protocol contract**: The queue client must be wrapped in a thin facade behind a Protocol contract (ADR-0077 Category A). The Protocol shape should emerge from wrapping the actual managed service SDK, not from pre-designed generic abstractions.
2. **`QUEUE_BACKEND` settings configuration**: Backend selection follows ADR-0055 Standard 9 and ADR-0056 Standard 8. A `QUEUE_BACKEND: Literal["memory", "sqs"] = "memory"` settings key enables dev/test fallback.
3. **Consumer lifecycle in lifespan transport phase**: Queue consumers start during lifespan phase 5 (transport phase, per ADR-0046) and stop during shutdown step 2 (per ADR-0057). Consumer registration uses pluggy hookspecs (ADR-0049 Standard 7).
4. **Dev/test in-memory fallback**: An in-memory queue implementation must exist per ADR-0054 dev/test fallback standard. It satisfies the Protocol contract for local development and CI testing.

**Classification**: Queue services are **Category A** per ADR-0077 — they abstract a backing service (SQS, in-memory) and are consumed by feature packages. Protocol contracts are required.

**Timing**: These standards apply when the first durable queue integration is implemented. The Protocol shape is not pre-defined — it emerges from the actual SDK wrapping work. Pre-designing `MessageProducer`/`MessageConsumer` Protocols before implementation risks creating abstractions that don't match the managed service's actual API surface.

> **Revision (2026-04-30 — Managed Service Delegation Review):** Standard 1 was narrowed from a pre-defined Protocol specification (`MessageProducer`, `MessageConsumer`, `MessageEnvelope`) to a queue integration standard that lets the Protocol shape emerge from wrapping the first managed service. Pre-designing Protocols before implementation tends to produce abstractions that don't match the actual API surface. See ADR-0045 P7: managed service wrapper is the preferred delegation tier.

### Standard 2: Event Dispatcher Remediation

The current event dispatcher (`app/infrastructure/events/dispatcher.py`) violates ADR-0048 Boundary 4 (no import-time side effects) by using `@register_event_handler` decorators that mutate a global handler dict at import time. The remediation standard is:

1. **Remove import-time registration**: The `@register_event_handler` decorator must be replaced with startup-driven registration via the lifespan.
2. **Pluggy-based event handler registration**: Event handlers must be discoverable via pluggy hookspecs, consistent with ADR-0049 Standard 7:
   - `register_event_handlers(dispatcher: EventDispatcher)` hookspec — feature packages implement this to register their handlers during startup.
   - Handler registration happens during lifespan phase 4 (feature activation — handlers, event subscribers, integrations), before transport start (phase 5).
3. **Handler registry encapsulation**: The global `EVENT_HANDLERS` dict must be encapsulated within the `EventDispatcher` class instance, not as a module-level global. The `EventDispatcher` instance is created by the provider and managed by the lifespan.
4. **Correlation propagation**: `dispatch_event()` must propagate the correlation context (correlation_id, user_email) from the originating request to all handler invocations. Handlers must receive the `Event[T]` dataclass which already carries `correlation_id`.
5. **Error isolation**: Handler exceptions must be caught, logged with structured context (handler name, event_type, correlation_id, error), and must not prevent other handlers from executing. This is the current behavior (`safe_run`) but must be codified.

**Timeline**: The event dispatcher remediation is independent of the durable queue migration. It should be executed during the next event infrastructure touch.

### Standard 3: Delivery Semantics Posture

Delivery semantics (at-least-once, ordering guarantees, deduplication) are properties of the managed queue service, not application-architecture standards. The application documents which managed service semantics it relies on, but does not codify them as app-level standards.

When adopting a managed queue:

1. **Document relied-upon semantics**: Record which delivery guarantees the application depends on (e.g., "SQS standard queue: at-least-once delivery, best-effort ordering") in the queue service's implementation documentation.
2. **Idempotent consumers**: Queue consumers should be idempotent — processing the same message twice must produce the same outcome. Use the `IdempotencyService` (ADR-0077) for deduplication where needed.
3. **Ordering**: If a feature requires ordered processing, it must implement ordering within the consumer (sequence numbers, causality tracking), not rely on broker ordering guarantees.

> **Revision (2026-04-30 — Managed Service Delegation Review):** Standard 3 was narrowed from prescribing at-least-once delivery, idempotency enforcement, and ordering policies as app-level standards to a posture statement. Delivery semantics are the managed service's responsibility (SQS owns at-least-once delivery; the app doesn't define it). The app documents which semantics it relies on. See ADR-0045 P7: the managed service owns availability, scaling, and delivery guarantees.

### Standard 4: Dead-Letter Queue Posture

Dead-letter queue (DLQ) configuration is an infrastructure-as-code concern (Terraform), not an application architecture standard. When the application adopts a managed queue:

1. **DLQ configuration**: DLQ setup (max receive count, DLQ queue ARN) is configured in Terraform, not in application code.
2. **Application responsibility**: The application handles poison messages by logging structured context (message_id, queue_name, attempt_count, last_error, correlation_id) per ADR-0054 and not crashing. The application does not implement DLQ routing — the managed service handles that.
3. **DLQ monitoring**: DLQ depth monitoring and alerting are configured in Terraform (CloudWatch alarms).

> **Revision (2026-04-30 — Managed Service Delegation Review):** Standard 4 was narrowed from prescribing DLQ configuration, retry counts, backoff policies, and poison-message handling as app-level standards to a posture statement. DLQ mechanics are an SQS/Terraform configuration concern, not an app architecture concern. The app logs failures and doesn't crash; the managed service handles DLQ routing. See ADR-0045 P7: the managed service owns these operational mechanics.

### Standard 5: Consumer Lifecycle Integration

Queue consumers must integrate with the lifespan model (ADR-0046):

1. **Startup phase**: Queue consumers start during lifespan phase 5 (transport phase), after all services, plugins, and feature handlers are initialized. This ensures that consumer handlers can safely use injected services.
2. **Registration**: Queue consumers register via pluggy hookspecs (ADR-0049 Standard 7).
3. **Shutdown**: Queue consumers stop during shutdown step 2 (per ADR-0046 Invariant 4 and ADR-0057 Standard 2): stop polling, drain in-flight messages within the shutdown timeout budget. Messages not acknowledged within the timeout are returned to the queue (visibility timeout expiry).

Health checks, poll intervals, and drain semantics are implementation details of the queue consumer adapter, not architecture standards. They are determined when wrapping the specific managed service SDK.

> **Revision (2026-04-30 — Managed Service Delegation Review):** Standard 5 was simplified from a detailed specification (health checks, poll intervals, drain semantics, consumer registration hookspec signatures) to the essential lifecycle integration points. Implementation details belong in the adapter code, not in the architecture standard. See ADR-0045 P7: the managed service adapter owns operational implementation details.

### Standard 6: Queue Settings Partitioning

Queue-specific settings follow ADR-0055 Standard 1 (independent singleton per domain) and Standard 9 (backend-selection pattern):

1. **`QueueSettings`**: A `BaseSettings` class defining queue infrastructure configuration:
   - `QUEUE_BACKEND: Literal["memory", "sqs"] = "memory"` — Backend selection per ADR-0055 Standard 9. Default `"memory"` for dev-safe startup.
   - `QUEUE_ENDPOINT_URL: str | None = None` — Broker endpoint (for SQS). Release-phase bound (ADR-0052).

2. **Provider**: `get_queue_settings()` with `@lru_cache(maxsize=1)`.
3. **Infrastructure-owned**: Queue settings are infrastructure-owned (ADR-0055 Standard 9 K5).

Visibility timeout, max retries, poll interval, and other operational settings are the managed service's configuration (set in Terraform), not application settings. Only settings that affect which implementation the application constructs belong in `QueueSettings`.

> **Revision (2026-04-30 — Managed Service Delegation Review):** Standard 6 was narrowed from specifying `QUEUE_DEFAULT_VISIBILITY_TIMEOUT`, `QUEUE_DEFAULT_MAX_RETRIES`, `QUEUE_POLL_INTERVAL_SECONDS`, and per-queue feature overrides to the essential backend-selection keys only. Operational settings (visibility timeout, max retries) are the managed service's domain, configured in Terraform. The application only needs to know which backend to construct. See ADR-0045 P7: the managed service owns operational configuration.

### Standard 7: Evolution Phases

The migration from the current in-process model to managed queue-backed processing follows a phased approach aligned with the delegation hierarchy (ADR-0045 P7):

1. **Phase 0 (current — in-process)**: In-process event dispatcher + `schedule`-based background jobs + DynamoDB retry queue. No external message broker. ADR-0058 governs this phase.
2. **Phase 1 (event dispatcher remediation)**: Fix import-time side effects (Standard 2). Encapsulate handler registry. Add pluggy-based handler registration. No functional change to delivery semantics. **Independent of queue adoption.**
3. **Phase 2 (managed queue adoption)**: Adopt a managed queue service (SQS per Tier 1 preference). Wrap the SDK in a thin Protocol-backed facade (Standard 1). Add `QUEUE_BACKEND` settings (Standard 6). Add in-memory fallback for dev/test. Integrate consumer lifecycle with lifespan (Standard 5). DLQ configured in Terraform (Standard 4).
4. **Phase 3 (feature migration)**: Individual features opt into managed queue-backed processing for specific operations. Each migration is a Tier-5 ADR. Migration is per-feature and incremental.
5. **Phase 4 (evaluate worker separation)**: When queue consumer volume or resource contention outgrows the colocated model (ADR-0058 Standard 4), evaluate separating queue consumers into a dedicated worker ECS service.

> **Revision (2026-04-30 — Managed Service Delegation Review):** Standard 7 was reframed from "building queue infrastructure" to "adopting a managed queue service." Phase 2 description was changed from implementing custom Protocols and DLQ infrastructure to adopting a managed service (SQS) with thin SDK wrapper and Terraform-configured DLQ. This aligns with ADR-0045 P7: managed cloud service is the preferred delegation tier for queue infrastructure.

## Alternatives Considered

1. Mandate SQS immediately:
   - Pros: Concrete target; SQS is already referenced in retry settings.
   - Cons: Premature for current workload. The colocated model works for the current scale. Adding SQS infrastructure (IAM, VPC endpoints, monitoring) before it is needed creates operational burden.
   - Why not chosen: Standards should be broker-agnostic. The phased evolution (Standard 7) allows SQS adoption when triggered by concrete needs.
2. Use Celery or a task queue library:
   - Pros: Mature ecosystem; worker management built-in.
   - Cons: Heavy dependency; brings its own broker requirements (Redis, RabbitMQ); architectural mismatch with the FastAPI lifespan model (Celery has its own worker lifecycle). ADR-0058 Standard 8 (library-agnostic) applies.
   - Why not chosen: The application's colocated single-process model and existing retry infrastructure make a lightweight Protocol-based abstraction more appropriate than a full task queue framework.
3. Use Redis Streams instead of SQS:
   - Pros: Lower latency; simpler infrastructure if Redis is already deployed.
   - Cons: No Redis in current infrastructure; SQS is already referenced in configuration; Redis adds operational burden (persistence, replication, monitoring).
   - Why not chosen: The standard is broker-agnostic. Backend selection is an infrastructure decision deferred to Phase 2.
4. Skip this ADR and add queue patterns ad-hoc:
   - Pros: Less governance overhead.
   - Cons: Without a standard, queue integrations will create inconsistent patterns (different DLQ strategies, no Protocol contracts, no lifecycle integration). The retry store's planned SQS backend already needs architectural guidance.
   - Why not chosen: Proactive governance prevents drift.
5. Merge with ADR-0058 (Background Execution):
   - Pros: Single record for all async execution.
   - Cons: ADR-0058 governs the colocated scheduled worker model (library-agnostic, daemon thread lifecycle). Queueing is a separate concern — durable message delivery, consumer lifecycle, dead-letter handling. Merging would create an oversized record mixing two distinct domains.
   - Why not chosen: Separation of concerns. ADR-0058 references this record for the evolution path; they are complementary, not overlapping.

## Consequences

- Positive impacts:
- Proactive architectural standard prevents ad-hoc queue integrations.
- Protocol-based abstraction enables broker substitution (SQS, Redis, in-memory) without feature-level changes.
- Event dispatcher remediation fixes an ADR-0048 B4 violation and aligns with the pluggy-based registration model.
- Phased evolution avoids premature infrastructure complexity.
- Consumer lifecycle integration ensures queue consumers participate in graceful shutdown.
- Tradeoffs accepted:
- The Protocol definitions (Standard 1) are aspirational until Phase 2. This is acceptable — defining the target interface before implementation ensures aligned implementation.
- At-least-once delivery requires idempotent consumers, which adds per-consumer implementation burden. This is a fundamental tradeoff of durable messaging and cannot be avoided.
- The event dispatcher remediation (Standard 2) requires touching existing handler registrations across the codebase. This is a one-time migration cost to fix an ADR-0048 B4 violation.
- Risks introduced:
- Protocol definitions authored before implementation may need revision when the first broker is integrated. Mitigation: the Protocol is minimal and follows established patterns (send/receive/acknowledge); revision scope should be small.
- Phase 2 SQS integration adds infrastructure complexity (IAM, VPC endpoints, DLQ, CloudWatch alarms). Mitigation: the existing Terraform infrastructure already manages SQS for other services; the pattern is established.
- Consumer lifecycle integration adds startup/shutdown complexity. Mitigation: the existing platform provider lifecycle (ADR-0046) provides a reference pattern for transport-phase start/stop.
- Mitigations:
- Phased evolution (Standard 7) limits blast radius — each phase is independently deployable and reversible.
- ADR-0077 Standard 5 defines the independently deployable Protocol migration path.
- ADR-0057 shutdown budgeting applies to queue consumers, preventing hung consumer shutdown.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Queue service facade and Protocol are infrastructure-owned (`app/infrastructure/queues/` or `app/infrastructure/events/`). Feature packages consume them via the injection boundary (ADR-0048 B2). Feature packages register queue consumers via pluggy hooks (ADR-0049 Standard 7).
- Type boundary impact: Queue Protocol shape emerges from wrapping the managed service SDK (Standard 1). Queue settings use Pydantic `BaseSettings` (configuration boundary). These follow ADR-0040 type boundary rules.
- Startup/plugin registration impact: Queue consumer registration happens during lifespan phase 3 (discovery and registration) via pluggy hookspecs. Event handler registration happens during phase 4 (feature activation). Consumer start happens during phase 5 (transport). No import-time side effects (ADR-0048 B4). Event handler registration must migrate from import-time decorators to startup-driven pluggy hooks (Standard 2).
- Settings partitioning impact: Standard 6 mandates `QueueSettings` with `QUEUE_BACKEND` and `QUEUE_ENDPOINT_URL` as backend-selection keys. Operational settings (visibility timeout, max retries) are configured in Terraform, not in application settings.
- DI alias ceremony impact: Queue Protocol follows ADR-0056 Standard 4 — provider function in `providers.py`, `Annotated[..., Depends(...)]` in `dependencies.py`.
- Service contract impact: Queue services are Category A per ADR-0077 (Standard 1). `EventDispatcher` is Category B (shared utility, concrete OK — it does not abstract a backing service in the current in-process model; reclassify to Category A if migrated to a durable broker).
- Managed service delegation impact: Standards 3 and 4 were narrowed to posture statements — delivery semantics and DLQ configuration are the managed service's responsibility. The application documents relied-upon semantics but does not codify them. Standard 1 defers Protocol shape to implementation time. This aligns with ADR-0045 P7 (Tier 1 — managed cloud service preferred).
- Graceful shutdown impact: Queue consumers must respect ADR-0057 Standard 2 shutdown timeout budgeting (Standard 5).
- Background execution relationship: ADR-0058 governs the colocated scheduled worker model. This standard governs queue-backed asynchronous processing. They are complementary.

## Codebase Audit (2026-04-29)

### Current State

| Component | Status | Violation |
|-----------|--------|-----------|
| `app/infrastructure/resilience/retry/` | Retry store with `RetryStore` and `RetryProcessor` Protocols. Multi-backend config (`memory`, `dynamodb`, `sqs`). SQS not implemented. | Standard 1 — aspirational; no immediate violation. Existing Protocols align directionally. |
| `app/infrastructure/events/dispatcher.py` | Global `EVENT_HANDLERS` dict. `@register_event_handler` decorator registers at import time. `dispatch_event()` with ThreadPoolExecutor. | **Standard 2 violation** — import-time side effects (ADR-0048 B4). |
| `app/infrastructure/events/service.py` | `EventDispatcher` class wraps module-level functions. | Standard 2 — facade exists but delegates to module-level globals. |
| `app/jobs/scheduled_tasks.py` | `schedule`-library scheduler with pluggy-based `BackgroundJobRegistry`. | No violation — governed by ADR-0058, not this standard. |
| `app/infrastructure/configuration/infrastructure/retry.py` | `RETRY_BACKEND` with `sqs` option. | Standard 6 — directionally aligned; needs `QueueSettings` extraction when SQS is implemented. |

### Immediate Remediation Required

| Action | Priority | Standard | Dependencies |
|--------|----------|----------|--------------|
| Encapsulate `EVENT_HANDLERS` in `EventDispatcher` instance | P1 | Standard 2 | None |
| Replace `@register_event_handler` with pluggy hookspec | P1 | Standard 2 | ADR-0049 compliance |
| Add `register_event_handlers` hookspec | P1 | Standard 2 | Plugin manager update |
| Remove module-level handler registration from all consumers | P1 | Standard 2 | After hookspec available |

### Deferred Actions (Phase 2+)

| Action | Phase | Standard | Trigger |
|--------|-------|----------|---------|
| Wrap managed queue SDK in Protocol-backed facade | Phase 2 | Standard 1 | First durable queue need |
| Implement SQS backend for retry store | Phase 2 | Standard 1 | Retry volume exceeds DynamoDB cost-efficiency |
| Configure DLQ in Terraform | Phase 2 | Standard 4 | First durable queue deployment |
| Define `QueueSettings` with `QUEUE_BACKEND` | Phase 2 | Standard 6 | First durable queue deployment |
| Implement consumer lifecycle in lifespan | Phase 2 | Standard 5 | First queue consumer |

## Best-Practice Revalidation

- Revalidation date: 2026-04-29
- Sources rechecked:
- Twelve-Factor App Factor VIII: Concurrency (<https://12factor.net/concurrency>) — process type diversity; web vs. worker.
- Enterprise Integration Patterns (Hohpe, Woolf) — message channel, dead-letter channel, idempotent receiver patterns.
- AWS SQS Best Practices (<https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-best-practices.html>) — visibility timeout, DLQ configuration, at-least-once delivery.
- Cosmic Python Ch. 11: Event-Driven Architecture (<https://www.cosmicpython.com/book/chapter_11_external_events.html>) — message broker abstractions, handler registration patterns.
- PEP 544 Protocols: Structural subtyping (<https://peps.python.org/pep-0544/>) — Protocol-based queue abstractions.
- Seemann, Mark. "Dependency Injection in .NET" (2011) — Composition Root pattern for service wiring.
- Alignment summary:
- Standard 1 (queue integration) aligns with Hexagonal Architecture ports and Cosmic Python's message bus abstraction. The Protocol shape is deferred to implementation time, consistent with the "wrap the SDK" guidance from managed service best practices.
- Standard 2 (event dispatcher remediation) aligns with Cosmic Python Ch. 11's guidance on separating handler discovery from handler registration.
- Standard 3 (delivery semantics posture) aligns with AWS SQS's native at-least-once delivery model — the app documents reliance on the managed service's semantics rather than reimplementing them.
- Standard 4 (DLQ posture) aligns with AWS SQS DLQ best practices — DLQ configuration is infrastructure-as-code, not application architecture.
- Standard 5 (consumer lifecycle) aligns with Twelve-Factor Factor VIII (process types) and the existing lifespan transport-phase model.
- Standard 7 (evolution phases) aligns with ADR-0058's explicit acknowledgment that the colocated model has a bounded lifetime, reframed around managed service adoption per ADR-0045 P7.
- Intentional deviations:
- The standard does not mandate separate worker processes (Factor VIII) because the current deployment model is single-process ECS Fargate. Worker separation is an evolution trigger (Standard 7 Phase 4), not a current mandate.
- The standard does not prescribe a broker. This deviates from opinionated frameworks (Celery mandates Redis/RabbitMQ) but is correct for an architecture standard that governs the abstraction layer, not the implementation.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Tier-2 standard narrowed by managed service delegation review (2026-04-30). Standards 1/3/4/5/6/7 revised to align with ADR-0045 P7 delegation hierarchy. Pre-designed Protocols deferred to implementation time. Delivery semantics and DLQ configuration delegated to managed service. Evolution phases reframed around managed service adoption. Standard 2 (event dispatcher remediation) unchanged.
- Follow-up actions:
- Execute P1 event dispatcher remediation (Standard 2): encapsulate global handler registry, add pluggy hookspec, migrate handler registrations.
- Add `register_event_handlers` hookspec to plugin manager.
- Update ADR-0058 related_records to include ADR-0079.

## Change Log

| Date | Section | Change Summary |
|------|---------|----------------|
| 2026-04-29 | All | Initial Draft — full queueing and message-broker architecture standard. |
| 2026-04-30 | Standards 1, 3, 4, 5, 6, 7, Compliance, Audit, Revalidation | Managed service delegation rework: narrowed Standard 1 from pre-defined Protocols to queue integration standard; narrowed Standards 3/4 to posture statements (managed service owns delivery semantics and DLQ); simplified Standard 5 to essential lifecycle points; narrowed Standard 6 to backend-selection keys only; reframed Standard 7 evolution phases around managed service adoption. Aligned with ADR-0045 P7 delegation hierarchy. |

## Source References

1. Source title: Twelve-Factor App - Factor VIII: Concurrency
   - URL: <https://12factor.net/concurrency>
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Process type diversity; web vs. worker separation trigger.
2. Source title: Enterprise Integration Patterns
   - URL: <https://www.enterpriseintegrationpatterns.com/>
   - Publisher/maintainer: Gregor Hohpe, Bobby Woolf
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Message channel, dead-letter channel, idempotent receiver patterns.
3. Source title: AWS SQS Best Practices
   - URL: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-best-practices.html>
   - Publisher/maintainer: Amazon Web Services
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: At-least-once delivery, visibility timeout, DLQ configuration.
4. Source title: Cosmic Python Ch. 11 - Event-Driven Architecture
   - URL: <https://www.cosmicpython.com/book/chapter_11_external_events.html>
   - Publisher/maintainer: Harry Percival, Bob Gregory
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Message bus abstraction, handler discovery vs. registration separation.
5. Source title: PEP 544 - Protocols: Structural subtyping
   - URL: <https://peps.python.org/pep-0544/>
   - Publisher/maintainer: Python Software Foundation
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Protocol-based queue abstractions.
6. Source title: ADR-0058 - Background Execution and Worker Isolation Standard
   - URL: docs/decisions/adr/0058-background-execution-and-worker-isolation-standard.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Colocated worker model; evolution path delegation to this record.

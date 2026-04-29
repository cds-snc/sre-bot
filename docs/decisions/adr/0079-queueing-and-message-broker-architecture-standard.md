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
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-27
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

### Standard 1: Queue Abstraction Layer

Queue interactions must be mediated through a Protocol-based abstraction layer:

1. **Message Producer Protocol**: A `MessageProducer` Protocol defines the outbound message interface:
   - `send(queue_name: str, message: MessageEnvelope) → OperationResult[None]`
   - `send_batch(queue_name: str, messages: list[MessageEnvelope]) → OperationResult[BatchResult]`

2. **Message Consumer Protocol**: A `MessageConsumer` Protocol defines the inbound message interface:
   - `receive(queue_name: str, max_messages: int, visibility_timeout: int) → OperationResult[list[MessageEnvelope]]`
   - `acknowledge(queue_name: str, receipt_handle: str) → OperationResult[None]`
   - `reject(queue_name: str, receipt_handle: str, delay: int) → OperationResult[None]`

3. **MessageEnvelope**: A `@dataclass(frozen=True)` carrying:
   - `message_id: str` — unique message identifier.
   - `body: dict[str, Any]` — serialized message payload.
   - `attributes: dict[str, str]` — message metadata (correlation_id, event_type, source, timestamp).
   - `receipt_handle: str | None` — broker-specific acknowledgment handle (populated on receive, None on send).

4. **Classification**: `MessageProducer` and `MessageConsumer` are **Category A** per ADR-0077 — they abstract a backing service (SQS, Redis, in-memory) and are consumed by feature packages. Protocol contracts are required.

These Protocols are not required until the first durable queue integration is implemented. This standard establishes the target interface so that implementation is aligned from the start.

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

### Standard 3: Delivery Semantics

All durable queue integrations must implement **at-least-once delivery**:

1. **At-least-once guarantee**: Messages are guaranteed to be delivered at least once. Consumers must be idempotent — processing the same message twice must produce the same outcome.
2. **Idempotency enforcement**: Queue consumers must use the idempotency service (ADR-0077 Standard 1, `IdempotencyService`) to deduplicate messages. The `message_id` (Standard 1) is the idempotency key.
3. **Exactly-once is not guaranteed**: The standard explicitly does not require exactly-once delivery. Exactly-once semantics are broker-specific and add significant complexity. At-least-once with idempotent consumers is the target model.
4. **Ordering**: Message ordering is not guaranteed across queue consumers. Features that require ordered processing must implement ordering within the consumer (e.g., sequence numbers, causality tracking).
5. **In-process event dispatcher**: The current in-process event dispatcher provides at-most-once delivery (fire-and-forget with `ThreadPoolExecutor`). This is acceptable for non-critical, observability-focused events (audit trail enrichment, metrics emission). Critical business events that require durability must use the durable queue path when available.

### Standard 4: Dead-Letter and Poison-Message Policy

1. **Dead-letter queue (DLQ)**: Every durable queue must have a configured dead-letter queue. Messages that fail processing after the maximum retry count are moved to the DLQ, not silently dropped.
2. **Maximum retry count**: Configurable per queue via settings (ADR-0055). Default: 3 retries with exponential backoff.
3. **Poison-message detection**: A message that fails all retries is a poison message. The DLQ handler must:
   - Log the poison message with structured context (message_id, queue_name, attempt_count, last_error, correlation_id) per ADR-0054.
   - Emit a notification via the notification service (ADR-0077 P2 migration candidate) if configured.
   - Never automatically reprocess poison messages. Manual intervention or explicit replay is required.
4. **DLQ monitoring**: DLQ depth must be observable. The operations team must be alerted when DLQ messages accumulate beyond a configured threshold.
5. **Retry backoff**: Retry delays must use exponential backoff with jitter, consistent with the retry infrastructure's existing `RetryRecord` model (base delay, max delay). Queue-level retry delays are separate from application-level retry (ADR-0050 `retry_after`) — queue retry is infrastructure-level; application retry is service-level.

### Standard 5: Consumer Lifecycle Integration

Queue consumers must integrate with the lifespan model (ADR-0046):

1. **Startup phase**: Queue consumers start during lifespan phase 5 (transport phase), after all services, plugins, and feature handlers are initialized. This ensures that consumer handlers can safely use injected services.
2. **Registration**: Queue consumers register via pluggy hookspecs (ADR-0049 Standard 7):
   - `register_queue_consumers(registry: QueueConsumerRegistry)` hookspec — feature packages implement this to register consumer handlers.
   - Consumer registration includes: queue name, handler function, concurrency settings, and DLQ configuration.
3. **Shutdown**: Queue consumers stop during shutdown step 2 (reverse of phase 5 — background work stops first in step 1, then transport connections including queue consumers stop in step 2, per ADR-0046 Invariant 4 and ADR-0057 Standard 2):
   - Stop polling for new messages.
   - Drain in-flight messages within the shutdown timeout budget (ADR-0057 Standard 2).
   - Messages not acknowledged within the timeout are returned to the queue (visibility timeout expiry).
   - Log shutdown completion with message counts (drained, returned).
4. **Health check**: Queue consumer health is part of the application health check. A consumer that fails to poll for longer than a configured threshold is unhealthy.

### Standard 6: Queue Settings Partitioning

Queue-specific settings follow ADR-0055 Standard 1 (independent singleton per domain):

1. **`QueueSettings`**: A `BaseSettings` class defining queue infrastructure configuration:
   - `QUEUE_BACKEND`: Backend type (`memory`, `sqs`, `redis`). Default: `memory`.
   - `QUEUE_ENDPOINT_URL`: Broker endpoint (for SQS, Redis). Release-phase bound (ADR-0052).
   - `QUEUE_DEFAULT_VISIBILITY_TIMEOUT`: Seconds before an unacknowledged message becomes visible again. Default: 30.
   - `QUEUE_DEFAULT_MAX_RETRIES`: Maximum delivery attempts before DLQ. Default: 3.
   - `QUEUE_POLL_INTERVAL_SECONDS`: Consumer poll frequency. Default: 10.

2. **Provider**: `get_queue_settings()` with `@lru_cache(maxsize=1)`.
3. **Per-queue overrides**: Feature packages may define queue-specific settings in their own settings module (e.g., `packages/<feature>/settings.py`) for queue name, visibility timeout, and retry count. Feature settings override defaults.

### Standard 7: Evolution Phases

The migration from the current in-process model to durable queue-backed processing follows a phased approach:

1. **Phase 0 (current)**: In-process event dispatcher + `schedule`-based background jobs + DynamoDB retry queue. No SQS or external message broker. ADR-0058 governs this phase.
2. **Phase 1 (event dispatcher remediation)**: Fix import-time side effects (Standard 2). Encapsulate handler registry. Add pluggy-based handler registration. No functional change to delivery semantics.
3. **Phase 2 (durable queue infrastructure)**: Implement `MessageProducer` and `MessageConsumer` Protocols with an SQS backend. Implement DLQ configuration. Implement consumer lifecycle integration (Standard 5). Settings partitioning (Standard 6).
4. **Phase 3 (feature migration)**: Individual features opt into durable queue-backed processing for specific operations (e.g., access sync entitlement application, webhook delivery). Migration is per-feature and incremental. Each migration is a Tier-5 ADR.
5. **Phase 4 (evaluate worker separation)**: When queue consumer volume or side-effect complexity outgrows the colocated model (ADR-0058 Standard 4 two-tier classification), evaluate separating queue consumers into a dedicated worker ECS service. This is not mandated — it is an evaluation trigger.

**Evolution triggers** (from ADR-0058 Standard 4):

- Job execution time regularly exceeds the shutdown timeout budget (ADR-0057).
- Queue consumer processing creates resource contention with the web server (CPU, memory, connection pool exhaustion).
- Horizontal scaling requirements differ between web and worker workloads.

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

- Package/infrastructure boundary impact: Queue Protocols (`MessageProducer`, `MessageConsumer`) are infrastructure-owned (`app/infrastructure/queues/` or `app/infrastructure/events/`). Feature packages consume them via the injection boundary (ADR-0048 B2). Feature packages register queue consumers via pluggy hooks (ADR-0049 Standard 7).
- Type boundary impact: `MessageEnvelope` is a `@dataclass(frozen=True)` (internal data carrier). Queue Protocols use `Protocol` (service contracts). Queue settings use Pydantic `BaseSettings` (configuration boundary). These follow ADR-0040 type boundary rules.
- Startup/plugin registration impact: Queue consumer registration happens during lifespan phase 3 (discovery and registration) via pluggy hookspecs. Event handler registration happens during phase 4 (feature activation). Consumer start happens during phase 5 (transport). No import-time side effects (ADR-0048 B4). Event handler registration must migrate from import-time decorators to startup-driven pluggy hooks (Standard 2).
- Settings partitioning impact: Standard 6 mandates `QueueSettings` extraction with independent singleton provider. Feature-specific queue settings follow ADR-0055 Standard 3 (package-local settings).
- DI alias ceremony impact: Queue Protocols follow ADR-0056 Standard 4 — provider function in `providers.py`, `Annotated[MessageProducerProtocol, Depends(get_message_producer)]` in `dependencies.py`.
- Service contract impact: `MessageProducer` and `MessageConsumer` are Category A per ADR-0077. `EventDispatcher` is Category B (shared utility, concrete OK — it does not abstract a backing service in the current in-process model; reclassify to Category A if migrated to a durable broker).
- Graceful shutdown impact: Queue consumers must respect ADR-0057 Standard 2 shutdown timeout budgeting. In-flight messages must be drained or returned within the shutdown window.
- Background execution relationship: ADR-0058 governs the colocated scheduled worker model. This standard governs queue-backed asynchronous processing. They are complementary: background jobs may produce messages to queues; queue consumers are a separate async execution path.

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
| Implement `MessageProducer` Protocol | Phase 2 | Standard 1 | First durable queue need |
| Implement `MessageConsumer` Protocol | Phase 2 | Standard 1 | First durable queue need |
| Implement SQS backend for retry store | Phase 2 | Standard 1 | Retry volume exceeds DynamoDB cost-efficiency |
| Implement DLQ infrastructure | Phase 2 | Standard 4 | First durable queue deployment |
| Define `QueueSettings` | Phase 2 | Standard 6 | First durable queue deployment |
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
- Standard 1 (Protocol abstraction) aligns with Hexagonal Architecture ports and Cosmic Python's message bus abstraction. The `MessageProducer`/`MessageConsumer` split follows the Enterprise Integration Patterns message channel pattern.
- Standard 2 (event dispatcher remediation) aligns with Cosmic Python Ch. 11's guidance on separating handler discovery from handler registration.
- Standard 3 (at-least-once delivery) aligns with AWS SQS's native delivery model and Enterprise Integration Patterns' idempotent receiver.
- Standard 4 (DLQ) aligns with Enterprise Integration Patterns' dead-letter channel and AWS SQS DLQ best practices.
- Standard 5 (consumer lifecycle) aligns with Twelve-Factor Factor VIII (process types) and the existing lifespan transport-phase model.
- Standard 7 (evolution phases) aligns with ADR-0058's explicit acknowledgment that the colocated model has a bounded lifetime.
- Intentional deviations:
- The standard does not mandate separate worker processes (Factor VIII) because the current deployment model is single-process ECS Fargate. Worker separation is an evolution trigger (Standard 7 Phase 4), not a current mandate.
- The standard does not prescribe a broker. This deviates from opinionated frameworks (Celery mandates Redis/RabbitMQ) but is correct for an architecture standard that governs the abstraction layer, not the implementation.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: New Tier-2 standard establishing queue architecture, consumer lifecycle, delivery semantics, and phased evolution from in-process async to durable queue-backed processing. No legacy ADR superseded (new coverage gap). All upstream constraint references verified against current accepted ADRs.
- Follow-up actions:
- Execute P1 event dispatcher remediation (Standard 2): encapsulate global handler registry, add pluggy hookspec, migrate handler registrations.
- Add `register_event_handlers` hookspec to plugin manager.
- Update ADR-0058 related_records to include ADR-0079.

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

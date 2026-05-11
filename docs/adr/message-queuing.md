---
title: "Message Queuing"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application, operations]
concerns: [architecture, data]
constrained_by: [layered-architecture.md, infrastructure-service-classification.md, application-lifecycle.md, plugin-registration-discovery.md, handler-idempotency.md, operation-result-pattern.md, cross-channel-correlation.md, configuration-ownership.md, logging-observability.md, cloud-portability.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Message Queuing

## Context and Problem Statement

Some work belongs to a producing intent but does not need to be done synchronously inside it: a notification that goes out after an approval is committed, a reconciliation step that runs after an account is provisioned, a fan-out to several downstream systems triggered by one upstream change. Doing this work inline lengthens the producer's response time and binds the producer's success to the downstream system's availability; doing it in-process — through the in-process domain-event dispatcher — is fine for effects that can tolerate process-local delivery and process-death loss, but unfit for effects that must survive the producing process or run on a different process.

The problem this record addresses: **what is the standard for cross-process, durable, at-least-once delivery of work between the application's processes — its broker, its message shape, its producer-side write contract, its consumer-side execution contract, its dead-letter handling, and its multi-step (saga) composition?** The answer determines:

1. Whether a producing handler can hand off downstream effects without holding open the request, and whether that handoff is durable across process death.
2. Whether a multi-step domain workflow (a "saga") composes through cleanly defined message contracts or through ad-hoc wiring.
3. Whether a partially-applied handler that crashes after a domain commit but before a downstream effect has a recovery path, or whether the system is left in an inconsistent state.
4. Whether queue messages are a *control-plane signal* (carrying just enough to identify the work) or a *state-carrier* (carrying domain payloads that consumers must trust).

**Constraints:**

- The application runs as N stateless processes ([cloud-portability.md](cloud-portability.md)). Cross-process work cannot be coordinated through process memory; it requires a backing service that survives process replacement.
- Composed infrastructure services are vendor-portable in shape ([infrastructure-service-classification.md](infrastructure-service-classification.md): Path A; [cloud-portability.md](cloud-portability.md)). The queueing capability is exposed to features as a Protocol that names the *capability*, not a vendor's API. AWS is the day-0 implementation of every backing service; the architecture must support swappable providers (Azure, GCP, in-process for local/CI) without feature-code changes.
- Every mutating handler is idempotency-keyed by `(feature, intent, correlation_id)` ([handler-idempotency.md](handler-idempotency.md)). Queue messages for the same intent must produce the same key on every redelivery.
- Service-layer outcomes use the closed five-status envelope ([operation-result-pattern.md](operation-result-pattern.md)). Producers and consumers compose through that envelope; the queue does not invent a parallel result type.
- Correlation context propagates through every transport ([cross-channel-correlation.md](cross-channel-correlation.md)). Queue-driven work inherits the originating correlation ID.
- Backing-service URLs and credentials live with the consuming service per [configuration-ownership.md](configuration-ownership.md). The queue's endpoint is a settings-class attribute, not an env-var read scattered through call sites.
- The plugin model ([plugin-registration-discovery.md](plugin-registration-discovery.md)) is the registration shape. Consumer attachment composes with it.

**Non-goals:**

- This record does not redefine in-process event semantics ([event-dispatch.md](event-dispatch.md)). In-process events stay in-process; cross-process delivery is what this record is for.
- This record does not commit the application to a single broker forever. AWS SQS (paired with DynamoDB for the outbox store) is the day-0 implementation; equivalent providers on other clouds are explicitly substitutable behind the same Protocol.
- This record does not own the inbound retry/idempotency contract ([handler-idempotency.md](handler-idempotency.md)). Consumer-side dedup follows the same rules as request handlers.
- This record does not own scheduled background work ([background-execution.md](background-execution.md)). A consumer is not a scheduled job; a scheduled job is not a consumer.
- This record does not introduce a centralized workflow orchestrator (Step Functions, Temporal, Airflow). Sagas in this application are choreographed through queue messages, not directed by an external coordinator.

## Considered Options

**Option 1 — Capability-shaped Protocol with two queue *kinds* (ordered-with-deduplication, unordered fan-out); transactional-outbox pattern for atomicity between entity write and message send; consumers attached as plugins; saga choreography through chained continuation messages.** The application owns a Path-A `QueueService` Protocol that names cross-process at-least-once delivery without naming a vendor. Producers write entity + outbox marker atomically in the durable store; a relay reads the outbox marker and publishes to the queue. Consumers re-fetch state from the durable store; messages carry only `(feature, intent, correlation_id)`. Day-0 implementation: AWS SQS (FIFO + Standard) with the outbox in DynamoDB, relayed via DynamoDB Streams. Other implementations (Azure Service Bus, GCP Pub/Sub, an in-process queue for local/CI) are explicitly substitutable behind the same Protocol.

**Option 2 — Direct, synchronous downstream calls.** No queue. Every effect runs inline in the producer's request. Failures fail the request.

**Option 3 — Self-hosted broker (RabbitMQ, Kafka).** Operate a broker inside the deployment. Better feature set on some axes; substantial operational surface.

**Option 4 — Best-effort send without outbox.** Producers send the queue message after the entity write returns; if the message send fails, the entity is committed but the work is lost. Recovery is manual.

**Option 5 — Vendor-shaped Protocol exposing the SQS API directly to features.** Features call `sqs.send_message(...)`; the queue is not abstracted.

## Decision Outcome

**Chosen: Option 1 — capability-shaped Protocol with the transactional-outbox pattern, plugin-registered consumers, and saga choreography. AWS SQS + DynamoDB is the day-0 implementation; the Protocol is provider-portable.**

This is the only option that combines (a) durability that survives process death, (b) atomicity between domain commit and queue send, (c) a recovery path for partial failure that is automatic at the boundary and operator-driven at the tail, (d) a saga shape that does not need a central coordinator, and (e) a contract that does not bind the application to AWS at the *feature-code* level. Direct synchronous calls (Option 2) couple the producer's response time and success to every downstream system. Self-hosted brokers (Option 3) carry operational cost the application does not need at its scale. Best-effort send without outbox (Option 4) is not durable; a process death between commit and send loses work silently. A vendor-shaped Protocol (Option 5) leaks SQS-specific concepts (`MessageGroupId`, `MessageDeduplicationId`, `ReceiptHandle`) into feature code, defeating the cloud-portability commitment.

### Where the queue lives

The queue is a **shared infrastructure capability** ([infrastructure-service-classification.md](infrastructure-service-classification.md): Path A, Shared). One Protocol exported to consumers, one DI-injected handle, one or more provider-specific implementations selected by configuration.

```text
app/infrastructure/queueing/
    __init__.py          # public surface: QueueService Protocol, QueueMessage value type
    in_memory.py         # in-process backend for local dev and CI
    aws.py               # AWS SQS-backed implementation (day-0 production)
    # azure.py, gcp.py … future provider implementations live here
    settings.py          # endpoint, region, dedup-window, visibility-timeout defaults
    consumer.py          # consumer runner + visibility-lease heartbeat
    outbox.py            # outbox-marker helpers + relay
```

Features depend on the Protocol, not on any vendor SDK. The implementation is selected by configuration (`QUEUE_BACKEND=memory|aws|...`); local development and tests use the in-memory backend, production runs against the cloud provider.

### Queue kinds

The Protocol distinguishes two queue *kinds*; a logical queue is one or the other.

- **Ordered-with-deduplication.** Messages within the same logical group (keyed by an application-owned string) are delivered to consumers in send order; duplicate sends within a bounded window are absorbed at the broker. Used for work tied to a domain entity, where two intents on the same entity must not be processed concurrently or out of order.
- **Unordered fan-out.** No ordering guarantee, no broker-side dedup window; messages are delivered at-least-once and consumers may run in parallel. Used for broadcasts and notifications where two messages on the same logical group are not order-dependent.

Per-queue kind is documented at the consumer's registration; the choice is a property of the work, not a global setting. Ordered-with-deduplication is the default for any work tied to a domain entity. Each work queue has a paired **dead-letter queue** (DLQ) with `max_delivery_attempts = 3` and 14-day retention; a consumer's exhausted message lapses to the DLQ for operator inspection.

Mapping to provider primitives:

- **AWS SQS (day 0):** *ordered-with-deduplication* maps to a FIFO queue (`*.fifo`) with `MessageGroupId` and `MessageDeduplicationId`; *unordered fan-out* maps to a Standard queue. The DLQ uses SQS's `RedrivePolicy` with `maxReceiveCount = 3`.
- **Azure Service Bus:** *ordered-with-deduplication* maps to a queue with sessions and duplicate detection; *unordered fan-out* maps to a queue without sessions. DLQ is the namespace's default `$DeadLetterQueue`.
- **GCP Pub/Sub:** *ordered-with-deduplication* maps to an ordered subscription with `enable_message_ordering` and an application-side dedup table (Pub/Sub does not deduplicate broker-side); *unordered fan-out* maps to a standard subscription. DLQ is a configured dead-letter topic.

The Protocol's contract is identical across these mappings; differences are confined to the provider-specific implementation file.

### Message shape

A queue message is a **control-plane signal**, not a state carrier. Its body carries exactly the fields a consumer needs to identify the work and reload state from the durable store:

```python
@dataclass(frozen=True, slots=True)
class QueueMessage:
    feature: str          # owning feature package
    intent: str           # domain command the consumer is to perform
    correlation_id: str   # UUID v4 — keys the originating intent's domain entity

    # Provider-managed metadata, populated on receive:
    message_id: str       # provider-issued unique id for this delivery
    lease_handle: str     # opaque token the consumer uses to acknowledge or extend the lease
    receive_count: int    # times this message has been delivered (1 = first delivery)
```

Rules:

- The message body is JSON `{"feature": ..., "intent": ..., "correlation_id": ...}`. No domain payloads, no entity snapshots, no transport context.
- The consumer re-fetches authoritative state from the durable store using `correlation_id` (the entity key). The queue does not act as a copy-of-truth.
- A future field added to the message (a hint, a routing key) is added through standard review and remains forward-compatible: consumers must tolerate unknown fields.
- The metadata fields are application-owned names. Each provider implementation populates them from its own primitives (e.g., AWS SQS's `ReceiptHandle` becomes `lease_handle`).

### Ordering and deduplication keys

For ordered-with-deduplication queues, the producer supplies two application-owned values to the Protocol:

- **`group_key = correlation_id`** — preserves ordering of intents within a single entity's lifecycle; permits parallelism across entities.
- **`dedup_id = idempotency_key`** — `<feature>:<intent>:<correlation_id>` ([handler-idempotency.md](handler-idempotency.md)). The broker absorbs duplicate sends carrying the same `dedup_id` within a bounded window; durable application-level dedup beyond that window lives in the dedup table per [handler-idempotency.md](handler-idempotency.md).

For unordered fan-out queues, neither value is used; consumer-side dedup is the only line of defence.

Mapping to provider primitives:

- **AWS SQS (day 0):** `group_key → MessageGroupId`; `dedup_id → MessageDeduplicationId` (5-minute broker dedup window).
- **Azure Service Bus:** `group_key → SessionId`; `dedup_id → MessageId` (with duplicate detection enabled and a configured `RequiresDuplicateDetection` window).
- **GCP Pub/Sub:** `group_key → ordering_key`; broker-side dedup not provided — the application's idempotency table is the only line of defence.

The 5-minute broker-side dedup window is therefore an *AWS-specific* affordance, not a Protocol guarantee. The Protocol's *durable* guarantee is provided by the dedup table at the consumer ([handler-idempotency.md](handler-idempotency.md)).

### Producer-side contract — transactional outbox

A producing handler that commits a domain transition and needs to enqueue a downstream message writes the entity, the idempotency record, and the **outbox marker** in **one atomic operation against the durable store**. The contract is:

- **Atomicity.** The entity write, the idempotency record, and the outbox marker succeed together or none of them do. There is no state in which the entity is committed but the work is lost.
- **No phantom outbox markers.** A failed transaction leaves nothing for the relay to send; a successful transaction guarantees the relay will see the marker.
- **No direct queue sends from handlers.** Direct send (`queue.publish(...)` from the handler body) is forbidden because it cannot be atomic with the entity write. The outbox is the only producer path for messages tied to a domain commit.

The outbox marker is a record with these fields, written to a durable store the application can transact against:

```text
outbox_id      — unique id for this marker
queue_name     — logical queue the relay should publish to
feature        — owning feature package
intent         — domain command
correlation_id — UUID v4 for the originating intent's domain entity
status         — "pending" on write; advanced by the relay
created_at     — epoch seconds
ttl            — bounded lifetime so abandoned markers are reclaimed
```

Mapping to provider primitives:

- **AWS DynamoDB (day 0):** the durable store is DynamoDB; the atomic operation is `TransactWriteItems` with three `Put` items (entity + idempotency record + outbox marker), an `attribute_not_exists` condition on the idempotency item, and `ClientRequestToken` derived from the idempotency key.
- **Azure Cosmos DB (NoSQL API):** transactional batch writes scoped to a partition key; the entity, idempotency record, and outbox marker share a partition key.
- **GCP Firestore:** a single transaction containing the three writes.
- **Relational stores (Postgres, MySQL):** the entity, idempotency record, and outbox marker share a single SQL transaction.

The Protocol's contract is "atomic write of three items in the durable store"; the implementation per provider varies but the property is the same.

### The relay

A separate component reads outbox markers and publishes them to the queue. The contract is:

- **Read pending markers** in (approximately) write order.
- **Publish each to the named queue.** Carry forward `feature`, `intent`, `correlation_id` as the message body; carry forward `correlation_id` as the `group_key` and `idempotency_key` as the `dedup_id` for ordered-with-deduplication queues.
- **On success, retire the marker** (delete or set `status = "sent"`).
- **On failure, retain the marker** so a subsequent relay attempt can retry.
- **Tolerate duplicate publishes.** Re-publishing an already-published message produces a duplicate at the queue; the broker's dedup window (where present) and the consumer's idempotency record absorb it.

Mapping to provider primitives:

- **AWS DynamoDB Streams + Lambda (day 0).** DynamoDB Streams emits an `INSERT` event for each new outbox marker; an AWS Lambda function consumes the stream, publishes to SQS, and retires the marker. DynamoDB Streams provides exactly-once event delivery per stream record within its 24-hour retention. This is the production relay.
- **Provider-native CDC equivalents.** Azure Cosmos DB Change Feed; GCP Firestore Change Streams; Postgres logical replication via Debezium. Each replaces the relay's "read marker" path with the provider's CDC primitive; the rest of the relay logic is unchanged.
- **Tier-1 background poller** ([background-execution.md](background-execution.md)). A scheduled job scans pending outbox markers older than a configurable threshold and forwards them. This is the fallback path used when CDC is not available (a region without Streams, a development environment with the in-memory backend, a provider whose CDC latency is unsuitable). Tier-1 is appropriate because the operation is conditional-write idempotent: each marker carries a unique key, and re-publishing an already-sent marker is absorbed by the consumer's dedup record.

The relay is what makes the boundary between "domain committed" and "message visible to consumers" both atomic and durable. The producing handler does not wait for the relay; the relay completes asynchronously.

### Consumer-side contract

Consumers attach through a Pluggy hookspec invoked once at lifespan **phase 4 (feature activation)**:

```python
@hookimpl
def register_queue_consumers(registry: QueueConsumerRegistry) -> None:
    registry.register(
        queue_name="access-sync.fifo",
        feature="access",
        intent="propagate_change",
        handler=_propagate_change_consumer,
        visibility_timeout_seconds=60,
        heartbeat_interval_seconds=30,
    )
```

Consumer execution lives at lifespan **phase 5 (transport)** — long-poll workers start with the rest of the inbound transport stack. Consumer rules:

- **Re-fetch state.** The consumer's first step is to fetch the domain entity from the durable store using `correlation_id`. If the entity is missing or in an unexpected state, the consumer logs and either acknowledges the message (work no longer applies) or raises (so the message returns to the queue for retry, eventually to the DLQ).
- **Idempotent execution.** The consumer's body invokes the same idempotency mechanism as request handlers ([handler-idempotency.md](handler-idempotency.md)). A duplicate delivery encounters the dedup record and returns the cached outcome.
- **Visibility-lease heartbeat.** The consumer extends the message's visibility lease on a heartbeat (default `visibility_timeout / 2` = 30s) for any work that may run longer than the initial timeout. The heartbeat is owned by the consumer runner, not the consumer body. The Protocol exposes one operation — `extend_lease(lease_handle, seconds)` — that each provider implementation maps to its primitive (AWS SQS: `ChangeMessageVisibility`; Azure Service Bus: `RenewMessageLock`; GCP Pub/Sub: `ModifyAckDeadline`).
- **Acknowledge on success.** Successful processing acknowledges the message (the Protocol's `ack(lease_handle)`; AWS maps this to `DeleteMessage`, Azure to `Complete`, GCP to `Acknowledge`). A `TRANSIENT_ERROR` outcome does not acknowledge; the message lapses, the visibility lease expires, and the broker redelivers (counting toward `max_delivery_attempts`). A `PERMANENT_ERROR` outcome may either acknowledge (the work is conclusively unrecoverable and the message should not be retried) or lapse to DLQ depending on the consumer's documented policy.

### Dead-letter queue

A message that fails processing `max_delivery_attempts = 3` times is automatically moved by the broker to the work queue's DLQ. DLQ rules:

- **14-day retention.** The DLQ holds messages long enough for operator inspection during a typical incident response.
- **Alarming.** A CloudWatch metric alarm on `ApproximateNumberOfMessagesVisible > 0` for any DLQ pages the on-call. A message arriving in the DLQ is always an operational event.
- **No automated replay.** The DLQ is operator-driven. An operator inspects the message (and the entity it references), decides whether the failure was transient or permanent, optionally amends the entity, and either replays the message back to the work queue (a documented operator command) or deletes it.
- **Replay is idempotent.** Replaying a message goes through the same dedup mechanism as a fresh delivery; if the work was already done before the failure, the dedup record returns the cached outcome.

### Saga choreography

Multi-step domain workflows ("sagas") compose through chained continuation messages, not a central orchestrator. Each step is a consumer that:

1. Re-fetches the entity.
2. Performs its single domain transition.
3. Writes its idempotency record + entity update + (optionally) the next step's outbox row in one `TransactWriteItems`.

The saga's state machine is the entity's `status` field plus the chain of consumed messages. There is no "saga orchestrator" service; the entity's state plus the next message in flight is the orchestration. A failed step lands in its own DLQ; operator replay resumes from where it stopped.

This is the **choreography** posture: each step knows what comes next and emits the next message. An **orchestrator** posture (a central service that decides next steps) is not in scope. If the application's saga complexity outgrows choreography, the introduction of an orchestrator is a future ADR; for now, choreography is sufficient and operationally simpler.

### Compensation and partial failure

A handler that commits a domain transition but whose downstream effect fails has, by construction, a recoverable state: the entity is committed, the outbox row is committed, the relay will deliver the message. There is no "inconsistent" state to compensate for at the producer side.

A consumer that performs a domain transition and whose subsequent downstream effect fails has the same recovery path: it commits its entity update and its next-step outbox row in one transaction; the relay delivers the next message; if the consumer crashed after the commit but before the message was visible to the queue, the next consumer's dedup record absorbs any redelivery.

This means **the application does not introduce explicit compensation logic for queue-driven sagas**. The combination of atomic dual-write (entity + outbox), idempotency at every consumer, and DLQ with operator replay is the recovery model.

Side-effects that *cannot* be deferred to the queue path — Slack `views.open` calls bound by a 3-second `trigger_id` window, OAuth-flow callbacks tied to short-lived state — are handled inline by the originating transport handler with its own error model. They do not enter the outbox.

### Lifespan integration

- **Phase 3 (registration):** Consumers register through `register_queue_consumers` hookspec. Registration is metadata only; no SQS calls.
- **Phase 4 (feature activation):** Per-feature initialization wires consumer dependencies.
- **Phase 5 (transport):** The consumer runner is started; long-poll workers begin receiving messages.
- **Phase 5 reverse (shutdown):** The runner stops accepting new messages; in-flight messages complete (bounded by visibility timeout and the lifespan's per-phase budget); the runner exits.
- **Phase 6 (background):** Independent of consumers. The optional outbox-relay fallback poller runs as a Tier-1 job here.

### Configuration

Queue settings live in `app/infrastructure/queueing/settings.py`:

- `QUEUE_BACKEND` — `"memory"` for local development and tests, `"aws"` (or another provider's identifier) for production.
- `QUEUE_ENDPOINTS` — a mapping from logical queue name to provider-specific endpoint (e.g., SQS queue URL, Service Bus queue name, Pub/Sub subscription path).
- `OUTBOX_STORE_BACKEND` — selects the durable store the outbox lives in (defaults to the same store the application's domain entities use).
- `OUTBOX_TTL_SECONDS` — outbox-marker TTL (default 7 days).
- `DEFAULT_VISIBILITY_TIMEOUT_SECONDS`, `DEFAULT_HEARTBEAT_INTERVAL_SECONDS`, `DEFAULT_MAX_DELIVERY_ATTEMPTS`, `DEFAULT_MESSAGE_RETENTION_DAYS` — overridable per consumer registration.

Provider-specific connection settings (e.g., AWS region, Service Bus connection string, Pub/Sub project id) live with the provider's implementation file in `app/infrastructure/queueing/<provider>/settings.py` per [configuration-ownership.md](configuration-ownership.md). The Protocol-level settings are vendor-neutral.

### Observability

Queue activity emits a fixed set of structured log events:

- `queue_message_sent` — producer side: `queue_name`, `feature`, `intent`, `correlation_id`, `via` (`outbox` | `direct-not-allowed`).
- `queue_message_received` — consumer side: `queue_name`, `message_id`, `receive_count`, plus the message body fields.
- `queue_message_processed` — consumer success: `queue_name`, `message_id`, `duration_seconds`.
- `queue_message_failed` — consumer raised: `queue_name`, `message_id`, `receive_count`, `error_type`, `error_message`.
- `queue_message_dlq` — consumer's `maxReceiveCount` exhausted: `queue_name`, `message_id`, `receive_count`. (Emitted by the consumer runner the last time before the message lapses to DLQ; the actual DLQ landing is also observable in CloudWatch.)
- `outbox_row_relayed` — relay success: `outbox_id`, `queue_name`.
- `outbox_row_relay_failed` — relay error: `outbox_id`, `queue_name`, `error_type`.

Records carry the standard correlation context. The redaction processor ([data-redaction-policy.md](data-redaction-policy.md)) is in effect.

### Day-0 implementation summary

The first production binding of this contract is:

- **Queue broker:** AWS SQS (FIFO for ordered-with-deduplication, Standard for unordered fan-out).
- **Outbox durable store:** AWS DynamoDB; atomic write via `TransactWriteItems`.
- **Relay primary:** DynamoDB Streams + AWS Lambda.
- **Relay fallback:** Tier-1 background poller scanning the outbox table.
- **Local/CI backend:** in-memory queue + in-memory outbox + immediate-publish relay.

Each subsequent provider binding (Azure, GCP) is added as a new implementation file under `app/infrastructure/queueing/<provider>/` plus its settings module, without changes to the Protocol, to consumer code, to producer code, or to the outbox-marker contract.

### What this record does not change

- The handler shape, the OperationResult envelope, the idempotency mechanism, the in-process event dispatcher, the lifespan ordering, the plugin model — all remain authoritative.
- The application's deployment topology (one process type running both inbound transport and consumers) is unchanged. Splitting consumers into a separate worker process type is a future ADR if it becomes warranted; today's posture is colocated.

## Consequences

**Positive:**

- A handler that needs to "finish later" can commit and exit; the work is durable across process death and naturally idempotent across redelivery.
- Saga steps compose without a central coordinator. Adding a step is one consumer, one outbox emission, one entity-status transition.
- Partial failure has a defined recovery path: the relay will deliver, the consumer will dedup, the DLQ catches the tail. Operators have a single mechanism to handle stuck messages.
- The control-plane-only message shape decouples the queue's contract from the entity's evolution. Adding fields to the entity does not require a queue-message migration.
- The in-memory backend means local development and tests do not need a cloud broker; the contract is exercised through the same Protocol.
- **Provider portability is preserved.** Feature code and consumer code never reference SQS, DynamoDB, or any other vendor SDK. A future migration to a different cloud is bounded to new implementation files under `app/infrastructure/queueing/`; no domain code changes.

**Tradeoffs accepted:**

- The outbox pattern is one extra durable-store write per message (and a relay component to operate). Acceptable: the alternative is a class of partial-failure modes the application would have to compensate for explicitly.
- Saga choreography means the saga's "shape" is not surveyable in one place; it is distributed across the consumers that participate. Acceptable for the current saga complexity; an orchestrator is the lever to pull when this stops being acceptable.
- A consumer's `PERMANENT_ERROR` policy (acknowledge vs lapse to DLQ) is per-consumer documented, not applied globally. Acceptable: the right choice depends on whether replay-after-amend is meaningful for the work, which is feature-specific.
- Some provider-specific affordances (SQS's 5-minute broker dedup window) are not available across all providers. Acceptable: the application's *durable* dedup guarantee comes from the consumer-side dedup table, not from the broker; broker dedup is a performance optimization where present, not a contract guarantee.

**Risks and mitigations:**

- **The relay is unavailable** (CDC delivery misconfigured, IAM problem). Outbox markers accumulate; messages are not delivered. *Mitigation:* the Tier-1 fallback poller forwards markers older than a threshold; an alarm fires on outbox markers older than a higher threshold (e.g., `created_at` more than 1 hour old).
- **A consumer's body has a non-idempotent side-effect.** Redelivery duplicates the side-effect. *Mitigation:* the dedup mechanism is mandatory for consumers as it is for handlers; review enforces.
- **A saga has a step that needs an action no consumer can perform** (e.g., "approve" requires a human). The saga stalls between steps. *Mitigation:* the entity's status reflects the stall; the missing action is reactivated by an inbound interaction (HTTP, Slack), which writes the next outbox row. Sagas are not all-machine; human-in-the-loop is a normal step.
- **The DLQ accumulates faster than operators can replay.** Operations becomes a bottleneck. *Mitigation:* alarms fire on DLQ depth; root-cause analysis determines whether the upstream is the issue, the consumer is the issue, or a code change is needed; the queue is not a workaround for fundamentally broken consumers.
- **A consumer's visibility-lease heartbeat fails.** Another task receives the message and runs the work in parallel. *Mitigation:* the dedup mechanism on the consumer body absorbs this; the second runner finds the dedup record from the first and skips. The heartbeat is an optimization, not a correctness mechanism.
- **A second provider implementation diverges from the Protocol contract** in a subtle way (e.g., GCP Pub/Sub's lack of broker-side dedup is not handled correctly). *Mitigation:* the Protocol's contract tests are run against every provider implementation; a provider that fails a contract test is not a valid backend.

## Confirmation

Compliance is verified by:

- **Code review.** No vendor-SDK calls outside `app/infrastructure/queueing/<provider>/` and the relay. No consumer registers via a non-hookspec path. No message body carries a domain payload beyond `(feature, intent, correlation_id)`. Feature code consumes only the Protocol; vendor types do not appear in feature signatures.
- **Static analysis.** A check forbids direct vendor-SDK imports (`boto3.client("sqs")`, equivalent for other providers) outside the per-provider implementation files in the queueing infrastructure.
- **Tests.** A producer-side test asserts that an entity write whose outbox put is rejected (e.g., transaction conflict) does not result in any queue message. A consumer-side test asserts that a duplicate delivery returns the cached outcome from the dedup mechanism. A relay test asserts an outbox row is forwarded once and the row is removed (or marked sent) idempotently.
- **Operational checks.** Dashboards visualize DLQ depths, outbox-row age, consumer process rate, `queue_message_failed` rate. Alarms fire on DLQ depth > 0 and on outbox-row-age past threshold.

## Source References

1. The Twelve-Factor App — Backing Services (Factor IV)
   - URL: <https://12factor.net/backing-services>
   - Accessed: 2026-04-29
   - Relevance: Establishes that an application treats backing services (queues, databases) as attached resources accessed via configuration, swappable without code changes. Grounds the rule that the queue backend is selected by configuration and that features depend on a Protocol, not on any vendor SDK.

2. Microsoft Learn — Transactional Outbox Pattern
   - URL: <https://learn.microsoft.com/en-us/azure/architecture/databases/guide/transactional-outbox-cosmos>
   - Accessed: 2026-05-08
   - Relevance: Establishes the transactional-outbox pattern as the canonical solution to the "publish-after-commit" problem in distributed systems. Names the relay's responsibilities and the at-least-once delivery property the pattern provides — properties this record adopts as the Protocol contract independent of the underlying store.

3. Chris Richardson — Microservices Patterns: Saga Pattern
   - URL: <https://microservices.io/patterns/data/saga.html>
   - Accessed: 2026-05-08
   - Relevance: Distinguishes choreography (each step emits the next event) from orchestration (a central coordinator drives the steps). Grounds the choice of choreography for this application's current saga complexity.

4. AWS Builders' Library — Avoiding Insurmountable Queue Backlogs
   - URL: <https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/>
   - Accessed: 2026-05-08
   - Relevance: Argues for control-plane message shapes, consumer-side state re-fetch, and dead-letter queues as operational safety nets rather than primary recovery channels. Grounds the message-shape rule, the consumer re-fetch rule, and the DLQ posture.

5. AWS SQS — Developer Guide (day-0 implementation)
   - URL: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html>
   - Accessed: 2026-05-08
   - Relevance: Documents Standard vs FIFO queue semantics, at-least-once delivery, the `RedrivePolicy` mechanism, `maxReceiveCount`, and message-retention configuration. The day-0 production binding for the queue-broker capability described in this record.

6. AWS SQS — Using FIFO Queues (day-0 implementation)
   - URL: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues.html>
   - Accessed: 2026-05-08
   - Relevance: Documents `MessageGroupId` (per-group ordering, parallelism across groups) and `MessageDeduplicationId` (5-minute broker-side dedup window). Maps to the Protocol's `group_key` and `dedup_id` for the AWS-backed implementation.

7. AWS DynamoDB — `TransactWriteItems` (day-0 implementation)
   - URL: <https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the all-or-nothing transactional write API. The day-0 implementation of the outbox's atomic-write contract; equivalent primitives exist on Cosmos DB transactional batches, Firestore transactions, and SQL transactions on relational stores.

8. AWS DynamoDB Streams — Use Cases (day-0 implementation)
   - URL: <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html>
   - Accessed: 2026-05-08
   - Relevance: Documents Streams as a 24-hour, ordered, exactly-once-per-stream-record event source for DynamoDB changes, with Lambda as the canonical consumer. The day-0 implementation of the relay's "read pending markers" path.

9. Azure — Service Bus Queues, Topics, and Subscriptions
   - URL: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-queues-topics-subscriptions>
   - Accessed: 2026-05-08
   - Relevance: Documents Azure's broker-equivalent capabilities (sessions for ordering, duplicate detection windows, dead-letter sub-queues, lock-renewal lease semantics). Establishes that the Protocol's contract maps cleanly onto a non-AWS provider when needed.

10. Google Cloud — Pub/Sub Ordering and Exactly-Once Delivery
    - URL: <https://cloud.google.com/pubsub/docs/ordering>
    - Accessed: 2026-05-08
    - Relevance: Documents Pub/Sub's `ordering_key` and the absence of broker-side deduplication. Establishes the constraint that on this provider, durable dedup must come from the consumer-side idempotency table — which is already the application's contract regardless of broker.

11. AWS DynamoDB — Time To Live (TTL) (day-0 implementation)
    - URL: <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html>
    - Accessed: 2026-05-08
    - Relevance: Documents item-level TTL on DynamoDB items, used by the outbox-marker lifecycle to bound table growth without an explicit cleanup job. Equivalent TTL mechanisms exist on Cosmos DB and Firestore.

## Change Log

- 2026-05-08: Created. Establishes a capability-shaped, vendor-portable Protocol for cross-process at-least-once delivery with two queue kinds (ordered-with-deduplication and unordered fan-out), a transactional-outbox pattern for atomicity between entity write and message send (entity + idempotency record + outbox marker written atomically against the durable store), a relay that reads outbox markers and publishes them to the queue, control-plane-only message shape (`feature`, `intent`, `correlation_id`) with consumers re-fetching authoritative state from the durable store, application-owned ordering and dedup keys (`group_key = correlation_id`, `dedup_id = idempotency_key`), consumer registration via `register_queue_consumers` hookspec at lifespan phase 4, consumer execution at phase 5, visibility-lease heartbeat at half the timeout, `max_delivery_attempts = 3` to DLQ, 14-day DLQ retention, alarming on DLQ depth, no automated replay, and saga choreography (each consumer emits the next outbox marker). Names AWS SQS + DynamoDB + DynamoDB Streams as the day-0 production implementation, with explicit substitutability for Azure Service Bus + Cosmos DB, GCP Pub/Sub + Firestore, and an in-memory backend for local development and CI. Locates the queue infrastructure at `app/infrastructure/queueing/` with one Protocol and per-provider implementation files. Compensation is implicit in the atomic-commit-plus-relay-plus-idempotent-consumer composition; no explicit compensation actions are introduced. Defers in-process events to event-dispatch.md, scheduled work to background-execution.md, inbound retry/idempotency to handler-idempotency.md, and centralized workflow orchestration to a future record.

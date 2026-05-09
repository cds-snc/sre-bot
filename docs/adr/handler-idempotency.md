---
title: "Handler Idempotency"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture, data]
constrained_by: [feature-handler-standard.md, operation-result-pattern.md, cross-channel-correlation.md, api-design-error-mapping.md, background-execution.md, message-queuing.md, infrastructure-service-classification.md, logging-observability.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Handler Idempotency

## Context and Problem Statement

The application handles work that arrives more than once for the same intent: a Slack interaction may be redelivered when an acknowledgement is slow, an SQS message is received at-least-once, an HTTP webhook is retried by an upstream sender on a perceived timeout, a background job is started independently on N processes when its singleton lock has lapsed, an operator hits "submit" twice on a form. Each of these is a real and routine operational condition; none of them is an error path.

The problem this record addresses: **when must a handler produce the same end state for repeated invocations of the same intent, what is the dedup mechanism, and what does the second invocation return?** The answer determines:

1. Whether duplicate inbound messages produce duplicate side-effects (notifications sent twice, accounts provisioned twice, transitions applied twice) or are absorbed at the boundary.
2. Whether the application's response to a retry is *indistinguishable* from its response to the first attempt — the contract that lets clients and queues retry safely without coordination.
3. Whether a handler that crashes mid-flight leaves the system in a state from which a re-attempt produces a coherent end state.
4. Whether the boundary between "re-runs are safe by design" (request-shaped operations against natural-key resources) and "re-runs require explicit dedup" (anything that mutates external state) is documented and enforceable.

**Constraints:**

- Handlers run on multiple identical processes ([cloud-portability.md](cloud-portability.md): `desired_count >= 2`); two processes may receive the same inbound message simultaneously and process it independently.
- Inbound transports redeliver. Slack Socket Mode is at-least-once across multiple WebSocket connections; SQS standard and FIFO queues guarantee at-least-once; upstream HTTP senders retry on perceived timeout. None of these is configurable away.
- Service-layer outcomes are returned as the closed five-status envelope ([operation-result-pattern.md](operation-result-pattern.md)). The dedup contract must compose with that envelope, not invent a parallel result type.
- Correlation IDs are minted at interaction creation and propagated through every transport ([cross-channel-correlation.md](cross-channel-correlation.md)). The same correlation ID names the same intent across retries.
- Composed infrastructure services are vendor-portable in shape ([infrastructure-service-classification.md](infrastructure-service-classification.md): Path A; [cloud-portability.md](cloud-portability.md)). The dedup utility is exposed to handlers as a Protocol that names the *capability* (atomic write of a dedup record alongside a domain entity), not a vendor's API. AWS DynamoDB is the day-0 implementation of the durable store; the architecture must support swappable providers (Azure Cosmos DB, GCP Firestore, PostgreSQL, in-process for local/CI) without handler-code changes.
- The dedup mechanism composes with the durable store the application's domain entities live in, rather than introducing a parallel coordination service.
- The handler shape is fixed ([feature-handler-standard.md](feature-handler-standard.md)): five steps, ~30 lines, OperationResult at the boundary. Idempotency is a property of the steps, not a new step.

**Non-goals:**

- This record does not cover compensation, rollback, sagas, or two-phase commit across services. A partially-applied handler that crashes mid-flight has its end-state guaranteed by atomicity at the data store, not by transactional choreography. Cross-step compensation is deferred.
- This record does not pick the retry policy (max attempts, backoff, jitter) for outbound calls. Idempotency is the property that makes retries safe; the retry policy is a separate concern.
- This record does not catalogue the application's actual handler intents. The intent name is part of each handler's contract; the registry is observable from the handler code, not from this document.
- This record does not redefine the OperationResult envelope ([operation-result-pattern.md](operation-result-pattern.md)) or the HTTP problem-details mapping ([api-design-error-mapping.md](api-design-error-mapping.md)). Cached outcomes flow through the existing channels.

## Considered Options

**Option 1 — Mandatory idempotency for mutating handlers, enforced through a deterministic key derived from `(feature, intent, correlation_id)`, with first-writer-wins atomicity on the durable store via a capability-shaped Protocol.** The handler computes the key, attempts an atomic write that includes the dedup record, and on collision returns the previously-stored outcome. The key is application-derived (not client-supplied). Read-only intents are exempt. AWS DynamoDB is the day-0 implementation; the contract is provider-portable.

**Option 2 — Optional idempotency with a client-supplied `Idempotency-Key` header, RFC-style.** The producer of the inbound message generates a key per attempt; the handler stores it and dedups on collision. The application accepts whatever the client sends; absence of a key means no dedup.

**Option 3 — Lock-based exclusive execution with no dedup record.** A handler acquires a lock keyed by `(feature, intent, correlation_id)`, executes, then releases. A second invocation finds the lock held and waits, retries, or rejects.

**Option 4 — In-memory dedup (per-process LRU cache).** The handler's recent (key → outcome) pairs are cached in memory. A second invocation on the same process returns the cached outcome.

## Decision Outcome

**Chosen: Option 1 — mandatory idempotency for mutating handlers, enforced through a deterministic application-derived key with first-writer-wins atomicity on the durable store. AWS DynamoDB is the day-0 implementation; the contract is provider-portable.**

This is the only option that closes the four operationally-real retry paths (transport redelivery, queue at-least-once, multi-process race, operator double-submit) under one mechanism without introducing new failure modes, and does so behind a Protocol that does not bind the application to AWS at the *handler-code* level. Client-supplied keys (Option 2) push the contract to senders the application does not control (Slack does not provide one; queue redrives do not regenerate one). Lock-based exclusion (Option 3) is a coordination primitive — useful for *concurrency* but not for *result reproduction*; a second invocation after the first completed must return the same outcome, which a lock alone cannot deliver. In-memory dedup (Option 4) does not survive process restart and does not work across `desired_count >= 2`.

### When idempotency applies

Every handler that **mutates state** is in scope:

- HTTP request handlers whose service call effects a domain transition (creates, approves, rejects, opens, closes, provisions, retires).
- Platform-transport handlers (Slack interactivity, Teams Adaptive Card actions) whose service call effects a domain transition.
- SQS message consumers — every consumer is mutating by design (queue work is the asynchronous tail of a request).
- Tier-2 background jobs ([background-execution.md](background-execution.md)) whose body effects domain transitions.

The following are **out of scope** (the dedup mechanism is not invoked):

- Read-only HTTP handlers (`GET /resource/{id}`, `GET /resources?filter=…`). Repeated reads are safe by definition.
- Health and readiness endpoints.
- Tier-1 background jobs ([background-execution.md](background-execution.md)). Tier-1's contract is design-time idempotency through naturally-idempotent operations (conditional writes, upserts, log-only). The dedup mechanism is unnecessary; mandating it would be ceremony without benefit.
- In-process event subscribers ([event-dispatch.md](event-dispatch.md)). The producer's idempotency at the boundary is sufficient; an event delivered twice in-process happens because the producer fired twice, which is itself an upstream dedup miss.

A handler that does *not* mutate but ends up wanting an idempotent response (for caching, for stable error responses) is not the dedup mechanism's customer. Its caching is its own concern.

### The idempotency key

The key is a string of the form:

```text
<feature>:<intent>:<correlation_id>
```

- `<feature>` is the feature package name (`incident`, `access`, `aws`, …) — the namespace owning the handler.
- `<intent>` is the domain command name the handler implements (`open_ticket`, `approve_request`, `provision_account`). One intent per handler. The string is part of the handler's contract; it does not change without a contract review.
- `<correlation_id>` is the per-interaction UUID v4 minted at the user-facing interaction's creation and propagated through every transport per [cross-channel-correlation.md](cross-channel-correlation.md). Two retries of the same intent for the same interaction carry the same UUID.

Properties this key has, by construction:

- **Deterministic.** The same intent on the same correlation ID produces the same key on every attempt. No timestamps, no per-attempt randomness, no client headers.
- **Cross-task stable.** Two processes computing the key for the same inbound message get the same string.
- **Cross-transport stable.** A retry through a different inbound transport (e.g., SQS replay of a previously HTTP-received intent) computes the same key.
- **Greppable.** The key fragments are unambiguous in logs and dedup-table scans.

The mechanism does **not** use:

- Client-supplied `Idempotency-Key` headers. Slack does not provide them; SQS does not regenerate them across redrives; HTTP senders we don't control don't send them.
- Per-delivery identifiers (Slack `envelope_id`, SQS `MessageId`, HTTP request ID). These differ across retries of the same intent.
- Hashes of the inbound payload. Payload variance across redeliveries (timestamps, signatures, sequence numbers in framing) defeats determinism.

### The dedup mechanism — atomic dual-write

The handler's mutation step performs **one** transactional write against the durable store that includes both the domain entity update and the idempotency record. The contract:

- **Atomic.** Both writes succeed together or neither does. No phantom dedup record (a key without an entity) and no phantom entity (an entity without a dedup record).
- **First-writer-wins.** A second attempt encounters a not-already-present condition that fails, and the entire transaction is cancelled. The application observes "the dedup record exists" as the trigger to read and return the cached outcome rather than re-execute the domain transition.
- **API-level deduplication on the transaction itself.** Where the durable store provides a transaction-deduplication token (a request token that absorbs duplicate attempts within a bounded window), the application sets it to a deterministic value derived from the idempotency key. A retry of the same transaction call within the window is a no-op success rather than a second attempt.

Outcomes that did **not** complete a domain transition (validation failures, authorization denials, vendor failures *before* the entity write) do **not** write a dedup record. The contract is "the dedup record is the receipt that the transition committed." A retry of an intent that previously failed validation is a fresh attempt; whether the second attempt also fails is a property of the validation, not of dedup.

#### Day-0 implementation: AWS DynamoDB

The day-0 backend is DynamoDB `TransactWriteItems` with a conditional `Put` on the idempotency item:

```python
dynamodb.transact_write_items(
    TransactItems=[
        {"Put": {  # idempotency record (condition: not already present)
            "TableName": IDEMPOTENCY_TABLE,
            "Item": {
                "key": idempotency_key,
                "result_status": "SUCCESS",          # OperationResult.status string
                "result_payload": serialized_payload, # JSON, redacted per data-redaction-policy.md
                "ttl": now_epoch + IDEMPOTENCY_TTL_SECONDS,
            },
            "ConditionExpression": "attribute_not_exists(#key)",
            "ExpressionAttributeNames": {"#key": "key"},
        }},
        {"Put": {  # domain entity write
            "TableName": ENTITY_TABLE,
            "Item": entity_item,
            "ConditionExpression": <feature-defined>,
        }},
    ],
    ClientRequestToken=idempotency_key_uuid_form,
)
```

Mapped to DynamoDB primitives:

- **Atomic** maps to `TransactWriteItems`'s all-or-nothing semantics across up to 100 items.
- **First-writer-wins** maps to `attribute_not_exists` on the idempotency item; the failure surfaces as `TransactionCanceledException` carrying `ConditionalCheckFailed` against the dedup-record put.
- **API-level deduplication** maps to `ClientRequestToken` (a UUID derived from the idempotency key, since DynamoDB requires the token in UUID shape); the 10-minute API-level window is a DynamoDB-specific affordance that absorbs lower-level retry storms.

#### Provider mappings (substitutable behind the Protocol)

- **Azure Cosmos DB:** transactional batch writes scoped to a partition key; the entity, idempotency record, and any related items share a partition key. The "not already present" condition is enforced via `pre-trigger` or stored procedure, or via `If-None-Match: *` on a `create` operation.
- **GCP Firestore:** a single transaction containing the writes; the "not already present" condition is enforced by reading the document under the transaction and aborting if it exists.
- **PostgreSQL (or other relational stores):** the entity, idempotency record, and any related rows share a single SQL transaction; "not already present" is enforced by a `UNIQUE` constraint on the idempotency key with `ON CONFLICT DO NOTHING RETURNING ...` to detect collision.
- **In-memory (local dev and CI):** a process-local dict keyed by the idempotency key, protected by a `threading.Lock`. Sufficient for the local-development single-process posture per [environment-parity.md](environment-parity.md).

The Protocol's contract tests (atomic dual-write, first-writer-wins under simulated contention, cached outcome on collision indistinguishable from first-attempt response) run against every provider implementation. A provider that fails a contract test is not a valid backend.

### Storing the outcome — what the second attempt returns

When the transaction is cancelled on a dedup collision, the handler reads the existing dedup record and returns its stored outcome. The contract:

- The stored `result_status` and `result_payload` are returned **as if** the handler had just produced them. The HTTP response (or transport response) is **indistinguishable** from the first attempt's response.
- The stored status is `SUCCESS`. The dedup record is only written on commit, so the only outcome it represents is success. A retry of an intent that previously failed validation does not encounter the dedup mechanism; it re-runs validation.
- The stored payload is the original write-time value, not a current re-fetch. A retry that arrives after the entity has subsequently been mutated by another path returns the *original* outcome, not the current state. A handler whose contract is "return current state on retry" is not a fit for this mechanism — but no domain handler in this application has that contract.

This is the property AWS's Builders' Library names: *"Clients cannot tell the difference between a request that was completed the first time, and one where the server processed the duplicate."*

### TTL and the dedup window

The dedup record carries a TTL of **24 hours** (configurable per table; this is the default). The window is calibrated to cover:

- Slack's interactive-component retry window (minutes to low single-digit hours).
- SQS standard queue's redrive cycles (`maxReceiveCount` × visibility timeout).
- Upstream HTTP senders' idempotent-retry expectations (typically minutes; outliers in hours).
- Operator-driven manual replays within the same workday.

After the window, the dedup record expires; a re-attempt with the same key is treated as a fresh attempt. This is acceptable because the operational scenarios that would replay an intent more than 24 hours later are rare and require deliberate operator intervention; if they need dedup, the operator runs the replay through a path that re-establishes the dedup record.

### Composition with OperationResult

The cached outcome is a *materialized* `OperationResult.SUCCESS`:

- The handler reads the dedup record, constructs `OperationResult.success(value=deserialized_payload)`, and returns it from the boundary as if it had just been produced by the service layer.
- The transport layer (HTTP problem-details mapper [api-design-error-mapping.md](api-design-error-mapping.md), Slack ack composer, etc.) sees the same envelope it sees on first-attempt success. The response body, status code, and observability records are identical.
- The handler's service-call step (step 3 of the standard handler shape) is *replaced* by the cache read on a dedup collision; the envelope-handling steps (4 and 5) are the same.

### Composition with the cross-process queue

Inbound and outbound queue messages compose with the dedup mechanism. The capability-shaped contract is named in [message-queuing.md](message-queuing.md); the points relevant here:

- **`group_key` is the correlation_id.** The queue's ordering-with-deduplication kind preserves intent ordering for one interaction across the consumer.
- **`dedup_id` is the idempotency key.** Where the queue's day-0 implementation provides a broker-side dedup window (AWS SQS FIFO: 5 minutes), it absorbs duplicate sends within that window; the durable application-level guarantee beyond that window comes from the dedup record described above.
- **Queue payload** carries `(feature, intent, correlation_id)` only. Domain state is re-fetched from the durable store by the consumer; the queue is a control-plane signal, not a state carrier. This is what makes consumer-side replays safe.
- **Send order** is "after entity write." A producer sends the queue message *only* after the atomic dual-write has succeeded. If the entity write fails, no message is sent. The transactional-outbox pattern ([message-queuing.md](message-queuing.md)) is the mechanism that makes this atomic.
- **Consumer DLQ.** A consumer that exhausts retries for a message (due to a permanent error in its processing chain, not a transient one) lands the message in the dead-letter queue. The dedup record is unaffected; the entity remains in its previous state. Operator intervention is required for replay.

### Where the dedup utility lives

The dedup mechanism is a **shared infrastructure capability** ([infrastructure-service-classification.md](infrastructure-service-classification.md): Path A, Shared). One Protocol exported to consumers, one DI-injected handle, one or more provider-specific implementations selected by configuration.

```text
app/infrastructure/idempotency/
    __init__.py          # public surface: IdempotencyStore Protocol, IdempotencyKey value type
    in_memory.py         # in-process backend for local dev and CI
    aws.py               # AWS DynamoDB-backed implementation (day-0 production)
    # cosmos.py, firestore.py, postgres.py … future provider implementations live here
    settings.py          # backend selector, TTL defaults, table/key-prefix
```

Handlers do not implement their own dedup. They call `idempotency_store.run_or_replay(key, mutate)` (or compose at the data-store level when the entity write is what carries the dedup item — both shapes are supported by the utility). The store handles serialization, redaction (per [data-redaction-policy.md](data-redaction-policy.md)), TTL math, and the provider-specific translation of "first-writer-wins condition failed" to "return cached outcome." The implementation seam is the only place provider-specific exception types are caught.

### Slack-specific notes

The application's Slack transport ([transport-slack.md](transport-slack.md)) defaults to Socket Mode. Socket Mode does *not* expose `X-Slack-Retry-Num` headers (those are an HTTP-Events-API concern). However, the multi-connection race (two WebSocket connections receiving the same event simultaneously) is a real and documented Slack behaviour. The dedup mechanism above closes that race by computing the same key on both processes; the second atomic write fails on the not-already-present condition and the duplicate is absorbed.

If a future configuration switches a Slack inbound to HTTP Events API, the same mechanism continues to work; `X-Slack-Retry-Num` becomes a useful telemetry signal but is not load-bearing in the dedup decision.

### Observability contract

Idempotency handling emits a fixed set of structured log events:

- `idempotency_check_passed` — first attempt; transaction committed; dedup record written.
- `idempotency_collision` — duplicate detected; cached outcome returned. Includes `key`, `original_attempt_age_seconds` (from the stored timestamp), `subscriber_count_for_event` if applicable.
- `idempotency_record_expired` — a record fetched during a near-miss diagnostic was past TTL (informational; does not affect handling).

Metrics derived from these events are owned by [logging-observability.md](logging-observability.md).

## Consequences

**Positive:**

- Retries from any inbound transport are safe by construction. Slack redeliveries, queue at-least-once, HTTP retries, and operator double-submits all converge on the same dedup record.
- The response on retry is observably identical to the response on first attempt. Clients and queues need no special-case logic; "200 OK with the same body" is sufficient.
- The mechanism uses one durable store (the same store the application's domain entities live in) and one transactional primitive (atomic multi-key write). No additional service to operate.
- Handler authors do not invent dedup; they call one infrastructure utility. The contract is reviewed once and reused everywhere.
- Tier-1 background jobs are not burdened with dedup ceremony; the contract is "design-time idempotency" and that is enough for them.
- **Provider portability is preserved.** Handler code and feature code never reference DynamoDB, SQS, or any other vendor SDK. A future migration to a different durable store is bounded to new implementation files under `app/infrastructure/idempotency/`; no domain code changes.

**Tradeoffs accepted:**

- Storing a dedup record per mutating intent is an extra durable-store write item per mutating handler invocation. Acceptable: an atomic two-item write costs roughly twice the resource of a single write, and that cost is bounded.
- The 24-hour window is a fixed value rather than a per-intent tunable. Acceptable: per-intent windows would multiply configuration; the window is generous and operationally justified.
- Cached outcomes return the original write-time value, not a current re-fetch. Acceptable: domain handlers in this application do not have a "return current state on retry" contract; the mechanism is right-sized to the actual contract.
- A retry that arrives after TTL expiry is treated as a fresh attempt. Acceptable: 24-hour replays are rare and signal operator intent.
- Some provider-specific affordances (DynamoDB's 10-minute `ClientRequestToken` API window) are not available across all providers. Acceptable: the application's *durable* dedup guarantee comes from the dedup record, not from any API-level token; the transaction-token affordance is a performance optimization where present, not a contract guarantee.

**Risks and mitigations:**

- **A handler computes the wrong key (typo in feature/intent string, missing correlation_id).** Two retries are not deduplicated. *Mitigation:* the key components are constants in the handler module, validated at registration; correlation_id is acquired through the standard contextvar, not re-derived. Code review enforces.
- **A long-running handler crashes after the entity write but before the response is composed.** The dedup record has been written; the next retry returns a cached SUCCESS but the original response was never sent. The end-state is consistent (the entity was written) but the requester may have no acknowledgement. *Mitigation:* request-shaped acks are produced inside the same transaction's response cycle; for queue-driven asynchronous notifications, the ack is a separate message that is itself idempotent.
- **A handler stores a payload that contains sensitive content not yet redacted.** The dedup record carries it for 24 hours. *Mitigation:* the store applies the redaction processor [data-redaction-policy.md](data-redaction-policy.md) before serialization; payload schemas are reviewed when intents are added.
- **The day-0 provider's API constraints intrude on the application's key shape.** DynamoDB's `ClientRequestToken` requires UUID v4 form; the application's key uses `:` separators. *Mitigation:* the AWS implementation derives a UUIDv5 over a fixed namespace from the application key for the token; handler authors do not see this. The Protocol's contract names the application key form; provider conversions are implementation-internal.
- **A queue consumer fails repeatedly, exhausting retries on a transient downstream failure.** The message lands in the DLQ; the entity is in its previous state; the dedup record is unchanged. *Mitigation:* DLQ alarming fires; operator-driven replay regenerates the queue message and the dedup mechanism handles the next attempt normally.
- **A second provider implementation diverges from the Protocol contract** in a subtle way (e.g., a relational backend's `ON CONFLICT DO NOTHING` does not match the dedup-record-write semantics if the entity write is in the same transaction but the conflict only fires on the dedup row). *Mitigation:* the Protocol's contract tests are run against every provider implementation; a provider that fails a contract test is not a valid backend.

## Confirmation

Compliance is verified by:

- **Code review.** Every mutating handler invokes the idempotency store. No handler maintains a parallel local-cache dedup. No handler computes the key from per-delivery identifiers (envelope_id, MessageId). Handler code consumes only the Protocol; vendor types do not appear in handler signatures.
- **Static analysis.** A check forbids vendor-SDK imports (`boto3.client("dynamodb")` and equivalents for other providers) outside `app/infrastructure/idempotency/<provider>.py`. A check confirms that any atomic-write path through the durable store touching domain entities also includes the dedup item (or invokes the store utility).
- **Tests.** Unit tests assert: same key produces a cached outcome on second invocation; different keys for the same intent are treated as distinct; the cached outcome is identical to the original response. Integration tests assert that two simulated concurrent invocations of the same handler produce one entity write and one notification. A test asserts that a handler crashing between entity write and response on the *first* attempt does not inhibit the dedup mechanism on the *second* attempt.
- **Operational dashboards.** `idempotency_collision` count per intent — a non-zero rate is normal (it is the dedup mechanism working); a sudden change is a signal of upstream behaviour change.

## Source References

1. AWS Builders' Library — Making Retries Safe with Idempotent APIs
   - URL: <https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-apis/>
   - Accessed: 2026-05-08
   - Relevance: Establishes the principle that "clients cannot tell the difference between a request that was completed the first time, and one where the server processed the duplicate," and the requirement that "the process that combines recording the idempotent token and all mutating operations related to servicing the request must meet the properties for an ACID operation." Grounds the atomic dual-write rule and the indistinguishable-response contract — properties this record adopts as the Protocol contract independent of the underlying store.

2. The Twelve-Factor App — Disposability (Factor IX)
   - URL: <https://12factor.net/disposability>
   - Accessed: 2026-04-29
   - Relevance: "Processes should be robust against sudden death, in the case of a failure in the underlying hardware. […] All jobs are reentrant, which typically is achieved by wrapping the results in a transaction, or making the operation idempotent." Grounds the rule that idempotency is a first-class property of mutating handlers, not a patch.

3. RFC 9110 — HTTP Semantics, §9.2.2 "Idempotent Methods"
   - URL: <https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2>
   - Accessed: 2026-05-08
   - Relevance: Defines the HTTP semantics of idempotent methods: "the intended effect on the server of multiple identical requests with that method is the same as the effect for a single such request." Grounds the contract that a `POST` handler implementing a mutating intent in this application offers the same property at the application layer that RFC 9110 names at the HTTP layer for `PUT` and `DELETE`.

4. AWS Builders' Library — Avoiding Insurmountable Queue Backlogs
   - URL: <https://aws.amazon.com/builders-library/avoiding-insurmountable-queue-backlogs/>
   - Accessed: 2026-05-08
   - Relevance: Establishes the discipline that queue messages should be control-plane signals, that consumers should be re-runnable, and that dead-letter queues are an operational safety net rather than a primary recovery channel. Grounds the rules around `group_key`, `dedup_id`, queue-payload shape, and DLQ ownership.

5. AWS DynamoDB — `TransactWriteItems` (day-0 implementation)
   - URL: <https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the transactional write API: up to 100 items, all-or-nothing atomicity, `ClientRequestToken` for 10-minute API-level idempotency, and `TransactionCanceledException` carrying per-item cancellation reasons. The day-0 implementation of the dedup-record-plus-entity-item atomic-write contract.

6. AWS DynamoDB — Time To Live (TTL) (day-0 implementation)
   - URL: <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the item-level TTL attribute as numeric epoch seconds with eventual deletion by the service. The day-0 implementation of the 24-hour dedup-record TTL; equivalent TTL mechanisms exist on Cosmos DB and Firestore.

7. AWS SQS — Exactly-Once Processing in FIFO Queues (day-0 implementation)
   - URL: <https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-exactly-once-processing.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the 5-minute `MessageDeduplicationId` window in SQS FIFO queues. Grounds the day-0 broker-side dedup affordance; the durable application-level dedup contract is provided by the dedup record regardless of broker.

8. Microsoft Learn — Azure Cosmos DB Transactional Batch Operations
   - URL: <https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/transactional-batch>
   - Accessed: 2026-05-08
   - Relevance: Documents Cosmos DB's transactional batch writes scoped to a partition key. Establishes that the Protocol's atomic-dual-write contract maps cleanly onto a non-AWS provider when needed.

9. Google Cloud — Firestore Transactions
   - URL: <https://cloud.google.com/firestore/docs/manage-data/transactions>
   - Accessed: 2026-05-08
   - Relevance: Documents Firestore's read-modify-write transactions used to enforce "not already present" conditions atomically. Validates the alternate-provider mapping for the dedup contract.

10. PostgreSQL — `INSERT ... ON CONFLICT` (UPSERT)
    - URL: <https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT>
    - Accessed: 2026-05-08
    - Relevance: Documents the conditional-insert primitive used by a relational-backed dedup-store implementation; combined with a `UNIQUE` constraint on the idempotency key and `ON CONFLICT DO NOTHING RETURNING ...`, it provides the "first-writer-wins" semantics the Protocol requires.

## Change Log

- 2026-05-08: Created. Establishes mandatory idempotency for handlers that mutate state (HTTP, platform-transport, queue consumers, Tier-2 background jobs) through a capability-shaped, vendor-portable Protocol. Defines a deterministic application-derived key of the form `<feature>:<intent>:<correlation_id>` — no client-supplied headers, no per-delivery identifiers, no payload hashes. Specifies first-writer-wins enforcement through an atomic dual-write against the durable store carrying both the domain entity write and the dedup record. Sets the dedup-record TTL at 24 hours and specifies that the cached outcome on collision is the original write-time `OperationResult.SUCCESS`, returned indistinguishably from the first attempt. Names AWS DynamoDB `TransactWriteItems` (with `ClientRequestToken` derived from the key for the 10-minute API-level dedup window) as the day-0 implementation, with explicit substitutability for Azure Cosmos DB transactional batches, GCP Firestore transactions, PostgreSQL `INSERT ... ON CONFLICT` with a `UNIQUE` constraint, and an in-memory backend for local development and CI. Composes with the queue's application-owned `group_key = correlation_id` and `dedup_id = idempotency_key` for outbound messages. Locates the dedup utility as a shared infrastructure capability in `app/infrastructure/idempotency/` with one Protocol and per-provider implementation files. Defers compensation, retry policy, and saga choreography to other records.

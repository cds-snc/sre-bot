---
adr_id: ADR-0091
title: "Handler Reliability and Idempotency Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
governance_domain: application
primary_domain: Data and Persistence
secondary_domains:
  - Transport and API
  - Runtime and Lifecycle
owners:
  - SRE Team
date_created: 2026-05-06
last_updated: 2026-05-07
last_reviewed: 2026-05-07
next_review_due: 2026-09-03
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0050
  - ADR-0058
  - ADR-0077
  - ADR-0079
  - ADR-0083
  - ADR-0089
impacts:
  - ADR-0050
  - ADR-0058
  - ADR-0063
  - ADR-0079
  - ADR-0083
  - ADR-0089
  - ADR-0090
  - ADR-0096
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0044
  - ADR-0045
  - ADR-0049
  - ADR-0054
  - ADR-0057
  - ADR-0062
  - ADR-0064
  - ADR-0065
  - ADR-0079
  - ADR-0083
  - ADR-0085
  - ADR-0086
  - ADR-0087
  - ADR-0088
  - ADR-0090
related_packages:
  - app/infrastructure/idempotency
  - app/infrastructure/queue
  - app/infrastructure/dynamodb
  - app/packages/access/interactions
---

# Handler Reliability and Idempotency Standard

## Context

- **Problem statement:** Platform event handlers in this application receive events from Slack,
  Teams, and HTTP. Each of these channels can re-deliver the same event:

  - **HTTP:** ALB and API client retries on transient failures (network timeout, 5xx).
  - **Slack Socket Mode:** up to 10 concurrent connections; Slack delivers the same event to
    all connected process instances simultaneously. This is documented Slack behavior, not a
    bug.
  - **Slack HTTP mode:** Slack retries delivery if the application does not respond within
    3 seconds (default; configurable). The same event may arrive twice.
  - **SQS:** at-least-once delivery. SQS workers receive the same message multiple times if
    visibility timeout lapses or a worker crashes before deleting the message.

  Without a formal idempotency contract, duplicate delivery leads to:
  1. Double entity writes (e.g., two APPROVED states, two Slack notifications to approvers).
  2. Race conditions between ECS tasks processing the same event simultaneously.
  3. Phantom idempotency records that claim an operation completed before the domain entity
     was actually written (split-write failure).

  Prior implementations used loose checks (query-then-write), which are inherently racy and
  do not satisfy the "first-writer-wins with zero phantom records" requirement.

- **Business/operational drivers:**
  - ECS desired_count=2: two tasks run in parallel at all times. The same Slack event may
    be dispatched to both tasks simultaneously.
  - Slack 3-second ack window: the idempotency check cannot add unbounded latency. DynamoDB
    conditional writes are single-digit milliseconds.
  - SQS-based continuation: long-running approval workflows continue via SQS messages that
    may be re-delivered. Continuation handlers must also be idempotent.
  - Operator incident response: when a handler fails after the entity write but before SQS
    enqueue, operators must be able to understand what happened and manually replay the SQS
    message without causing data corruption.

- **Constraints:**
  - ADR-0045 Principle 6: stateless processes. No in-process idempotency cache. All
    idempotency state persists in DynamoDB.
  - ADR-0045 Principle 7: managed cloud service > library > custom code. DynamoDB
    `TransactWriteItems` is the idempotency enforcement mechanism. No custom locking
    library.
  - ADR-0050: fallible operations return `OperationResult`. Idempotency detection returns
    `SUCCESS` with the original result, not a `PERMANENT_ERROR`.
  - ADR-0058: background SQS workers run as Phase 6 lifespan processes. Their reliability
    invariants (at-least-once execution, error isolation, `safe_run`) apply here.
  - ADR-0077: `IdempotencyService` is a Category A infrastructure service, exposed via
    `Protocol` and injected via `Annotated[Protocol, Depends(...)]`.
  - ADR-0079: SQS FIFO queues for async continuation. This ADR extends ADR-0079 with the
    specific message schema, `MessageGroupId`, and `MessageDeduplicationId` requirements
    for handler continuation messages.
  - ADR-0083: blinker `EventDispatcher` provides error-isolated in-process events. Subscriber
    failures are logged but do not propagate to the publisher. This is complementary to, not
    a substitute for, DynamoDB-based idempotency.
  - ADR-0089: handlers follow the mandatory sequence (ack → read → validate → write →
    publish → return). The idempotency gate in `ingress.py` (ADR-0089 Standard 5) enforces
    this standard at the entry point.

- **Non-goals:**
  - This ADR does not define `correlation_id` cardinality or payload carrier format. Those
    are ADR-0090's scope.
  - This ADR does not define domain entity status transitions or the stateless handler
    invariant. Those are ADR-0089's scope.
  - This ADR does not define the tenacity retry policy for transient infrastructure failures.
    That is ADR-0094's scope (when authored).
  - This ADR does not govern identity-based access controls on SQS queue policies. That is
    an infrastructure concern.
  - This ADR does not define per-feature DLQ monitoring alarm thresholds. Those are
    operational decisions documented in Terraform and runbooks.

## Decision

All platform event handlers implement a **first-writer-wins, atomic-dual-write, semantically-
equivalent-response** idempotency contract. Idempotency state persists exclusively in DynamoDB.
SQS continuation messages carry only routing keys; workers re-fetch domain state on dequeue.

---

### Standard 1: Idempotency Key Schema and Window

Every mutable platform event (state-changing request) is assigned a unique idempotency key
that scopes the idempotency guarantee to the exact operation intent.

**Key schema:**

```
<feature>:<intent>:<correlation_id>

Examples:
  access:submit_request:550e8400-e29b-41d4-a716-446655440000
  access:approve:550e8400-e29b-41d4-a716-446655440000
  incident:open:7c9e6679-7425-40de-944b-e07fc1f90ae7
```

**DynamoDB record schema:**

```python
{
    "pk": "<feature>:<intent>:<correlation_id>",  # Idempotency key
    "result": "<serialized OperationResult>",      # Original success result (JSON)
    "ttl": <unix_epoch_seconds>,                   # 24-hour TTL from write time
}
```

**Rules:**

- IK1: `feature` is the package name (`access`, `incident`, `aws_ops`). `intent` is the
  domain command name (`submit_request`, `approve`, `reject`). `correlation_id` is the UUID
  v4 entity key (ADR-0090 Standard 1).
- IK2: The idempotency record TTL is set to 24 hours from the record write time. This is
  a DynamoDB item-level TTL attribute (`ttl`). Expired records are automatically deleted by
  DynamoDB.
- IK3: The 24-hour window is intentionally wider than the Slack retry window (minutes) and
  the SQS FIFO deduplication window (5 minutes). It covers manual operator replays and
  delayed retries from network partitions.
- IK4: Observe-only endpoints (`GET /feature/entities/{correlation_id}`) do not produce or
  consume idempotency records. Idempotency applies only to mutable operations.
- IK5: The idempotency key schema does not embed timestamps or request IDs. The key is
  deterministic from `feature`, `intent`, and `correlation_id`. Two requests for the same
  operation produce the same key, enabling first-writer-wins detection.

---

### Standard 2: Atomic Write Invariant

The domain entity write and the idempotency key write happen in a single atomic
`TransactWriteItems` call. This prevents phantom idempotency records — records that exist
without a corresponding domain entity (split-write failure).

**Transaction structure:**

```python
dynamodb.transact_write_items(
    TransactItems=[
        {
            "Put": {
                "TableName": ENTITY_TABLE,
                "Item": entity_item,
                "ConditionExpression": "attribute_not_exists(pk)"  # on create
                # OR no condition on status update (with optimistic lock version check)
            }
        },
        {
            "Put": {
                "TableName": IDEMPOTENCY_TABLE,
                "Item": idempotency_item,
                "ConditionExpression": "attribute_not_exists(pk)"  # first-writer-wins
            }
        },
    ],
    ClientRequestToken=str(uuid4()),  # 10-minute idempotency for the TransactWriteItems itself
)
```

**Rules:**

- AW1: The idempotency key write uses `ConditionExpression: "attribute_not_exists(pk)"`.
  If the idempotency key already exists, DynamoDB raises `TransactionCanceledException`.
  This is the first-writer-wins enforcement.
- AW2: On `TransactionCanceledException` with reason `ConditionalCheckFailed` on the
  idempotency item, `ingress.py` (ADR-0089 Standard 5 I2) reads the existing idempotency
  record and returns its stored `OperationResult` as a semantically equivalent response
  (Standard 3). It does NOT re-execute the domain call.
- AW3: On `TransactionCanceledException` with reason `ConditionalCheckFailed` on the entity
  item (entity already exists at create time), the handler reads the existing entity and
  returns `SUCCESS` with the existing entity. Entity creation is idempotent (ADR-0090
  Standard 2 M2).
- AW4: `ClientRequestToken` on `TransactWriteItems` provides 10-minute idempotency for the
  DynamoDB API call itself. This covers the case where the network response is lost after
  DynamoDB commits the transaction. The `ClientRequestToken` should be derived from the
  idempotency key to remain stable across retries of the same operation.
- AW5: Domain entity status update transactions (non-creation) include an optimistic lock
  condition on the entity's `version` attribute to prevent lost updates from concurrent
  handlers. On optimistic lock failure, the handler re-fetches and returns the current
  entity state (not an error).

---

### Standard 3: Semantically Equivalent Response

On duplicate detection (Standard 2 AW2), the handler returns a response that is
**semantically equivalent** to the original success response, not an error or a signal that
the operation was a duplicate.

**Rules:**

- SR1: The stored `OperationResult` (Standard 1 DynamoDB record schema) is deserialized
  and returned without re-executing the domain service call.
- SR2: The response status MUST be `SUCCESS` (ADR-0050). Returning `PERMANENT_ERROR` or a
  "DUPLICATE" status code on duplicate detection is incorrect — it forces the caller to
  implement duplicate-specific handling.
- SR3: This behavior satisfies the AWS Builders Library principle: *"Clients cannot tell
  the difference between a request that was completed the first time, and one where the
  server processed the duplicate."* (Amazon Builder's Library, "Making retries safe with
  idempotent APIs").
- SR4: The entity value returned in the `SUCCESS` result is the value stored at original
  write time. It does NOT re-fetch the current entity from DynamoDB. The caller should
  use `GET /feature/entities/{correlation_id}` (ADR-0090 Standard 5) to observe the
  current status if they need the most up-to-date state after a cached replay.

---

### Standard 4: SQS Continuation Message Schema

Long-running domain operations and platform notifications that exceed the ack window are
deferred to SQS. The message carries only routing keys. The worker re-fetches domain state
from DynamoDB on dequeue.

**FIFO queue message schema:**

```json
{
    "feature": "access",
    "intent": "send_approval_notification",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**SQS send parameters:**

```python
sqs.send_message(
    QueueUrl=QUEUE_URL,
    MessageBody=json.dumps(message),
    MessageGroupId=correlation_id,            # FIFO ordering: one group per entity
    MessageDeduplicationId=f"{feature}:{intent}:{correlation_id}",  # 5-min producer dedup
)
```

**Rules:**

- SM1: Messages carry only `feature`, `intent`, and `correlation_id`. No domain objects,
  no entity state, no serialized dataclasses in message bodies. Domain state is authoritative
  in DynamoDB, not in SQS.
- SM2: `MessageGroupId = correlation_id` groups all messages for the same entity into a
  FIFO group. This preserves ordering within a single entity's lifecycle and prevents
  concurrent processing of two steps for the same entity.
- SM3: `MessageDeduplicationId = "<feature>:<intent>:<correlation_id>"` is the same
  schema as the idempotency key (Standard 1). SQS FIFO provides 5-minute producer-side
  deduplication. Application-level idempotency (Standard 2) provides the durable guarantee
  beyond 5 minutes.
- SM4: Workers re-fetch domain entity state from DynamoDB on dequeue. They must not assume
  the entity is in a specific state based on message content. The worker validates the
  current status before executing the continuation.
- SM5: SQS send must happen ONLY after the domain entity write succeeds (ADR-0089 Standard 8
  stateless handler invariant — side-effect sequencing: entity write before SQS enqueue).
  If the entity write fails (TransactionCanceledException on entity condition), the
  SQS message must NOT be sent.

---

### Standard 5: Visibility Timeout and Heartbeating

SQS message visibility timeout governs how long a message is hidden from other consumers
while a worker is processing it.

**Default configuration:**

```
Default visibility timeout: 60 seconds
Maximum visibility timeout (SQS hard limit): 12 hours
Extension mechanism: ChangeMessageVisibility API
```

**Rules:**

- VT1: Default visibility timeout is 60 seconds. This is the initial value set on the SQS
  queue in Terraform.
- VT2: Workers that perform long-running domain operations (DynamoDB writes, platform API
  calls, retries) must call `ChangeMessageVisibility` to extend the visibility timeout
  before it lapses. The extension keeps the message hidden from other consumers.
- VT3: The recommended heartbeat interval is `visibility_timeout / 2` (30 seconds with 60-
  second default). Workers launch a background coroutine or thread that extends visibility
  at this interval while the message is being processed.
- VT4: The 12-hour absolute maximum cannot be extended further. Operations expected to
  exceed 12 hours are not suitable for SQS-based continuation. Escalate to DynamoDB Streams
  or a Step Functions alternative if such durations arise.
- VT5: On worker shutdown (ADR-0057), the visibility extension coroutine must be cancelled
  before message deletion. Letting the visibility lapse on shutdown allows SQS to
  re-deliver the message to another worker — this is correct behavior for graceful shutdown.

---

### Standard 6: Dead-Letter Queue Policy

Each SQS feature queue is paired with a Dead-Letter Queue (DLQ). Messages that fail
processing after the configured receive count are moved to the DLQ.

**Configuration:**

```
maxReceiveCount: 3
DLQ retention: 14 days
DLQ name convention: <feature>-<intent>-queue-dlq.fifo
Alarm: CloudWatch alarm fires when DLQ message count > 0
```

**Rules:**

- DQ1: `maxReceiveCount = 3`. After 3 failed processing attempts, the message is moved to
  the DLQ. This allows for transient failures (e.g., DynamoDB throttling) to recover on
  retry without infinite delivery loops.
- DQ2: CloudWatch alarms fire when DLQ ApproximateNumberOfMessages > 0. Alarm action is
  SNS → operator notification. Alarm threshold and period are Terraform configuration.
- DQ3: DLQ message schema is identical to the source queue schema (Standard 4). DLQ
  messages can be replayed directly to the source queue using the AWS console or a CLI
  command without transformation.
- DQ4: Replay from DLQ to source queue requires **manual operator action**. There is no
  automated DLQ replay in this architecture. Automated replay risks re-introducing a
  systematic bug in a loop.
- DQ5: Operators inspecting the DLQ must check the domain entity status in DynamoDB before
  replaying. If the entity has already reached a terminal status (APPROVED, REJECTED,
  EXPIRED), the DLQ message is a stale continuation and should be deleted, not replayed.
- DQ6: DLQ retention is 14 days. Messages not reviewed or replayed within 14 days are
  permanently lost. This is an operational SLA, not a technical enforcement.

---

### Standard 7: Multi-Connection and At-Least-Once Delivery Handling

All handlers must be idempotent regardless of the transport mode. This standard applies to
both Slack Socket Mode multi-connection delivery and HTTP at-least-once retry behavior.

**Transport-specific context:**

- **Slack Socket Mode:** Slack may maintain up to 10 concurrent WebSocket connections per
  app. The same event may be delivered to any connected process. With ECS `desired_count=2`,
  both tasks receive the event simultaneously. Idempotency via Standard 2 (atomic
  `TransactWriteItems`) ensures first-writer-wins. The losing task receives
  `TransactionCanceledException`, re-fetches the entity, and returns the semantically
  equivalent response (Standard 3).

- **Slack HTTP mode:** Slack retries delivery if the application does not respond within
  3 seconds. With HTTP mode and a single ALB endpoint, only one task receives each delivery.
  However, Slack retries the event if the response is delayed. Standard 2 handles this
  identically — the second delivery finds the idempotency key already written.

- **SQS FIFO:** At-least-once delivery with a 5-minute deduplication window. Standard 2
  provides the durable idempotency guarantee beyond the 5-minute FIFO window.

**Recommendation:** HTTP mode is preferred for production Slack deployments. It eliminates
the multi-connection race scenario entirely and simplifies operational reasoning (single ALB
endpoint, no Socket Mode daemon threads). See also ADR-0089 Standard 4 transport guidance
and ADR-0096 (Slack Handler Constraints).

**Rules:**

- MC1: Application-level idempotency (Standard 2) is required regardless of Slack transport
  mode. HTTP mode reduces the frequency of concurrent duplicate delivery but does not
  eliminate the need for idempotency — at-least-once delivery remains.
- MC2: Socket Mode deployments with multiple ECS tasks MUST implement Standard 2. Without
  atomic dual-write, two tasks may simultaneously create conflicting entity records.
- MC3: Workers that receive duplicate SQS messages (within or beyond the FIFO dedup window)
  must apply Standard 2 before executing domain logic. The idempotency check must be the
  first operation after dequeue, before any domain state read.
- MC4: Handlers must not use optimistic "check-then-act" patterns (query entity, then
  conditionally write). This is inherently racy. Only `ConditionExpression` on the write
  is race-safe.

---

## Migration

This ADR governs new handler implementations. It does not require immediate refactoring of
existing code that uses the prior idempotency patterns.

### Idempotency Key Schema (`IdempotencyKeyBuilder`)

The existing `app/infrastructure/idempotency/key_builder.py` generates keys as
`<namespace>:<operation>:<sha256_hash(components)[:16]>` (e.g.,
`groups_notifications:send_notification:a1b2c3d4e5f6g7h8`). This schema is incompatible
with Standard 1's deterministic `<feature>:<intent>:<correlation_id>` schema.

**Migration path:**

- New handlers implementing this standard use the Standard 1 key schema directly; they do
  not use `IdempotencyKeyBuilder`.
- Existing callers of `IdempotencyKeyBuilder` (background job deduplication, lock-gating
  in `access/sync/interactions/ingress.py`) are grandfathered under their current schema
  until those code paths are migrated to the Standard 1 handler model.
- The `IdempotencyKeyBuilder` class may be retired once all callers are migrated.
- This migration is tracked as a code work item separate from ADR acceptance.

### `IdempotencyService` Protocol Extension

The current `IdempotencyService` (`app/infrastructure/idempotency/service.py`) exposes
only `get(key)` / `set(key, response, ttl_seconds)` / `clear()`. These methods use a
simple `put_item` call — not `TransactWriteItems`. Standard 2 requires an atomic
`TransactWriteItems` combining the domain entity write and the idempotency key write.

**Migration path:**

- The `IdempotencyService` ADR-0077 Category A Protocol must be extended with a
  `transact_write(entity_item, idempotency_item, client_token)` method.
- New handler implementations use `transact_write`; they must NOT use the existing
  `set()` method for the Standard 2 write path.
- The existing `set()` method may be retained for legacy lock-gating callers (grandfathered)
  until migrated. It must NOT be used for new Standard 1/2 idempotency patterns.
- This Protocol extension is tracked as a code work item separate from ADR acceptance.

### ADR-0059 Supersession

This ADR does not supersede any legacy ADRs. ADR-0059 was superseded by ADR-0089.

---

## Compliance

An implementation is compliant with this standard if and only if:

1. Every mutable platform event produces an idempotency key of the form
   `<feature>:<intent>:<correlation_id>` (Standard 1).
2. The domain entity write and idempotency key write occur in a single `TransactWriteItems`
   call with `attribute_not_exists(pk)` condition on the idempotency item (Standard 2).
3. Duplicate detection returns `SUCCESS` with the stored `OperationResult`, not an error
   (Standard 3).
4. SQS continuation messages carry only `feature`, `intent`, `correlation_id` with the
   correct `MessageGroupId` and `MessageDeduplicationId` (Standard 4).
5. Workers call `ChangeMessageVisibility` before the visibility timeout lapses (Standard 5).
6. Each SQS queue is paired with a DLQ with `maxReceiveCount=3`, 14-day retention, and a
   CloudWatch alarm (Standard 6).
7. All handlers are idempotent regardless of transport mode (Standard 7 MC1).

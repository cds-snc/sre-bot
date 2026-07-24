---
status: Accepted
date: 2026-07-24
applies: target
scope: Idempotency, durable queuing, and background jobs — the at-least-once doctrine.
---

# Reliability

## Context

Slack redelivers, queues redeliver, retries retry, and multiple replicas race. **Nothing in this system provides exactly-once delivery** — not SQS FIFO, not DynamoDB Streams, not locks. Every durable guarantee therefore reduces to one primitive: idempotent consumers. The current idempotency store is a read-then-write cache with a TOCTOU race — the opposite of what four other decisions assume — which makes this the highest-priority correctness fix in the codebase.

## Decision

**Idempotency.** Every mutating handler (Slack action, webhook, queue consumer, Tier-2 job) is idempotent via an **atomic conditional claim** on the durable store (the Powertools-idempotency pattern): key `<feature>:<intent>:<idempotency_id>`, claimed with DynamoDB `ConditionExpression: attribute_not_exists(pk)` and status `IN_PROGRESS` with a bounded in-progress TTL; updated to `COMPLETED` with the outcome on success; deleted on failure so redelivery retries. A conditional-check failure branches: `COMPLETED` → return the recorded outcome; `IN_PROGRESS` unexpired → concurrent duplicate, reject/defer; `IN_PROGRESS` expired → the claimant crashed, take over and re-execute. The `idempotency_id` is a **sender-assigned identifier stable across redeliveries** — Slack `event_id`, the webhook provider's delivery id, the id embedded in the queue message or outbox event — **never** the middleware-generated `request_id`, which changes on every redelivered HTTP request. No payload hashes in keys, no truncation, no get-then-set. Where the domain entity lives in the same store, marker and entity go in one `TransactWriteItems`.

**Idempotency is not a general job-status store.** Dedup of a redelivered attempt (the claim/complete/release primitive above) and concurrency locking (a Tier-2 lease, same primitive) are both instances of the one conditional-write contract. Querying the current state of a long-running job for a poller (e.g. `GET /sync-runs/{job_id}`) is a **different capability** — a plain keyed record store that is read many times and overwritten as state progresses — and must not be modeled as a `get`/`set` cache smuggled in under the idempotency name; give it its own small Protocol even if it happens to share a table with idempotency records.

**Queuing.** Work that must survive a crash goes on the durable queue behind a capability Protocol (`QueueService`; SQS today). Semantics assumed everywhere: **at-least-once, possibly out of order.** Messages are control-plane signals — small, carrying `correlation_id` and intent; consumers re-fetch current state from the store rather than trusting queue-borne payloads (also the anti-spoofing posture), and authorize the intent against the fetched entity. Failed messages go to a DLQ after bounded receives; DLQ replay is an authenticated operator action.

**Outbox.** Domain events that must reach the queue reliably are written to an outbox table in the same transaction as the state change, relayed asynchronously. The relay is at-least-once; consumer idempotency absorbs duplicates.

**Outbound retry** is owned by SDK-native configuration at client construction ([outbound-clients.md](outbound-clients.md)); consumers of `TRANSIENT_ERROR` decide whether to retry, honoring `retry_after` when present (queue consumers extend visibility timeout with it). Duplicate side-effects from ambiguous outcomes (timeout after the call landed) are absorbed by — again — consumer idempotency.

**Background jobs.** In-process, hookspec-registered, wrapped in an error boundary so one job's crash never kills the scheduler. Tier-1 jobs are safe to run concurrently on every replica; Tier-2 (singleton) jobs take a TTL lease via the same conditional-write primitive — and the lease is a duplication *optimization*, never a correctness mechanism: the job body must be idempotent regardless. Jobs join shutdown within the lifespan's budget.

## Consequences

- One primitive (conditional write) backs dedup, leases, and outbox claims — one thing to implement correctly per storage backend, and it ports (Redis `SET NX`, Postgres unique insert, Cosmos conditional).
- Conflating dedup, locking, and job-status polling under one `get`/`set` cache — as `app/packages/access/sync` currently does (`platform_lock.py`'s lock is a get-then-set race on the same store `job_runner.py` polls for status) — reproduces the TOCTOU race in a new place and hides three call sites that need three different fixes behind one rewrite; migrating the store requires triaging each caller by which capability it actually needs, not a mechanical `get`→`claim`/`set`→`complete` rename.
- Consumers do more work (re-fetch, idempotency check) than a trust-the-message design; that work is the price of correctness under redelivery, and it is not optional.

## Checks

- Idempotency tests: two concurrent identical requests → one execution (asserted via the conditional-write path, not timing); redelivered message with different framing → same key.
- grep: no `get(` -then-`put` patterns in the idempotency store; no "exactly-once" claims in code or docs.
- DLQ alarm exists; replay path requires an authenticated principal.

## Migration

Ticket: idempotency rewrite (Phase 0 — this is a security-grade fix); outbox implementation; `QueueService` Protocol extraction. Tolerated until closed: none for new mutating handlers — they must use the corrected primitive from its first PR.

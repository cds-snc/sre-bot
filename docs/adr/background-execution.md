---
title: "Background Execution"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [lifecycle, architecture]
constrained_by: [application-lifecycle.md, plugin-registration-discovery.md, configuration-ownership.md, infrastructure-service-classification.md, logging-observability.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Background Execution

## Context and Problem Statement

The application runs work that is not triggered by an inbound request: scheduled reconciliations, periodic health probes, recurring notifications, asynchronous post-write side-effects. The lifespan record reserves the sixth startup phase for starting these loops and the symmetric first shutdown step for stopping them, but it does not say *how* a feature declares a job, *when* a job is permitted to run on more than one process at once, *how* an exception inside a job is handled, or *what* the termination contract is between the loop and the lifespan.

The problem this record addresses: **what is the standard pattern for in-process background work in this application — its registration mechanism, its concurrency-safety classification, its error-isolation contract, and its shutdown semantics?** The answer determines:

1. Whether a feature can add a recurring job through declarative metadata, the same way it adds any other plugin contribution, or whether background work needs a separate registration path.
2. Whether the application can scale horizontally (`desired_count >= 2`) without each task duplicating side-effects, while still preserving the property that any single task can fail and be replaced without coordination.
3. Whether a single failing job can take down the scheduler, the request loop, or the process, or whether failures are bounded to the failing job's invocation.
4. Whether shutdown completes within the orchestrator's grace window, or whether a misbehaving worker forces a `SIGKILL` that bypasses cleanup.

**Constraints:**

- Multiple identical processes run concurrently. Per [cloud-portability.md](cloud-portability.md), the application is one or more stateless processes; `desired_count >= 2` is the production posture. Any background work that produces external side-effects must reckon with N independent runners.
- Boot is a deterministic, ordered sequence ([application-lifecycle.md](application-lifecycle.md)). Jobs are *declared* in phase 3 (registration) and *started* in phase 6 (background). Phase 6 is suppressed by configuration in non-production runs and tests.
- Plugins register via Pluggy entry-points and `hookimpl`s ([plugin-registration-discovery.md](plugin-registration-discovery.md)); registration is fail-fast and frozen at lifespan yield.
- Service-layer outcomes are returned as a closed five-status envelope ([operation-result-pattern.md](operation-result-pattern.md)). Background jobs invoke the same service layer that handlers do; their outcome handling must be coherent with the envelope contract.
- Logging is structured JSONL with correlation context bound to a `ContextVar` ([logging-observability.md](logging-observability.md), [cross-channel-correlation.md](cross-channel-correlation.md)). Job log records inherit the scheduler context, not request context.
- Settings live with the service that consumes them ([configuration-ownership.md](configuration-ownership.md)); the production-only switch and lock-backend identifiers are settings owned at the appropriate layer, not ad-hoc env-var reads scattered across jobs.
- Composed infrastructure services are vendor-portable in shape ([infrastructure-service-classification.md](infrastructure-service-classification.md): Path A; [cloud-portability.md](cloud-portability.md)). The singleton-lock utility is exposed to jobs as a Protocol that names the *capability* (conditional-write coordination with TTL-bounded leases), not a vendor's API. AWS is the day-0 implementation; the architecture must support swappable providers (Redis, PostgreSQL, Azure Cosmos DB, GCP Firestore, in-process for local/CI) without job-code changes.

**Non-goals:**

- This record does not pick the scheduling primitive (a particular cron-style library vs. asyncio loop). It defines the contract; the chosen library is replaceable as long as the contract holds.
- This record does not specify per-job idempotency mechanics (key derivation, dedup-record schema, collision behavior). Those belong to [handler-idempotency.md](handler-idempotency.md), which background jobs share with request handlers.
- This record does not introduce out-of-process workers, separate worker process types, or external job queues. That posture (queue-driven workers) is owned by [message-queuing.md](message-queuing.md).
- This record does not enumerate the application's current job inventory; the inventory lives in feature packages and is observable from the registry, not from this document.

## Considered Options

**Option 1 — Hookspec-registered, in-process, two-tier-classified jobs with infrastructure-owned singleton lock.** Each feature declares its jobs through a `register_background_job` hookspec at phase 3. Jobs self-classify as Tier-1 (concurrent-safe across N tasks) or Tier-2 (singleton; one task at a time). A shared infrastructure utility wraps Tier-2 jobs with a capability-shaped conditional-write lock with TTL-bounded leases — exposed to jobs as a Path-A Protocol, with AWS DynamoDB as the day-0 implementation and other providers (Redis, PostgreSQL, Cosmos DB) substitutable behind the same Protocol. A shared error boundary wraps every job and converts exceptions to structured log records without propagation. The runner starts in phase 6 only when the production-equivalent settings flag is set; shutdown signals via `threading.Event` with a ≤5-second join.

**Option 2 — Per-feature, ad-hoc job runners.** Each feature wires its own scheduler (thread or task), its own lock (or none), and its own error handling. The host has no shared registration, no shared classification, and no shared shutdown contract.

**Option 3 — External job queue with worker processes.** Replace in-process scheduling with a queue (SQS, Celery, etc.) and a separate worker process type. The host application serves only HTTP/transport traffic; workers run elsewhere.

**Option 4 — `asyncio.create_task()` on the FastAPI event loop.** Launch background work as fire-and-forget tasks on the request-handling loop. No threads; no separate runner.

## Decision Outcome

**Chosen: Option 1 — hookspec-registered, in-process, two-tier-classified jobs with infrastructure-owned singleton lock.**

This is the only option that combines (a) a single declarative registration shape consistent with the rest of the plugin model, (b) a horizontal-scaling story that does not require operators to reason about which task is "primary," (c) a bounded and observable error contract, and (d) a shutdown contract that fits inside the orchestrator's grace window. Per-feature ad-hoc runners (Option 2) make the contract invisible at the host level. External workers (Option 3) are a different architecture, governed by [message-queuing.md](message-queuing.md), and out of scope for jobs that are inherently colocated with the application's own state and code path. Loop-resident `asyncio.create_task` (Option 4) couples background work to the request-handling event loop, so a slow synchronous job blocks request processing — this is a runtime risk the application explicitly does not take.

### Registration shape

Each feature package contributes jobs through a single hookspec — `register_background_jobs(registry: BackgroundJobRegistry) -> None` — invoked once during phase 3. The registry exposes one method:

```python
registry.register(
    name: str,                      # globally unique, dotted: "<feature>.<job>"
    schedule: Schedule,             # interval or cron-shaped value object
    job: Callable[..., None] | Callable[..., Awaitable[None]],
    tier: Literal["tier1", "tier2"],
    timeout: float | None = None,   # per-invocation soft cap; default = scheduler interval
)
```

Registration is a metadata-only operation: it does not start the job, allocate threads, or open external connections. A registration error (missing name, duplicate name, unknown tier, invalid schedule) raises during phase 3 and halts boot per the lifespan record's fail-fast contract. The registry is frozen at lifespan yield; jobs are not added on a running process.

Jobs do not return values. Their domain effect is mediated through the service layer they call, which uses the standard envelope. The job body's responsibility is to invoke the service, observe the envelope status, and emit observability records — not to surface a result.

### Two-tier concurrency model

Every registered job declares one of two tiers. The tier is part of the job's contract, not a runtime decision.

| Tier | Meaning | Coordination mechanism |
| --- | --- | --- |
| Tier-1 | Concurrent-safe. Read-only, log-only, or naturally-idempotent writes (`PUT IF NOT EXISTS`, conditional updates, upserts). Running on N tasks simultaneously produces the same end state as running once. | None. Each task runs the job independently. |
| Tier-2 | Singleton. Sends external notifications, provisions external resources, performs long-running I/O, or consumes significant CPU/memory. Running on N tasks would duplicate side-effects or exhaust resources. | A distributed lock keyed by job name; only the lock holder executes. |

**Tier-1 examples (shape):** scheduler heartbeat, integration health probes, cache warmup that uses conditional writes.

**Tier-2 examples (shape):** sending recurring notifications, provisioning external accounts, generating reports, reconciling external state with stored state.

A job whose classification is uncertain is registered as Tier-2. The bias is intentional: a Tier-2 job that could have been Tier-1 wastes one acquire-and-release per interval; a Tier-1 job that should have been Tier-2 produces duplicate external side-effects on every interval, with no automatic detection.

**Idempotent design is mandatory regardless of tier.** Locks reduce duplication; they do not establish exactly-once semantics. A lock-holding task may crash mid-run, drop the lock via TTL, and a subsequent run on a different task must produce a coherent end state. Idempotency rules are governed by [handler-idempotency.md](handler-idempotency.md) and apply to background jobs with the same force as to request handlers.

### Singleton lock — capability-shaped infrastructure utility

The singleton lock is a **shared infrastructure capability** ([infrastructure-service-classification.md](infrastructure-service-classification.md): Path A, Shared). Features depend on the Protocol; the implementation behind the Protocol is selected by configuration. Tier-2 jobs do not import any vendor SDK to acquire a lock; they receive a `SingletonLock` handle through dependency injection.

```text
app/infrastructure/locks/
    __init__.py          # public surface: SingletonLock Protocol, LockHandle value type
    in_memory.py         # in-process backend for local dev and CI
    aws.py               # AWS DynamoDB-backed implementation (day-0 production)
    # redis.py, postgres.py, cosmos.py … future provider implementations live here
    settings.py          # backend selector, TTL defaults, table/key-prefix
```

**The Protocol contract.** The lock exposes three operations:

- **`acquire(lock_key, ttl_seconds, holder_id) -> LockHandle | None`** — atomically acquires the lock if it is free or lapsed; returns a handle on success, `None` on contention. The handle carries the holder identity and the absolute expiry.
- **`release(handle) -> None`** — releases a lock the caller holds. Idempotent: releasing an already-free or expired lock is a no-op success. A lock held by a different `holder_id` is not released; this is enforced at the implementation layer.
- **`extend(handle, additional_seconds) -> bool`** — extends the lease on a held lock. Used by long-running jobs whose duration may approach the initial TTL. Returns `False` if the lock has already lapsed and been reclaimed by another holder.

**Semantic guarantees the Protocol promises (and every implementation must satisfy):**

- **Mutual exclusion.** At most one `holder_id` observes a successful `acquire` for a given `lock_key` at a given moment.
- **TTL-bounded recovery.** A holder that crashes without releasing has its lock auto-reclaimed after `ttl_seconds`; no out-of-band cleanup is required.
- **First-writer-wins atomicity.** Two simultaneous `acquire` calls have a deterministic winner; the loser receives `None`.
- **Non-acquisition is non-exceptional.** Contention is observable as a `None` return (or equivalent), not a raised exception. This is the expected, normal path on N-1 of N tasks every scheduling interval.

**Calibration rule (independent of provider):**

- TTL ≥ 2× the expected job duration so a slow run does not lapse mid-flight.
- TTL strictly less than the schedule interval so a killed task does not lock the next interval out.
- A successor task acquires on the next interval after the TTL elapses; idempotent design ([handler-idempotency.md](handler-idempotency.md)) absorbs any work the previous holder may have partially completed.

**Operator override.** A documented utility (CLI entry point, optionally exposed through an admin route or operator command) forcibly releases a lock by `lock_key` regardless of holder; emits `singleton_lock_operator_released` with `operator_id`, `reason`, `lock_key`. The override is idempotent: forcing a release on an already-free lock is a no-op success. Each implementation provides this operation; its mechanics differ but the contract is identical.

#### Day-0 implementation: AWS DynamoDB

The day-0 backend is DynamoDB conditional writes with an item-level TTL attribute. The implementation in `app/infrastructure/locks/aws.py`:

- **Acquire** is `PutItem` with `ConditionExpression="attribute_not_exists(<lock_key>) OR ttl < :now"`. The condition allows a lapsed lock to be reclaimed without an out-of-band cleanup step. The item carries `holder_id`, `acquired_at`, `ttl`. A `ConditionalCheckFailedException` is the contention signal and translates to `acquire → None`.
- **Release** is `DeleteItem` with `ConditionExpression="holder_id = :self"`. A task only deletes its own lock; a TTL-expired lock owned by a dead task is reclaimed by the next acquire, not by a release.
- **Extend** is `UpdateItem` with `ConditionExpression="holder_id = :self"` setting a new `ttl`. A failed condition (held by another, or already lapsed) translates to `extend → False`.

#### Provider mappings (substitutable behind the Protocol)

- **Redis (in-cluster or managed):** `acquire` uses `SET <key> <holder_id> NX PX <ttl_ms>`; `release` uses a Lua script that compares `holder_id` and deletes atomically (the canonical "Redlock-style" compare-and-delete idiom); `extend` uses a similar compare-and-`PEXPIRE` Lua script.
- **PostgreSQL:** `acquire` uses `INSERT INTO locks (key, holder_id, expires_at) VALUES (...) ON CONFLICT (key) DO UPDATE SET holder_id = EXCLUDED.holder_id, expires_at = EXCLUDED.expires_at WHERE locks.expires_at < now() RETURNING ...`; `release` is a conditional `DELETE` checking `holder_id`; `extend` is a conditional `UPDATE` of `expires_at`.
- **Azure Cosmos DB:** an item with the lock key as `id` and a `holder_id` property; `acquire` uses an upsert with a `pre-trigger` or stored procedure that enforces "free-or-expired"; `release` is a conditional delete via `If-Match` on the holder eTag.
- **GCP Firestore:** a transaction that reads the lock document, checks `holder_id` and expiry, and writes if the condition holds; `release` is the symmetric transaction.
- **In-memory (local dev and CI):** a process-local dictionary protected by a `threading.Lock`; satisfies the Protocol contract within a single process. Sufficient for the local-development single-process posture per [environment-parity.md](environment-parity.md).

The Protocol's contract tests (mutual exclusion under simulated contention, TTL-bounded recovery after holder crash, idempotent release) run against every provider implementation. A provider that fails a contract test is not a valid backend.

### Error isolation — `safe_run`

Every job invocation runs inside a shared error boundary — `safe_run` — that:

- Catches all exceptions raised by the job body and any service it calls.
- Emits a `job_failed` structured log record with `job_name`, `module`, `function`, `duration_seconds`, `error_type`, and `error_message`. The redaction processor ([data-redaction-policy.md](data-redaction-policy.md)) is in effect on all such records.
- Does not re-raise. Returns normally so the scheduler thread proceeds to the next interval.
- Does not retry. Retry policy is the job's own concern; the boundary is concerned only with not allowing one failed invocation to terminate the runner.
- Wraps both Tier-1 and Tier-2 jobs identically. Tier-2 lock acquisition runs *outside* the boundary; a lock acquisition failure is not a job failure.

A job that raises produces exactly one `job_failed` log record per interval. The scheduler continues. The process stays up. Operational monitoring fires off the absence of `job_completed` for the job, off `job_failed` rate, or off the absence of `scheduler_heartbeat` (which would indicate the scheduler thread itself died — a class of failure the boundary cannot catch).

### Production-only execution

Phase 6 starts the runner only when the application's canonical production-equivalent indicator is true. The indicator is read once during phase 1 (configuration) and surfaced as a settings-class attribute consumed by phase 6; ad-hoc environment-variable reads inside individual jobs are prohibited.

In non-production (local development, integration tests), phase 6 is a no-op for runner startup but **registration in phase 3 still runs**. This is deliberate: a job whose registration code is broken must surface that failure in test, not only in production. The lifespan emits `background_runner_skipped` with `reason="non_production"` and proceeds.

### Shutdown contract

The runner uses a `threading.Event` for shutdown signaling.

- The runner thread checks the event between job dispatches and between blocking calls; it does not pre-empt a job mid-execution.
- Phase 6 reverse: the lifespan sets the event and joins the runner thread with a ≤5-second timeout, per [application-lifecycle.md](application-lifecycle.md).
- The runner's poll interval (sleep between scheduler ticks) is ≤5 seconds, so the event is observed within the join budget.
- A running job is allowed to complete during shutdown if it finishes within the budget; otherwise the join times out, the lifespan emits `background_runner_join_timeout` with `pending_jobs`, and the next shutdown phase proceeds. The orchestrator's grace window absorbs the residue.
- Tier-2 jobs that do not complete during shutdown leave their lock held; the TTL releases it. A successor task acquires on the next interval.

### Concurrency primitive — threads, not the request loop

The runner runs in a dedicated thread (or worker thread pool for CPU-affine jobs). Work is **not** scheduled as `asyncio.create_task` on the request-handling event loop. The reasons:

- A long synchronous call inside a job (a vendor SDK that blocks on I/O, a heavy serialization step) would block the event loop and stall request handling if scheduled there. The thread-based runner isolates this risk.
- The shutdown contract is straightforward to express with `threading.Event` and `Thread.join(timeout=...)`; equivalent constructs on the event loop (`asyncio.shield`, task cancellation, `asyncio.wait_for`) compose differently and are easier to misuse.
- Async-shaped jobs are still permitted: the runner schedules them with `asyncio.run` (or an analogous adapter) on a dedicated loop owned by the runner thread, not the request loop. Async support is a runner-internal capability, not a coupling to the request stack.

### Observability contract

Background execution emits a fixed set of structured log events:

- `background_runner_started` — phase 6 success: `job_count`, `tier1_count`, `tier2_count`.
- `background_runner_skipped` — phase 6 no-op in non-production: `reason`.
- `background_runner_stopped` — phase 6 reverse success: `joined_within_timeout` (bool).
- `background_runner_join_timeout` — phase 6 reverse exceeded budget: `pending_jobs`.
- `scheduler_heartbeat` — periodic proof-of-life: `time` (monotonic).
- `job_started` — per invocation: `job_name`, `tier`.
- `job_completed` — per successful invocation: `job_name`, `duration_seconds`.
- `job_failed` — per failed invocation: `job_name`, `error_type`, `error_message`, `duration_seconds`.
- `singleton_lock_acquired` — Tier-2 lock taken: `job_name`, `lock_key`, `ttl_seconds`, `task_id`.
- `singleton_lock_released` — Tier-2 lock returned: `job_name`, `lock_key`, `held_seconds`, `task_id`.
- `singleton_lock_skipped` — Tier-2 contention (expected): `job_name`, `lock_key`, `held_by_task_id`.
- `singleton_lock_ttl_expired` — Tier-2 reclaim of lapsed lock: `job_name`, `lock_key`.
- `singleton_lock_operator_released` — manual override: `job_name`, `lock_key`, `operator_id`, `reason`.

Duration measurement uses `time.monotonic()`. Records carry the standard correlation context (a per-invocation correlation ID generated at job start; the request_id slot is left empty since the work is not request-scoped).

### What this record does not change

- The lifespan's six-phase order, fail-fast contract, and reverse-shutdown budget remain authoritative.
- The plugin registration mechanism (entry-points, frozen registries, fail-fast) remains authoritative; this record adds one hookspec to the contract.
- The service-layer envelope remains the contract for domain outcomes; jobs invoke services and observe envelopes, they do not invent a parallel result type.
- The operator's mental model for horizontal scaling remains: "any task can fail; replacement is automatic; no task is primary." The lock utility is the bounded acknowledgement that some side-effects need to be exclusive — it is not a leader-election service.

## Consequences

**Positive:**

- A new background job is added through one hookimpl in a feature package and one entry-point line in `pyproject.toml` — the same shape as any other plugin contribution. There is no special path for background work.
- Horizontal scaling works without operator coordination: Tier-1 jobs run on every task by design; Tier-2 jobs run on whichever task wins the lock; failures of any task are absorbed by lock TTL and re-acquisition.
- Job failures are bounded: `safe_run` localizes blast radius to one invocation; the scheduler keeps running; the process keeps serving requests. The error contract is observable through a fixed log-event vocabulary.
- Shutdown completes within the orchestrator grace window with high probability. The bounded join, the bounded poll interval, and the TTL-based lock release together avoid stuck-state recovery on operator intervention paths.
- The lock utility is a single piece of infrastructure code; its rules (TTL, condition expression, audit logging) are reviewed once and reused everywhere.

**Tradeoffs accepted:**

- A Tier-2 job that should have been Tier-1 wastes one lock acquire/release per interval. Acceptable: lock operations are cheap relative to the job body.
- The thread-based runner uses one (or a small pool of) Python threads regardless of whether the loop is busy. Acceptable: the alternative is event-loop coupling, which is a worse failure mode.
- Phase 6 not running in non-production means a job that *only* fails when scheduled (e.g., an integration that breaks on real network calls) is not exercised by the standard test path. Acceptable: registration errors are caught in phase 3 in every environment; runtime failures of integrations are exercised through targeted integration tests against staging.

**Risks and mitigations:**

- **A Tier-2 job's TTL is set shorter than its actual runtime.** The lock lapses mid-run; a second task acquires; both run, defeating the singleton property. *Mitigation:* the lock utility documents the calibration rule (TTL ≥ 2× expected job duration, < schedule interval); job authors are responsible for validating with measured duration before classifying as Tier-2.
- **A scheduler thread silently dies (segfault, native crash in a C extension).** No `safe_run` boundary catches it; jobs stop running. *Mitigation:* `scheduler_heartbeat` absence is the primary detection signal; an operator alarm fires if heartbeat lapses past 2× the heartbeat interval. Process replacement is the recovery action.
- **A jobs's body invokes a service that holds an open connection past `safe_run` return.** Pooled-resource leaks accumulate over many failed runs. *Mitigation:* services own their pool lifecycle ([infrastructure-service-classification.md](infrastructure-service-classification.md)); jobs do not bypass DI to acquire resources directly. Code review enforces.
- **Operator-released lock collides with a still-running task.** Two tasks now run the Tier-2 job. *Mitigation:* the override is documented as a recovery action with audit logging; routine schedules do not invoke it; the released event names the operator and reason for post-incident review.

## Confirmation

Compliance is verified by:

- **Code review.** Every job is registered through the `register_background_jobs` hookspec; no direct `Thread()` construction in feature code; no `asyncio.create_task` for background work outside the runner; Tier-2 jobs use the shared lock utility, not a local re-implementation.
- **Static analysis.** A check forbids module-level scheduler instantiation, module-level lock acquisition, and `from threading import Thread` inside feature packages.
- **Tests.** A boot test asserts the registry contains the expected jobs after phase 3, with correct tiers. A shutdown test asserts that a running Tier-2 job's lock is released or TTL-bounded after a forced runner stop. A regression test asserts that a job raising during execution does not stop the scheduler thread (the next interval's `job_started` still fires).
- **Operational checks.** Dashboards visualize `job_completed` rate, `job_failed` rate, `singleton_lock_skipped` rate, and `scheduler_heartbeat` cadence. Alarms fire on heartbeat absence and on `job_failed` rate above a threshold per job.

## Source References

1. The Twelve-Factor App — Concurrency (Factor VIII)
   - URL: <https://12factor.net/concurrency>
   - Accessed: 2026-04-29
   - Relevance: Defines the multi-process model under which N stateless processes are managed by an external supervisor. The two-tier classification (Tier-1 concurrent-safe vs. Tier-2 singleton) is the application-level expression of the constraints this factor imposes on background work that produces external side-effects.

2. The Twelve-Factor App — Disposability (Factor IX)
   - URL: <https://12factor.net/disposability>
   - Accessed: 2026-04-29
   - Relevance: "Processes shut down gracefully when they receive a SIGTERM signal from the process manager. […] Processes should also be robust against sudden death, in the case of a failure in the underlying hardware. […] A queueing backend such as Beanstalkd that returns jobs to the queue when clients disconnect or time out is the ideal." Grounds the bounded-shutdown contract and the lock-with-TTL recovery model.

3. AWS Builders' Library — Reliability, Constant Work, and a Good Cup of Coffee
   - URL: <https://aws.amazon.com/builders-library/reliability-and-constant-work/>
   - Accessed: 2026-05-08
   - Relevance: Argues for steady, bounded background work that does not vary with load — the operational property the scheduler-driven model produces. Grounds the design preference for fixed-interval, bounded-duration jobs over event-burst processing.

4. Amazon ECS — Task Lifecycle and Stop Timeout
   - URL: <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_lifecycle.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the `SIGTERM → stopTimeout (default 30s) → SIGKILL` contract enforced by ECS. The ≤5-second runner-join budget composes inside this window with the ≤10-second request-drain budget defined by the lifespan record, leaving headroom for resource teardown and SIGKILL margin.

5. Python — `threading.Event`
   - URL: <https://docs.python.org/3/library/threading.html#event-objects>
   - Accessed: 2026-05-08
   - Relevance: Documents `Event.set()` / `Event.is_set()` / `Event.wait(timeout)` as a thread-safe signaling primitive. Grounds the runner-shutdown signaling contract: lifespan reverse phase 6 calls `event.set()`, the runner observes `event.is_set()` between dispatches, and the lifespan calls `Thread.join(timeout=5)` to bound shutdown.

6. Python — `time.monotonic`
   - URL: <https://docs.python.org/3/library/time.html#time.monotonic>
   - Accessed: 2026-05-08
   - Relevance: Documents the monotonic clock as the correct source for elapsed-duration measurement (immune to wall-clock adjustments). Grounds the rule that `duration_seconds` in `job_completed` and `job_failed` records is computed from `time.monotonic()` deltas, not `time.time()`.

7. AWS DynamoDB — Conditional Writes (day-0 implementation)
   - URL: <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the `ConditionExpression` semantics used by the day-0 singleton-lock implementation — `attribute_not_exists` and equality comparison on item attributes for atomic acquire and release. Establishes that `PutItem` with a failed condition is a non-error outcome (`ConditionalCheckFailedException`), which is the mechanism by which non-acquiring tasks discover contention without an exception path.

8. AWS DynamoDB — Time To Live (TTL) (day-0 implementation)
   - URL: <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html>
   - Accessed: 2026-05-08
   - Relevance: Documents item-level TTL as a numeric attribute interpreted in epoch seconds, with item deletion handled by the service "typically within a few days" of expiration. The day-0 lock implementation uses TTL as a *lifetime cap on visibility for acquire purposes* (the acquire condition checks `ttl < :now`), so reclamation is immediate at the API surface even though physical deletion lags. Grounds the rule that TTL must be shorter than the schedule interval.

9. Redis — `SET` Command with `NX` and `PX` (alternate-provider mapping)
   - URL: <https://redis.io/commands/set/>
   - Accessed: 2026-05-08
   - Relevance: Documents `SET key value NX PX milliseconds` as the canonical primitive for "acquire if absent, with TTL." Grounds the Redis provider mapping for the singleton-lock Protocol; the compare-and-delete idiom for safe release is documented under the Lua-scripting pattern at <https://redis.io/docs/latest/develop/use/patterns/distributed-locks/>.

10. PostgreSQL — `INSERT ... ON CONFLICT` (UPSERT) (alternate-provider mapping)
    - URL: <https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT>
    - Accessed: 2026-05-08
    - Relevance: Documents `ON CONFLICT (key) DO UPDATE ... WHERE` as the conditional-write primitive used by a PostgreSQL-backed singleton-lock implementation. Grounds the alternate-provider mapping; an `expires_at` column plus the `WHERE locks.expires_at < now()` clause provides the TTL-bounded recovery contract.

## Change Log

- 2026-05-08: Created. Establishes hookspec-registered, in-process background jobs with two-tier concurrency classification (Tier-1 concurrent-safe vs. Tier-2 singleton). The singleton-lock utility is exposed as a capability-shaped Path-A Protocol (`SingletonLock` with `acquire` / `release` / `extend` operations and TTL-bounded leases); AWS DynamoDB conditional writes are the day-0 implementation, with Redis (`SET NX PX`), PostgreSQL (`INSERT ... ON CONFLICT`), Azure Cosmos DB, GCP Firestore, and an in-memory backend explicitly substitutable behind the same Protocol. Adds a shared `safe_run` error boundary that bounds blast radius to a single invocation, a `threading.Event` shutdown contract bounded to ≤5 seconds, a production-only execution gate that still exercises registration in non-production, and a fixed observability event vocabulary. Defers per-job idempotency mechanics to handler-idempotency.md, queue-driven worker postures to message-queuing.md, and the lifespan ordering and budgets to application-lifecycle.md.

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
- Settings live with the service that consumes them ([configuration-ownership.md](configuration-ownership.md)); the production-only switch and lock-table identifiers are settings owned at the appropriate layer, not ad-hoc env-var reads scattered across jobs.

**Non-goals:**

- This record does not pick the scheduling primitive (a particular cron-style library vs. asyncio loop). It defines the contract; the chosen library is replaceable as long as the contract holds.
- This record does not specify per-job idempotency mechanics (key derivation, dedup-record schema, collision behavior). Those belong to [handler-idempotency.md](handler-idempotency.md), which background jobs share with request handlers.
- This record does not introduce out-of-process workers, separate worker process types, or external job queues. That posture (queue-driven workers) is owned by [message-queuing.md](message-queuing.md).
- This record does not enumerate the application's current job inventory; the inventory lives in feature packages and is observable from the registry, not from this document.

## Considered Options

**Option 1 — Hookspec-registered, in-process, two-tier-classified jobs with infrastructure-owned singleton lock.** Each feature declares its jobs through a `register_background_job` hookspec at phase 3. Jobs self-classify as Tier-1 (concurrent-safe across N tasks) or Tier-2 (singleton; one task at a time). A shared infrastructure utility wraps Tier-2 jobs with a DynamoDB conditional-write lock keyed by job name. A shared error boundary wraps every job and converts exceptions to structured log records without propagation. The runner starts in phase 6 only when the production-equivalent settings flag is set; shutdown signals via `threading.Event` with a ≤5-second join.

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

### Singleton lock — infrastructure utility

The singleton lock is a **shared infrastructure utility** ([infrastructure-service-classification.md](infrastructure-service-classification.md): Path A, Shared) — a single implementation in `app/infrastructure/<lock-service>/` consumed by every Tier-2 job. Features do not implement their own locks; they receive the utility through dependency injection.

The utility is implemented over DynamoDB conditional writes with an item-level TTL attribute (the production data store; portable to any backing store that supports conditional writes plus TTL):

- **Acquire:** `PutItem` with `ConditionExpression="attribute_not_exists(<lock_key>) OR ttl < :now"`. The condition allows a lapsed lock to be reclaimed without an out-of-band cleanup step. The item carries `task_id`, `acquired_at`, `ttl`.
- **Hold semantics:** the TTL is the lock's lifetime cap. Setting TTL ≥ 2× the expected job duration accommodates cold-start latency without leaving the lock held past plausible job completion. Setting TTL strictly less than the schedule interval is the contract that prevents permanent lockout from a killed task.
- **Release:** `DeleteItem` with `ConditionExpression="task_id = :self"`. A task only deletes its own lock; a TTL-expired lock owned by a dead task is reclaimed by the next acquire, not a release.
- **Non-acquisition:** if the conditional acquire fails, the calling task logs at debug-level (`singleton_lock_skipped` with `held_by_task_id`) and skips the run. This is the expected, non-exceptional path on N-1 of N tasks every interval.
- **Operator override:** a documented utility (CLI entry point, optionally exposed through an admin route or operator command) deletes the lock unconditionally and emits `singleton_lock_operator_released` with `operator_id`, `reason`, `lock_key`. The override is idempotent: deleting an already-free lock is a no-op success.

The lock utility is a Path-A capability — vendor-portable in shape, even though the current backing store is DynamoDB. A Tier-2 job's contract names the lock by capability ("singleton coordination"), not by store.

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

3. AWS DynamoDB — Conditional Writes
   - URL: <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the `ConditionExpression` semantics used by the singleton lock — `attribute_not_exists` and equality comparison on item attributes for atomic acquire and release. Establishes that `PutItem` with a failed condition is a non-error outcome (`ConditionalCheckFailedException`), which is the mechanism by which non-acquiring tasks discover contention without an exception path.

4. AWS DynamoDB — Time To Live (TTL)
   - URL: <https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html>
   - Accessed: 2026-05-08
   - Relevance: Documents item-level TTL as a numeric attribute interpreted in epoch seconds, with item deletion handled by the service "typically within a few days" of expiration. The lock utility uses TTL as a *lifetime cap on visibility for acquire purposes* (the acquire condition checks `ttl < :now`), so reclamation is immediate at the API surface even though physical deletion lags. Grounds the rule that TTL must be shorter than the schedule interval.

5. AWS Builders' Library — Reliability, Constant Work, and a Good Cup of Coffee
   - URL: <https://aws.amazon.com/builders-library/reliability-and-constant-work/>
   - Accessed: 2026-05-08
   - Relevance: Argues for steady, bounded background work that does not vary with load — the operational property the scheduler-driven model produces. Grounds the design preference for fixed-interval, bounded-duration jobs over event-burst processing.

6. Amazon ECS — Task Lifecycle and Stop Timeout
   - URL: <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_lifecycle.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the `SIGTERM → stopTimeout (default 30s) → SIGKILL` contract enforced by ECS. The ≤5-second runner-join budget composes inside this window with the ≤10-second request-drain budget defined by the lifespan record, leaving headroom for resource teardown and SIGKILL margin.

7. Python — `threading.Event`
   - URL: <https://docs.python.org/3/library/threading.html#event-objects>
   - Accessed: 2026-05-08
   - Relevance: Documents `Event.set()` / `Event.is_set()` / `Event.wait(timeout)` as a thread-safe signaling primitive. Grounds the runner-shutdown signaling contract: lifespan reverse phase 6 calls `event.set()`, the runner observes `event.is_set()` between dispatches, and the lifespan calls `Thread.join(timeout=5)` to bound shutdown.

8. Python — `time.monotonic`
   - URL: <https://docs.python.org/3/library/time.html#time.monotonic>
   - Accessed: 2026-05-08
   - Relevance: Documents the monotonic clock as the correct source for elapsed-duration measurement (immune to wall-clock adjustments). Grounds the rule that `duration_seconds` in `job_completed` and `job_failed` records is computed from `time.monotonic()` deltas, not `time.time()`.

## Change Log

- 2026-05-08: Created. Establishes hookspec-registered, in-process background jobs with two-tier concurrency classification (Tier-1 concurrent-safe vs. Tier-2 singleton), an infrastructure-owned conditional-write singleton lock with TTL-based recovery, a shared `safe_run` error boundary that bounds blast radius to a single invocation, a `threading.Event` shutdown contract bounded to ≤5 seconds, a production-only execution gate that still exercises registration in non-production, and a fixed observability event vocabulary. Defers per-job idempotency mechanics to handler-idempotency.md, queue-driven worker postures to message-queuing.md, and the lifespan ordering and budgets to application-lifecycle.md.

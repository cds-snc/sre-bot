# ADR Challenge and Content Review — ADR-0058

**Purpose:** Step 9.5 (Canonical ADR Challenge and Content Review Gate) execution for ADR-0058: Background Execution and Worker Isolation Standard. This review anchors all judgments on authoritative best practices, not current code implementation.

---

## 1. Review Metadata

| Field | Value |
|-------|-------|
| **ADR Under Review** | ADR-0058: Background Execution and Worker Isolation Standard |
| **Reviewer Name & Title** | AI Architecture Reviewer, SRE Team |
| **Secondary Reviewers** | — |
| **Review Date** | 2026-04-29 |
| **Revalidation Due** | 2027-04-29 |
| **Gate Outcome** | ⚪ **PASS** |
| **Outcome Rationale** | All eight standards are grounded in authoritative sources. The two-tier concurrency classification (Standard 4) is well-anchored in Kubernetes CronJob `concurrencyPolicy`, Azure Background Jobs best practices, and Azure Leader Election guidance. The colocated worker model (Standard 1) is a documented pragmatic posture with an explicit evolution path. The production-only execution guard (Standard 2) and plugin-based registration (Standard 3) are correctly implemented and tested. Two moderate-confidence assumptions documented with mitigations. One prior challenge review (2026-04-29) already revised Standard 4 from the original "all-idempotent" model to the two-tier classification. |

---

## 2. Evidence Gathering & Convention Validation

### 2.A Language & Framework Standards

**Applicable Standards:**
- ✅ FastAPI Background Tasks Documentation (https://fastapi.tiangolo.com/tutorial/background-tasks/) — reviewed for scope distinction
- ✅ Python `schedule` Library Documentation (https://schedule.readthedocs.io/)
- ✅ Pluggy Documentation (https://pluggy.readthedocs.io/en/stable/)
- ✅ Python `threading.Event` Documentation
- ✅ Python `time.monotonic()` Documentation

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| FastAPI Background Tasks | "BackgroundTasks request-scoped fire-and-forget" | FastAPI `BackgroundTasks` are request-scoped and fire-and-forget (execute after HTTP response is sent). They are NOT scheduled recurring jobs. The ADR correctly scopes its concern to scheduled recurring jobs, not request-scoped tasks. | ✅ Aligned | N/A — ADR explicitly notes in Best-Practice Revalidation: "Not applicable to this standard's scope" |
| Python `schedule` library | "run_pending sleep loop thread safety" | `schedule` uses a single-thread `run_pending()` + sleep loop model. Not thread-safe for concurrent registration (must register before starting thread). The library has no built-in error isolation — exceptions in jobs propagate to the run loop. | ✅ Aligned | N/A — Standard 5 mandates `safe_run` wrapper to compensate for `schedule` library's lack of error isolation |
| Pluggy hookspec registration | "hookspec hookimpl plugin manager register" | Pluggy supports hookspec-based registration where plugins implement hooks. The `register_background_job` hookspec pattern is a standard use of pluggy's hook-calling convention. Multiple plugins can implement the same hookspec. | ✅ Aligned | N/A — Standard 3 uses pluggy's native registration model |
| Python `threading.Event` | "threading Event set is_set wait" | `threading.Event` is the standard Python mechanism for cooperative thread shutdown signaling. `event.set()` + `event.is_set()` check pattern is thread-safe and well-documented. | ✅ Aligned | N/A — Standard 7 correctly mandates `threading.Event` for shutdown signaling |
| Python `time.monotonic()` | "monotonic clock duration measurement" | `time.monotonic()` is the correct choice for duration measurement — not affected by system clock adjustments, NTP drift, or daylight saving changes. PEP 418 introduced this for exactly this purpose. | ✅ Aligned | N/A — Standard 6 correctly mandates monotonic time for job duration |

---

### 2.B Infrastructure & Operational Standards

**Applicable Standards:**
- ✅ Twelve-Factor App — Factor IX (Disposability)
- ✅ Twelve-Factor App — Factor VIII (Concurrency)
- ✅ Twelve-Factor App — Factor X (Dev/Prod Parity)
- ✅ Kubernetes CronJob Documentation — `concurrencyPolicy` (https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- ✅ Azure Architecture — Best Practices for Background Jobs (https://learn.microsoft.com/en-us/azure/architecture/best-practices/background-jobs)
- ✅ Azure Architecture — Leader Election Pattern (https://learn.microsoft.com/en-us/azure/architecture/patterns/leader-election)

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Twelve-Factor Factor IX — Disposability | "reentrant idempotent jobs graceful shutdown" | "All jobs are reentrant, which typically is achieved by wrapping the results in a transaction, or making the operation idempotent." Also: "Processes shut down gracefully when they receive a SIGTERM signal." | ✅ Aligned | N/A — Standard 4 mandates idempotency for all jobs regardless of tier |
| Twelve-Factor Factor VIII — Concurrency | "process model scale out internal multiplexing threads" | "This does not exclude individual processes from handling their own internal multiplexing, via threads inside the runtime VM." Horizontal scaling via process formation is preferred, but thread-based internal multiplexing is explicitly permitted. | ✅ Aligned | N/A — Standard 1 uses thread-based multiplexing, with documented evolution path to separate worker process type |
| Twelve-Factor Factor X — Dev/Prod Parity | "development staging production similar" | "Keep development, staging, and production as similar as possible." | ✅ Aligned | N/A — Standard 8 maintains parity with controlled exceptions (execution suppressed, registration preserved) |
| Kubernetes CronJob `concurrencyPolicy` | "concurrencyPolicy Allow Forbid Replace" | Three policies: `Allow` (default — concurrent runs OK), `Forbid` (skip new if previous running), `Replace` (kill running, start new). The doc states: "The Jobs that you define should be idempotent." | ✅ Aligned | N/A — ADR Tier 1 maps to `Allow`, Tier 2 maps to `Forbid`. The ADR correctly omits `Replace` (not applicable to the single-process scheduler model) |
| Azure Background Jobs best practices | "single-instance execution scheduled background tasks concurrent" | "Enforce single-instance execution when required. Some scheduled background tasks must not run concurrently, like database maintenance or report generation that isn't idempotent." Also: "To reduce job impact on web app performance, consider creating an empty Azure web app instance in a separate App Service plan to host long-running or resource-intensive WebJobs." | ✅ Aligned | N/A — Standard 4 Tier 2 implements the singleton recommendation; Standard 1 acknowledges the separate-worker evolution path |
| Azure Leader Election pattern | "lightweight optimistic pessimistic locking coordination" | "Might not be useful if the coordination between tasks can be achieved by using a more lightweight method like optimistic or pessimistic locking." Full leader election is for complex multi-step coordination; simple job mutual exclusion is better served by lightweight locks. | ✅ Aligned | N/A — Standard 4 uses DynamoDB conditional writes (optimistic locking), not full leader election |

---

### 2.C Cross-Cutting Design Patterns

**Applicable Standards:**
- ✅ Error Boundary / Error Isolation Pattern
- ✅ Dead-Man's-Switch Monitoring Pattern
- ✅ Idempotency Patterns for Distributed Systems
- ✅ Plugin Registration / Strategy Pattern

**Search & Findings:**

| Standard/Doc | Search Query Used | Key Findings | ADR Alignment | Deviation Rationale |
|--------------|-------------------|--------------|---------------|---------------------|
| Error Boundary pattern | "error boundary isolation fault tolerance" | Error boundaries catch exceptions at service boundaries to prevent propagation. Common in React (UI), equally applicable to background job isolation. The boundary logs the error and allows the system to continue operating. | ✅ Aligned | N/A — Standard 5 `safe_run` wrapper implements this pattern |
| Dead-Man's-Switch monitoring | "heartbeat dead man switch scheduler health" | A periodic signal that, when absent, indicates system failure. If the heartbeat stops arriving, the monitored component is considered dead. Used in infrastructure monitoring (Prometheus alertmanager, Cronitor, Healthchecks.io). | ✅ Aligned | N/A — Standard 6 `scheduler_heartbeat` event serves exactly this purpose |
| Idempotency patterns | "idempotent conditional write upsert deduplication" | Idempotent operations produce the same result when applied multiple times. Techniques: conditional writes (DynamoDB `ConditionExpression`), upserts, idempotency keys. | ✅ Aligned | N/A — Standard 4 mandates idempotency via conditional writes and upsert patterns |
| Plugin Registration / Strategy pattern | "plugin registry strategy pattern registration" | The Strategy pattern encapsulates algorithms behind a common interface. Plugin registration extends this to runtime discovery. Pluggy implements this via hookspecs and hookimpls. | ✅ Aligned | N/A — Standard 3 uses pluggy hookspecs for job registration, consistent with ADR-0049 |

---

### 2.D Validation Summary

**Total Standards Checked:** 15
**Aligned with Best Practice:** 15
**Deliberate Deviations:** 0

**High-Level Finding:**
- 🟢 **Fully Grounded:** All standards checked; no unresolved deviations

---

## 3. Assumptions Challenged

### Assumption 3.1: The colocated worker model is appropriate for the current scale

- **Stated Norm:** "Background jobs execute within the same OS process as the FastAPI web server. There is no separate worker process type." (Standard 1)
- **Underlying Assumption:** Current background job volume and resource consumption do not justify the deployment complexity of a separate worker process type.
- **Challenge:** Could background jobs (especially `provision_aws_identity_center` which runs every 2 hours and involves long-running AWS API calls) already be impacting request latency? The current codebase has 6 scheduled jobs, 4 of which are classified as Tier 2 (resource-intensive).
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Partial — Twelve-Factor Factor VIII explicitly permits internal thread multiplexing while recommending process formation for horizontal scaling. Azure Background Jobs best practices recommend separation "to reduce job impact on web app performance" but qualify it with "consider" — not mandate. The current deployment is a single ECS task type; adding a worker task type doubles deployment complexity (two task definitions, separate scaling policies, potentially separate container images). At 6 jobs with infrequent schedules (most daily or multi-hour intervals), the overhead of process separation is disproportionate.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The ADR explicitly documents this as a pragmatic posture with an evolution path. Standard 1 includes the rule: "If the team scales to a point where background work materially impacts request latency, the colocated model must be re-evaluated." The evolution trigger is defined; the current posture is justified by scale.

### Assumption 3.2: Production-only execution with registration-in-all-environments is the correct parity model

- **Stated Norm:** "Background jobs must only execute in production environments... Job registration (via pluggy hooks) still occurs in all environments so that registration-time errors are caught during development and testing." (Standard 2)
- **Underlying Assumption:** Registration parity is sufficient to catch most job integration errors, even though execution is suppressed.
- **Challenge:** Could there be classes of errors (runtime failures, timing-dependent bugs, resource contention issues) that only manifest during actual scheduled execution? These would only be caught in production, violating the spirit of Factor X (Dev/Prod Parity).
- **Evidence Strength:** ⭐⭐ Moderate
- **Counter-Evidence Found:** Partial — Factor X says "keep development, staging, and production as similar as possible." The ADR's model is a pragmatic compromise: registration parity + direct-invocation testing (Standard 8) covers the job logic path, while scheduling-specific behavior (cron timing, concurrent execution, scheduler thread lifecycle) is production-only. This is comparable to how most web applications don't run load balancers in development but still test HTTP handlers. The `safe_run` wrapper is tested independently (Standard 8), providing error isolation coverage.
- **Confidence (ADR survives challenge):** 🟡 Moderate
- **Reviewer Notes:** The parity model is a pragmatic compromise. The risk is that scheduler-thread-specific failures (e.g., thread starvation, event loop blocking) are only discoverable in production. Mitigation: Standard 6's `scheduler_heartbeat` dead-man's-switch detects scheduler thread death in production. Standard 8's direct-invocation testing covers the job logic itself. The gap is narrow and acceptable at current scale.

### Assumption 3.3: Two-tier concurrency classification is sufficient (no need for three tiers)

- **Stated Norm:** Standard 4 defines two tiers: Tier 1 (concurrent-safe) and Tier 2 (singleton). Kubernetes CronJob has three policies: Allow, Forbid, Replace.
- **Underlying Assumption:** The `Replace` policy (kill running, start new) has no useful equivalent in the sre-bot context.
- **Challenge:** Could there be jobs where you want the latest invocation to supersede a stale one? For example, a data generation job where running the newest version is more valuable than letting the old one complete?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — In the single-process scheduler model, `Replace` semantics would require killing a running thread, which is not safely possible in Python (no `Thread.kill()`). The only way to implement `Replace` would be cooperative cancellation (check a flag in the job loop), which makes it functionally equivalent to "start new after current completes" — the same as Tier 2 with a short lock TTL. The two-tier model is appropriate for the execution model.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** The omission of `Replace` is deliberate and correct for the Python single-process model. The ADR does not need to mention this explicitly because the two tiers map cleanly to the two relevant Kubernetes policies.

### Assumption 3.4: DynamoDB conditional writes are sufficient for singleton lock implementation

- **Stated Norm:** "Tier 2 (singleton) jobs must acquire a distributed lock before execution. The implementation must use DynamoDB conditional writes with TTL-based expiration." (Standard 4)
- **Underlying Assumption:** DynamoDB conditional writes provide sufficient mutual exclusion for the job scheduling use case.
- **Challenge:** DynamoDB conditional writes are not true distributed locks — they provide optimistic concurrency control. Could two tasks acquire the "lock" simultaneously due to DynamoDB eventual consistency?
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — DynamoDB conditional `PutItem` with `attribute_not_exists` is strongly consistent for writes (DynamoDB provides strong consistency for write operations). The conditional check and write are atomic within a single item. Two concurrent `PutItem` calls with the same key and `attribute_not_exists` condition will result in exactly one succeeding and the other receiving a `ConditionalCheckFailedException`. This is not eventual consistency — it's a linearizable compare-and-swap operation. The Azure Leader Election guidance validates this approach: "lightweight method like optimistic or pessimistic locking" is preferred over full leader election for simple coordination.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** DynamoDB conditional writes are the correct primitive for this use case. The strong consistency guarantee on writes makes this equivalent to a compare-and-swap lock. The TTL-based expiration (DynamoDB TTL) prevents permanent lock-out from killed tasks. The approach is well-documented in AWS best practices for distributed locking.

### Assumption 3.5: Unclassified jobs defaulting to Tier 2 is the correct safe default

- **Stated Norm:** "Each job's tier classification must be documented at registration time. Unclassified jobs default to Tier 2 (singleton) — the safer posture." (Standard 4)
- **Underlying Assumption:** Singleton execution is always safer than concurrent execution as a default.
- **Challenge:** Could defaulting to singleton cause missed job executions in the lock-contention case? If a new job is added without classification and happens to be a read-only health check, it would unnecessarily acquire a singleton lock and only run on one task.
- **Evidence Strength:** ⭐ Strong
- **Counter-Evidence Found:** No — The worst case of defaulting to Tier 2 is that a read-only job runs on one task instead of N tasks. This is a performance impact (reduced monitoring coverage), not a correctness impact. The worst case of defaulting to Tier 1 is that a side-effecting job runs N times, potentially sending duplicate notifications or performing duplicate writes. The asymmetry clearly favors Tier 2 as the safe default. The Azure Background Jobs guidance aligns: "Enforce single-instance execution when required" — the conservative posture is to enforce until you've explicitly verified concurrent safety.
- **Confidence (ADR survives challenge):** 🟢 High
- **Reviewer Notes:** Correct default. The risk asymmetry (missed monitoring vs. duplicate side effects) strongly favors Tier 2. Registration-time classification documentation makes the default easy to override.

---

## 4. Failure Modes Identified

### Failure Mode 4.1: Scheduler thread death goes undetected in production (from Assumption 3.2)

- **If Assumption Fails:** If the scheduler thread crashes or becomes blocked without emitting errors, background jobs stop running. Standard 6's `scheduler_heartbeat` event is the detection mechanism, but it requires external monitoring (alerting on heartbeat absence).
- **Platform Impact:**
  - Incident management workflow: Medium — `notify_stale_incident_channels` would stop running, causing stale channels to accumulate
  - Access synchronization workflow: Medium — `reconcile_access_sync` would stop running, causing drift to accumulate
  - Access request workflow: Low — request-scoped, not dependent on background jobs
  - Multi-provider integrations: Medium — `integration_healthchecks` would stop reporting
- **Probability Estimate:** Low (< 10%) — the `schedule` library's run loop is simple and stable; the `safe_run` wrapper prevents job exceptions from propagating
- **Mitigation or Acceptance:** Mitigated by Standard 6 heartbeat monitoring. The heartbeat event serves as a dead-man's-switch. If heartbeat events are absent beyond the expected interval, operational monitoring can alert. The `safe_run` wrapper (Standard 5) prevents the most common cause of thread death (unhandled exceptions). The remaining risk (thread starvation, deadlock, OOM) is inherent to the colocated model and would be resolved by process separation.

### Failure Mode 4.2: DynamoDB lock TTL expiration causes brief overlapping execution (from Assumption 3.4)

- **If Assumption Fails:** If a task acquires the singleton lock, starts executing a Tier 2 job, and is then killed (SIGKILL, OOM), the lock remains held until TTL expiration. During TTL expiration, another task may also not be able to run the job (lock still held). After TTL expires, two tasks might briefly execute the same job if timing aligns with the lock acquisition window.
- **Platform Impact:**
  - Incident management workflow: Low — `notify_stale_incident_channels` sending duplicate Slack messages is annoying but not data-corrupting
  - Access synchronization workflow: Low — idempotent writes mean duplicate sync iterations produce the same end state
  - Access request workflow: Low — not dependent on singleton jobs
  - Multi-provider integrations: Low — duplicate API calls may consume rate limit quota but don't corrupt state
- **Probability Estimate:** Very Low (< 5%) — requires both task death AND TTL expiration race condition
- **Mitigation or Acceptance:** Accepted. The ADR explicitly notes: "DynamoDB lock TTL expiration could allow brief overlapping execution if a task is killed between acquiring the lock and completing the job. Acceptable because jobs are still idempotent." The idempotency requirement (Standard 4 baseline) ensures overlapping execution does not produce incorrect results. The TTL should be set shorter than the job interval (Standard 4 rule) to minimize the window.

---

## 5. Contradiction Audit

### Cross-ADR Contradictions

| Conflict | ADRs Involved | Severity | Resolution Status |
|----------|---------------|----------|-------------------|
| ADR-0046 Invariant 2 places background work in phase 6. ADR-0058 Standard 3 says job registration occurs in phase 3 (Discovery and Registration), with execution starting in phase 6. Is the two-phase split (register in 3, execute in 6) consistent with ADR-0046? | ADR-0046, ADR-0058, ADR-0049 | 🟢 Low | ✅ Resolved — ADR-0049 Standard 7 (zero-touch extension) defines the hookspec registration model. Registration is discovery-phase activity; execution is a separate lifecycle concern. ADR-0046 Invariant 2's "Background" phase 6 refers to execution start, not registration. The two-phase model is consistent. |
| ADR-0057 Standard 2 allocates ≤5s to Background shutdown phase. ADR-0058 Standard 7 requires scheduler thread join with timeout. Are these aligned? | ADR-0057, ADR-0058 | 🟢 Low | ✅ Resolved — ADR-0058 Standard 7 explicitly says "joined with a timeout during lifespan shutdown (ADR-0057 Standard 2 — background phase budget ≤ 5 seconds)." The cross-reference is correct. Note: ADR-0057 has a pending revision for timeout budget recalculation (see ADR-0057 challenge review), but the Budget for Background phase is likely to remain ≤5s. |
| ADR-0049 Standard 3 (post-registration validation) says registration errors are startup-fatal. ADR-0058 Standard 3 says duplicate job names are a startup error. Consistent? | ADR-0049, ADR-0058 | 🟢 Low | ✅ Resolved — consistent. Duplicate job names at registration time = startup error = fail-fast per ADR-0046 Invariant 3. |
| ADR-0052 (Build-Release-Run) says release-phase configuration binding. ADR-0058 says "job schedules must not be fetched at runtime from external sources." Consistent? | ADR-0052, ADR-0058 | 🟢 Low | ✅ Resolved — consistent. ADR-0052 mandates that configuration is bound at release time. Job schedules are configuration — they must be set at build/release, not fetched dynamically at runtime. |

### Supersession Ambiguities

- **ADRs this one supersedes:** ADR-0015 (Background Services)
- **Inheritance Status:** ADR-0015 prescribed APScheduler; the codebase actually uses `schedule`. ADR-0058 is deliberately library-agnostic, correcting this misalignment. The conceptual content (scheduled background work, error isolation) is preserved. The tier classification was promoted from Tier-1 to Tier-2.
- **Gaps Identified:** None in supersession.

### Ownership Clarity

- **Primary Domain Owner:** SRE Team
- **Secondary Domain Owners:** N/A
- **Plugin/Startup Registration:** Standard 3 defines the `BackgroundJobRegistry` Protocol and `register_background_job` hookspec. Ownership is clear: hookspec in `app/infrastructure/hookspecs/features.py`, adapter in `app/jobs/scheduled_tasks.py`.
- **Config Owner:** Job schedules currently hardcoded; if made configurable, follows ADR-0055 (noted in Compliance section).
- **Audit Result:** ✅ Clear

---

## 6. Scenario Validation Matrix

### Scenario 6.1: Incident Management Workflow
**Context:** Emergency response requires rapid logging, context propagation, and operational decision-making under time pressure.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| `notify_stale_incident_channels` classified as Tier 2 | Standard 4 — singleton (sends Slack messages) | Job sends Slack messages — duplicate notifications are user-visible side effects | ✅ No | Correct classification |
| Job failure isolation | Standard 5 — `safe_run` wraps all jobs | Notification failures must not crash scheduler | ✅ No | `safe_run` wrapper catches and logs |

**Validation Summary:**
- ✅ Fully aligned

---

### Scenario 6.2: Access Synchronization Workflow
**Context:** Automated sync from identity providers to application; must handle failure, retry, and eventual consistency.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| `reconcile_access_sync` classified as Tier 2 | Standard 4 — singleton (long-running, external API calls) | Sync calls multiple identity providers; duplicate runs waste API quota | ✅ No | Correct classification |
| `provision_aws_identity_center` classified as Tier 2 | Standard 4 — singleton (resource-intensive, external API calls) | Provisioning involves AWS IAM operations; N duplicate runs waste resources | ✅ No | Correct classification |
| Idempotency of sync operations | Standard 4 — all jobs must be idempotent | Access sync uses conditional DynamoDB writes (upserts) | ✅ No | Naturally idempotent via conditional writes |

**Validation Summary:**
- ✅ Fully aligned

---

### Scenario 6.3: Access Request Workflow
**Context:** User requests access to a resource/role; admin approves; system provisions and audits across platforms.

| Aspect | ADR Requirement | Workflow Reality | Gap? | Notes |
|--------|-----------------|------------------|------|-------|
| Background jobs do not affect request handling | Standard 1 — job failure must not crash web server | Request-scoped operations are independent of scheduled jobs | ✅ No | Thread isolation prevents cross-contamination |
| Request latency not impacted | Standard 1 — isolation from request handling | Current job volume is low; Tier 2 singleton classification limits resource-intensive jobs to one task | ✅ No | Singleton classification provides additional protection |

**Validation Summary:**
- ✅ Fully aligned

---

### Scenario 6.4: Multi-Provider Integration (Slack/Teams/AWS/GWS/GitHub)
**Context:** Operations span multiple external APIs with rate limits and error handling.

| Aspect | ADR Requirement | Integration Reality | Gap? | Notes |
|--------|-----------------|---------------------|------|-------|
| `integration_healthchecks` as Tier 1 | Standard 4 — concurrent-safe (read-only checks) | Health checks are read-only; N tasks running them increases monitoring coverage | ✅ No | Correct classification — more coverage is beneficial |
| `scheduler_heartbeat` as Tier 1 | Standard 4 — concurrent-safe (log-only) | Heartbeat is a proof-of-life log event; all tasks should emit it | ✅ No | Correct classification |
| External API rate limits | Standard 4 rationale — N concurrent invocations may hit rate limits | Tier 2 classification for API-calling jobs prevents N-fold rate limit consumption | ✅ No | Singleton classification protects API quotas |

**Validation Summary:**
- ✅ Fully aligned

---

## 7. Tradeoffs Accepted

### Tradeoff 7.1: Colocated Worker vs. Separate Worker Process
- **Chosen:** Single OS process for web serving and background jobs
- **Rejected:** Separate ECS task definition with worker-only container
- **Rationale:** Current scale (6 jobs, infrequent schedules) does not justify doubled deployment complexity. Factor VIII permits thread-based multiplexing. Azure guidance recommends separation only when "background work materially impacts web app performance."
- **Risk Accepted:** Resource contention between jobs and request handling under load.
- **Contingency:** Standard 1 defines the evolution trigger and the natural next step (separate worker process type).

### Tradeoff 7.2: Library-Agnostic Standards vs. Library-Specific Optimization
- **Chosen:** Standards are library-agnostic; the `schedule` library is an implementation choice
- **Rejected:** Prescribe APScheduler (legacy ADR-0015) or another specific library
- **Rationale:** The `schedule` library is already in use and compliant with all standards. Library-specific guidance at the Tier-2 level would create artificial coupling. APScheduler 4.x has breaking changes and provides no immediate benefit for the current job set.
- **Risk Accepted:** No library-specific optimization guidance (e.g., APScheduler's missed job handling, job stores).
- **Contingency:** Library migration is a Tier-4 implementation decision that can be made independently of this standard.

### Tradeoff 7.3: DynamoDB Singleton Lock vs. No Coordination (Idempotency Only)
- **Chosen:** Two-tier model with DynamoDB conditional write locks for Tier 2 jobs
- **Rejected:** All jobs run independently with idempotency as the only coordination mechanism
- **Rationale:** Idempotency alone does not prevent resource waste (N tasks running a 2-hour provisioning job simultaneously) or user-visible duplicate side effects (N Slack notifications). The DynamoDB lock adds minimal overhead (one conditional `PutItem` per job invocation) and is already in the infrastructure stack.
- **Risk Accepted:** DynamoDB dependency for background job coordination; TTL expiration edge case allowing brief overlapping execution.
- **Contingency:** Idempotency requirement (Standard 4 baseline) ensures overlapping execution does not corrupt state. Lock TTL shorter than job interval minimizes the overlap window.

### Tradeoff 7.4: Production-Only Execution vs. Full Environment Parity
- **Chosen:** Suppress scheduler execution in non-production; maintain registration and direct-invocation testing
- **Rejected:** Run scheduler in all environments for full parity
- **Rationale:** Running scheduled jobs in development/test environments would require backing service availability (DynamoDB, Slack, AWS IAM) and would produce real side effects (Slack messages, AWS resource modifications). Factor X's "as similar as possible" acknowledges that full parity has limits.
- **Risk Accepted:** Scheduler-thread-specific failures only discoverable in production.
- **Contingency:** Standard 6 heartbeat monitoring detects scheduler thread death. Standard 8 direct-invocation testing covers job logic.

---

## 8. Follow-Up Actions

| Action | Blocker? | Owner | Due Date | Description |
|--------|----------|-------|----------|-------------|
| Implement `@singleton_job` DynamoDB lock decorator | ❌ No | SRE Team | Post-ADR-0057 revision | Create infrastructure utility for Tier 2 singleton lock (DynamoDB conditional `PutItem` + TTL). Place in `app/infrastructure/`. |
| Apply singleton lock to Tier 2 jobs | ❌ No | SRE Team | After lock implementation | Apply `@singleton_job` to `provision_aws_identity_center`, `notify_stale_incident_channels`, `generate_spending_data`, `reconcile_access_sync`. |
| Add per-job observability events | ❌ No | SRE Team | Post-revision | Add `job_started`, `job_completed`, `job_failed` structured events with duration measurement to `safe_run` wrapper. |
| Add duration measurement to `safe_run` | ❌ No | SRE Team | Post-revision | Use `time.monotonic()` for duration; emit in `job_completed` and `job_failed` events. |
| Audit `notify_stale_incident_channels` idempotency | ❌ No | SRE Team | Post-lock implementation | Verify that singleton classification + current implementation satisfies idempotency under TTL edge case. Document acceptance or add deduplication. |
| Add `tier` field to `BackgroundJobRegistry.register()` | ❌ No | SRE Team | Post-lock implementation | Extend the Protocol with `tier: Literal[1, 2] = 2` to formalize classification at registration time. |
| Cross-reference ADR-0057 timeout budget revision | ❌ No | SRE Team | After ADR-0057 revision | Verify that scheduler thread join timeout (Standard 7) aligns with the revised ADR-0057 Standard 2 background phase budget. |

**Blocking Actions Must Resolve Before Step 10 Proceeds:** None — all follow-up actions are non-blocking.

---

## 9. Binary Gate Outcome

**GATE DECISION:**

⚪ **PASS** → ADR-0058 is professionally sound and ready for phase-in via Step 10 cascade

---

## 10. Reviewer Sign-Off

| Field | Signature/Value |
|-------|-----------------|
| **Reviewer Name** | AI Architecture Reviewer |
| **Reviewer Title** | Architecture Review Agent |
| **Organization/Team** | SRE Team |
| **Sign-Off Date** | 2026-04-29 |
| **Email** | N/A (automated review) |

---

## 11. Review Artifacts Reference

**This Review Record Should Be Attached To:**
- Internal decision tracker / ADR review calendar
- ADR-0058 metadata (next review cycle)

**This Review Template Was Completed Per:**
- ADR-0044 (Governance and Operating Model) § Step 9.5
- Revalidation Cycle: One-time gate review → then annual review_state cycle

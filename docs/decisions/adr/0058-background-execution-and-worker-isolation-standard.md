---
adr_id: ADR-0058
title: "Background Execution and Worker Isolation Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Runtime and Lifecycle
secondary_domains:
 - Package and Plugin Architecture
 - Observability and Operations
 - Delivery and Environment Parity
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
 - ADR-0049
 - ADR-0052
 - ADR-0054
impacts: []
supersedes:
 - ADR-0015
superseded_by: []
review_state: current
related_records:
 - ADR-0053
 - ADR-0055
 - ADR-0057
related_packages:
 - app/jobs
 - app/server
---

# Background Execution and Worker Isolation Standard

## Context

- Problem statement: ADR-0015 (Background Services) was classified as Tier-1 Principle but contained implementation-level code examples (APScheduler usage, scheduler selection guidance, job registration patterns) - a tier violation per ADR-0044. It prescribed APScheduler as the scheduling library, but the codebase actually uses the `schedule` library with a daemon thread. ADR-0015 also lacked standards for horizontal scaling (multiple ECS tasks running the same jobs), job idempotency, worker-request isolation, and the relationship between background jobs and the plugin registration system (ADR-0049). ADR-0046 Invariant 2 placed background work in phase 6 of the lifecycle and ADR-0046 Invariant 4 requires background work to stop first during shutdown - but the implementation standards were delegated to this record.
- Business/operational drivers:
 - Codify the background execution model for the current single-process ECS Fargate deployment where web serving and background jobs coexist in one process.
 - Establish job registration standards that integrate with the pluggy-based plugin system (ADR-0049).
 - Define idempotency and horizontal scaling requirements for jobs that run on multiple ECS tasks simultaneously.
 - Separate background execution concerns from the request-handling event loop to prevent mutual interference.
 - Standardize structured observability for background job execution to enable operational monitoring.
 - Align development and production parity for background execution (ADR-0054).
- Constraints:
 - Background work starts during lifespan phase 6, production only (ADR-0046 Invariant 2).
 - Background work stops first during shutdown (ADR-0046 Invariant 4, ADR-0057 Standard 2).
 - Feature packages register background jobs through pluggy hookspecs (ADR-0049 Standard 7 - zero-touch extension).
 - The application runs as a single-process ECS Fargate task with no separate worker process type. Background jobs share the same OS process as the FastAPI web server.
 - Multiple ECS tasks may be running simultaneously, each executing the same scheduled jobs independently.
 - Release-phase configuration binding applies (ADR-0052) - job schedules must not be fetched at runtime from external sources.
- Non-goals:
 - This record does not prescribe a specific scheduling library. Library selection is an implementation detail; the standards are library-agnostic.
 - This record does not define one-off task execution (e.g., CLI commands, management scripts). Those are governed by separate concerns.
 - This record does not define event-driven async processing (e.g., SQS consumers, webhook handlers). Those are transport-level concerns governed by ADR-0078 (Queueing and Message-Broker Architecture Standard, Wave 4). ADR-0059 covers interaction provider patterns, not queueing infrastructure.

## Decision

- Chosen approach: Establish a Tier-2 standard that defines the background execution model, job registration contract, isolation requirements, idempotency rules, observability expectations, and horizontal scaling posture.
- Why this approach: ADR-0046 Invariant 2 establishes background work as a lifecycle phase, and ADR-0049 establishes the plugin registration model, but neither defines how background jobs should behave at runtime. This record fills that gap with enforceable standards that apply regardless of which scheduling library is used.

### Standard 1: Colocated Worker Model

Background jobs execute within the same OS process as the FastAPI web server. There is no separate worker process type. This is a pragmatic posture for the current deployment model (single ECS task definition, single container).

**Consequences of colocation:**
- Background jobs share the process's memory, CPU, and network resources with request handling.
- A runaway background job can starve request handling of resources.
- Process termination (SIGTERM/SIGKILL) affects both web serving and background execution simultaneously.

**Rules:**
- Background job threads must not block the asyncio event loop. Jobs that perform blocking I/O must run in dedicated threads (daemon or non-daemon), not on the FastAPI event loop.
- Background job execution must be isolated from request handling: a job failure must not crash the web server process or corrupt request-scoped state.
- If the team scales to a point where background work materially impacts request latency, the colocated model must be re-evaluated. A separate worker process type (Factor VIII - Concurrency) is the natural evolution, but premature separation adds deployment complexity without proportionate benefit at current scale.

### Standard 2: Production-Only Execution

Background jobs must only execute in production environments. The production guard is evaluated once at startup during lifecycle phase 6.

**Rules:**
- The production check must use the application's canonical environment indicator (currently `PREFIX == ""`), not ad-hoc environment variable checks within individual jobs.
- In non-production environments, the scheduler thread must not be started. The lifespan must log a structured event (`background_tasks_skipped`) indicating that background execution was suppressed and the reason.
- Job registration (via pluggy hooks) still occurs in all environments so that registration-time errors are caught during development and testing (ADR-0049 Standard 3 - post-registration validation). Only execution is suppressed.

### Standard 3: Job Registration via Plugin Hooks

Feature packages register background jobs through the `register_background_job` pluggy hookspec defined in `app/infrastructure/hookspecs/features.py`. This integrates background job registration with the plugin lifecycle (ADR-0049 Standard 7 - zero-touch extension).

**Registration contract:**
- The hookspec provides a `BackgroundJobRegistry` Protocol to each feature plugin.
- Plugins call `registry.register(job_name=..., schedule=..., job=...)` to register their jobs.
- The registry adapter translates the Protocol call into the scheduling library's native registration API.
- Job registration occurs during lifespan phase 3 (Discovery and Registration), consistent with ADR-0049. Job execution begins in phase 6 (Background).

**Rules:**
- Infrastructure-owned jobs (heartbeat, integration health checks) are registered directly in the job initialization module, not through plugin hooks. Plugin hooks are for feature package jobs.
- All registered jobs - both infrastructure and feature - must be wrapped in the `safe_run` error boundary (Standard 5) before being handed to the scheduler.
- Job names must be unique across all registrations. Duplicate job names must be detected at registration time and treated as a startup error (ADR-0049 Standard 3).

### Standard 4: Job Concurrency Classification and Horizontal Scaling

Multiple ECS tasks may be running simultaneously. Each task runs the same scheduler, but not all jobs should execute on every task. Jobs are classified into two concurrency tiers based on their side-effect profile and resource impact.

This classification follows the Kubernetes CronJob `concurrencyPolicy` model (Allow vs. Forbid) and Azure Well-Architected guidance: "Enforce single-instance execution when required. Some scheduled background tasks must not run concurrently, like database maintenance or report generation that isn't idempotent" (Microsoft, Best Practices for Background Jobs, 2026).

**Concurrency tiers:**

| Tier | Name | Behavior | Criteria |
|------|------|----------|----------|
| 1 | **Concurrent-safe** | Runs on all N tasks independently | Read-only, log-only, or writes are naturally idempotent (conditional/upsert). Low resource cost. Equivalent to Kubernetes `concurrencyPolicy: Allow`. |
| 2 | **Singleton** | Runs on exactly one task at a time | Sends external notifications, provisions resources, performs long-running I/O, or consumes significant CPU/memory/network. Equivalent to Kubernetes `concurrencyPolicy: Forbid`. |

**Rules:**
- All scheduled jobs must be idempotent regardless of tier. Running the same job simultaneously on N ECS tasks must produce the same end state as running it once. This aligns with Twelve-Factor Factor IX: "all jobs are reentrant, which typically is achieved by wrapping the results in a transaction, or making the operation idempotent."
- **Tier 1 (concurrent-safe) jobs** require no coordination beyond idempotent design. Conditional writes, atomic operations, or upsert patterns are sufficient.
- **Tier 2 (singleton) jobs** must acquire a distributed lock before execution. The implementation must use DynamoDB conditional writes with TTL-based expiration. The lock TTL must be shorter than the job interval to prevent permanent lock-out from a killed task. A task that fails to acquire the lock must skip the job run silently (log at debug level) - this is normal operation, not an error.
- The singleton lock pattern is lightweight - a single DynamoDB conditional `PutItem` per job invocation, not a heavyweight coordination system. This aligns with Azure Leader Election guidance: "might not be useful if the coordination between tasks can be achieved by using a more lightweight method like optimistic or pessimistic locking."
- Each job's tier classification must be documented at registration time. Unclassified jobs default to Tier 2 (singleton) - the safer posture.
- The singleton lock implementation must be provided as an infrastructure utility (decorator or wrapper), not reimplemented per job.

**Rationale for two tiers instead of "all idempotent, no coordination":**
- Resource efficiency: N tasks running a 2-hour AWS Identity Center provisioning job simultaneously wastes N-1 copies of CPU, memory, and API quota. The tasks not running the singleton job remain available for request handling, improving overall responsiveness.
- External API quotas: Some external APIs (Slack, AWS) have rate limits. N concurrent invocations of the same notification job may hit rate limits or produce duplicate user-visible messages.
- Twelve-Factor does not prohibit coordination - it requires idempotency as a baseline. Kubernetes, Azure, and AWS all provide first-class singleton scheduling primitives, recognizing that idempotency alone is necessary but not always sufficient.

**Current classification:**
- `scheduler_heartbeat`: **Tier 1** - Concurrent-safe (log-only).
- `integration_healthchecks`: **Tier 1** - Concurrent-safe (read-only checks).
- `provision_aws_identity_center`: **Tier 2** - Singleton (long-running, external API calls, resource-intensive).
- `notify_stale_incident_channels`: **Tier 2** - Singleton (sends Slack messages - duplicate notifications are a user-visible side effect).
- `generate_spending_data`: **Tier 2** - Singleton (writes spending records, resource-intensive computation).
- `reconcile_access_sync`: **Tier 2** - Singleton (long-running reconciliation, external API calls).

### Standard 5: Job Error Isolation

Background job failures must not propagate to the web server process or to other jobs.

**Rules:**
- Every job must be wrapped in an error boundary (`safe_run` or equivalent) that catches all exceptions, logs them with structured context, and returns normally.
- The error boundary must log: `job_name`, `error` (exception message), `module`, `function`, `duration_seconds`.
- The error boundary must not swallow exceptions silently - structured logging is the minimum acceptable error handling.
- A job failure must not stop the scheduler. The scheduler must continue executing subsequent jobs on their normal schedule.
- A job failure must not trigger process shutdown. Background job errors are operational concerns, not startup-fatal errors (contrast with ADR-0049 Standard 6 where startup warmup failures are fatal).

### Standard 6: Job Observability

Background job execution must emit structured log events that enable operational monitoring:

| Event | Required Fields | Purpose |
|-------|----------------|---------|
| `background_tasks_initialized` | `job_count`, `environment` | Marks scheduler start with registered job count |
| `background_tasks_skipped` | `reason` | Marks suppressed execution in non-production |
| `job_started` | `job_name`, `module` | Marks individual job execution start |
| `job_completed` | `job_name`, `duration_seconds` | Marks successful job completion |
| `job_failed` | `job_name`, `error`, `module`, `duration_seconds` | Marks job failure with error context |
| `scheduler_heartbeat` | `time` | Periodic proof-of-life for the scheduler thread |

**Rules:**
- Job observability events must use the same structured logging configuration as request events (ADR-0054 compliance).
- Job events must not log sensitive data (credentials, tokens, PII) even in error contexts.
- The `scheduler_heartbeat` event serves as a dead-man's-switch for monitoring - absence of heartbeat events beyond the expected interval indicates scheduler thread failure.
- Job duration measurement must use monotonic time (`time.monotonic()` or equivalent), not wall clock time.

### Standard 7: Scheduler Thread Lifecycle

The scheduler runs in a dedicated thread with cooperative shutdown signaling.

**Rules:**
- The scheduler thread must use `threading.Event` for shutdown signaling. The lifespan shutdown code sets the event; the scheduler thread checks `event.is_set()` in its run loop.
- The scheduler thread must check the shutdown event between job executions, not during job execution. A running job is allowed to complete before the thread exits.
- The scheduler thread's run loop interval (sleep between `run_pending()` checks) must be <= 5 seconds to ensure timely shutdown response.
- The scheduler thread must be joined with a timeout during lifespan shutdown (ADR-0057 Standard 2 - background phase budget <= 5 seconds).
- If the scheduler thread does not terminate within the join timeout, the lifespan must log a warning and proceed to the next shutdown phase.
- The `cease_continuous_run` event (or equivalent) returned by the scheduler initialization must be stored in `app.state` for access during shutdown.

### Standard 8: Development and Test Parity

Background execution must maintain parity between development/test and production environments per ADR-0054, with controlled exceptions:

| Concern | Production | Development/Test |
|---------|------------|------------------|
| Job registration | Via plugin hooks + direct | Via plugin hooks + direct (same code path) |
| Job execution | Active (scheduler thread running) | Suppressed (thread not started) |
| Job testing | Covered by scheduled execution | Covered by direct invocation in test suite |
| Error boundary | `safe_run` wrapper active | `safe_run` wrapper active (same code path) |
| Observability events | Emitted to stdout | Emitted to stdout (same code path) |

**Rules:**
- Job functions must be testable by direct invocation without the scheduler. Tests call the job function directly and assert on its behavior and side effects.
- The `safe_run` error boundary must be testable independently - tests verify that it catches exceptions and logs structured events without propagating.
- Job registration code must execute in test environments to catch registration errors (ADR-0049 Standard 3). Only the scheduler thread start is suppressed.
- Integration tests for background jobs should use explicit invocation, not time-based scheduling, to avoid flaky timing-dependent tests.

## Alternatives Considered

1. Separate worker process type (ECS task definition with worker-only container):
 - Pros: Full resource isolation between web serving and background work. Independent scaling of workers. Aligns with Factor VIII (concurrency via process model).
 - Cons: Doubles deployment complexity (two task definitions, two container images or entry points, separate scaling policies). Premature for current workload where background jobs consume minimal resources.
 - Why not chosen: The colocated model is appropriate for current scale. Standard 1 explicitly acknowledges this as a pragmatic posture with a documented evolution path.

2. Async background tasks via `asyncio.create_task()` on the FastAPI event loop:
 - Pros: No separate thread; natural integration with async request handlers.
 - Cons: Background tasks share the event loop with request handlers - a slow background task delays request processing. No natural scheduling primitive; requires custom or library-based scheduler. Error isolation is harder - unhandled exceptions in tasks can propagate to the event loop.
 - Why not chosen: The current codebase uses synchronous background jobs (database calls, HTTP requests to external APIs). Moving to async tasks would require rewriting all job implementations. The thread-based model provides better isolation for synchronous workloads.

3. Distributed job scheduling (e.g., Celery, AWS EventBridge + Lambda):
 - Pros: Built-in distributed coordination; exactly-once semantics; independent scaling.
 - Cons: Major infrastructure addition (message broker, worker fleet, monitoring). Significant operational overhead for the current job volume and team size.
 - Why not chosen: Current job volume (6 scheduled jobs) does not justify the infrastructure cost. Idempotent job design (Standard 4) handles the multi-task case adequately. If job volume grows significantly, this alternative should be re-evaluated.

4. APScheduler as prescribed by legacy ADR-0015:
 - Pros: Richer scheduling primitives (cron expressions, missed job handling, job stores). `AsyncIOScheduler` variant supports async jobs.
 - Cons: The codebase already uses the `schedule` library successfully. Migration to APScheduler provides no immediate benefit for the current job set. APScheduler 4.x has breaking API changes from 3.x.
 - Why not chosen: This standard is deliberately library-agnostic. The current `schedule` library implementation complies with all standards. Migration to APScheduler or any other library is an implementation decision, not an architectural one.

## Consequences

- Positive impacts:
 - Library-agnostic standards prevent prescriptive lock-in and allow the scheduling library to be replaced without amending this ADR.
 - Two-tier concurrency classification (Standard 4) enables horizontal scaling with appropriate coordination: concurrent-safe jobs run everywhere; singleton jobs use lightweight DynamoDB locks to prevent wasted work and duplicate side effects.
 - Plugin-based registration (Standard 3) integrates background jobs with the existing package extension model.
 - Error isolation (Standard 5) prevents background job failures from impacting request handling.
 - Observability standards (Standard 6) enable dead-man's-switch monitoring for scheduler health.
- Tradeoffs accepted:
 - Colocated model (Standard 1) means background jobs can impact request latency under resource contention. Accepted because current workload does not justify process separation. Singleton classification mitigates the worst case by ensuring resource-intensive jobs run on only one task.
 - Singleton lock adds a DynamoDB dependency for Tier 2 jobs. Accepted because DynamoDB is already in the infrastructure stack and the conditional write pattern is minimal overhead.
 - Production-only execution (Standard 2) means background job behavior is only fully exercised in production. Mitigated by direct-invocation testing (Standard 8).
- Risks introduced:
 - A non-idempotent job running on multiple tasks simultaneously could produce duplicate side effects if miscategorized as Tier 1. Standard 4 requires explicit tier classification and defaults unclassified jobs to Tier 2 (singleton) as the safer posture.
 - The scheduler thread running in the same process as the web server means an OS-level resource exhaustion (OOM, file descriptor limit) affects both. This is inherent to the colocated model.
 - Switching the production environment indicator (`PREFIX`) without updating the background execution guard would enable or disable background execution unintentionally.
 - DynamoDB lock TTL expiration could allow brief overlapping execution if a task is killed between acquiring the lock and completing the job. Acceptable because jobs are still idempotent.
- Mitigations:
 - Standard 4 compliance is reviewable: each job's concurrency tier and idempotency posture are documented in the standard itself.
 - Defaulting unclassified jobs to Tier 2 (singleton) prevents accidental concurrent execution of side-effecting jobs.
 - Standard 6 heartbeat monitoring detects scheduler thread death.
 - Standard 2 uses the canonical environment indicator, reducing the risk of environment-check drift.

## Compliance and Boundaries

- Package/infrastructure boundary impact: Standard 3 defines the contract between feature packages (which register jobs) and infrastructure (which provides the scheduler and registry). Feature packages depend on the `BackgroundJobRegistry` Protocol, not on the scheduling library.
- Type boundary impact: `BackgroundJobRegistry` is a `Protocol` (correct per ADR-0045 Principle 6 and ADR-0077 - behavior contracts use Protocol). The registry adapter is an infrastructure implementation detail.
- Startup/plugin registration impact: Job registration occurs during phase 3 via pluggy hooks (ADR-0049). Job execution starts in phase 6. This two-phase separation ensures registration errors are caught before execution begins.
- Settings partitioning impact: Job schedules are currently hardcoded in the initialization module. If job schedules become configurable, they must follow ADR-0055 (feature-owned settings for feature jobs, infrastructure settings for infrastructure jobs).

## Best-Practice Revalidation

- Revalidation date: 2026-04-29
- Sources rechecked:
 - Twelve-Factor App Factor IX - Disposability (https://12factor.net/disposability). Confirms: all jobs must be reentrant/idempotent; graceful shutdown returns current job to queue or allows completion.
 - Twelve-Factor App Factor VIII - Concurrency (https://12factor.net/concurrency). Confirms: scale out via the process model; internal multiplexing via threads is permitted but horizontal scaling via process formation is the preferred evolution.
 - Twelve-Factor App Factor X - Dev/Prod Parity (https://12factor.net/dev-prod-parity). Confirms: keep development, staging, and production as similar as possible.
 - FastAPI Background Tasks documentation (https://fastapi.tiangolo.com/tutorial/background-tasks/). Reviewed for applicability - FastAPI's `BackgroundTasks` are request-scoped (fire-and-forget after response), not scheduled recurring jobs. Not applicable to this standard's scope.
 - Python `schedule` library documentation (https://schedule.readthedocs.io/). Reviewed for thread safety, error handling, and shutdown patterns. Confirmed: `schedule` runs in a single thread; `run_pending()` + sleep loop is the intended execution model.
 - pluggy documentation (https://pluggy.readthedocs.io/en/stable/). Confirmed: hookspec-based registration with Protocol registries is a supported pattern.
 - Kubernetes CronJob documentation (https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/). Reviewed `concurrencyPolicy` field: Allow (default - concurrent runs OK), Forbid (skip new if previous running), Replace (kill running, start new). Confirms industry-standard recognition that not all jobs should run concurrently. "Jobs should be idempotent."
 - Microsoft Azure Architecture - Best Practices for Background Jobs (https://learn.microsoft.com/en-us/azure/architecture/best-practices/background-jobs). Confirms: "Enforce single-instance execution when required. Some scheduled background tasks must not run concurrently." Recommends distributed locks or Kubernetes `concurrencyPolicy: Forbid` for singleton jobs. Also: "scale background tasks independently from the application" and "To reduce job impact on web app performance, consider creating an empty Azure web app instance in a separate App Service plan to host long-running or resource-intensive WebJobs."
 - Microsoft Azure Architecture - Leader Election Pattern (https://learn.microsoft.com/en-us/azure/architecture/patterns/leader-election). Confirms: use when multiple instances must coordinate to avoid conflicting access. Also: "might not be useful if the coordination between tasks can be achieved by using a more lightweight method like optimistic or pessimistic locking" - validates the DynamoDB conditional write approach over full leader election.
- Alignment summary:
 - Colocated model with thread-based execution aligns with Factor VIII's allowance for internal multiplexing via threads.
 - Idempotency requirement aligns with Factor IX's reentrant job mandate.
 - Two-tier concurrency classification aligns with Kubernetes CronJob `concurrencyPolicy` model and Azure Background Jobs best practices.
 - Lightweight DynamoDB lock for singleton jobs aligns with Azure Leader Election guidance preferring optimistic/pessimistic locking over full leader election when sufficient.
 - Production-only guard with registration parity aligns with Factor X's dev/prod parity principle.
 - Plugin-based registration aligns with ADR-0049's zero-touch extension model.
- Intentional deviations: None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Supersedes ADR-0015 by extracting implementation-level background service guidance from Tier-1 to Tier-2 standard with library-agnostic standards for execution model, job registration, idempotency, error isolation, and observability.
- Follow-up actions:
 - Mark ADR-0015 as `status: Superseded` with `superseded_by: [ADR-0058]`.
 - Move ADR-0015 to `docs/decisions/adr/superseded/`.
 - Audit `app/jobs/scheduled_tasks.py` against Standard 4 idempotency requirements (particularly `notify_stale_incident_channels` and `generate_spending_data`).
 - Add missing Standard 6 observability events to job initialization and `safe_run` wrapper.
 - Consider adding job duration measurement to the `safe_run` wrapper.

## Source References

1. Source title: The Twelve-Factor App - Disposability
 - URL: https://12factor.net/disposability
 - Publisher/maintainer: 12factor contributors
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Factor IX requires reentrant/idempotent jobs and graceful shutdown of worker processes.
2. Source title: The Twelve-Factor App - Concurrency
 - URL: https://12factor.net/concurrency
 - Publisher/maintainer: 12factor contributors
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Factor VIII defines the process model for scaling; permits internal thread multiplexing while recommending process formation for horizontal scaling.
3. Source title: The Twelve-Factor App - Dev/Prod Parity
 - URL: https://12factor.net/dev-prod-parity
 - Publisher/maintainer: 12factor contributors
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Factor X requires minimizing divergence between development and production environments, including background execution behavior.
4. Source title: ASGI Lifespan Protocol v2.0
 - URL: https://asgi.readthedocs.io/en/latest/specs/lifespan.html
 - Publisher/maintainer: ASGI community
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Lifespan shutdown event triggers background task cleanup.
5. Source title: Python schedule library documentation
 - URL: https://schedule.readthedocs.io/
 - Publisher/maintainer: schedule contributors
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Documents the `run_pending()` + sleep loop execution model and thread safety characteristics of the current scheduling library.
6. Source title: Pluggy Documentation - Hook Specifications
 - URL: https://pluggy.readthedocs.io/en/stable/
 - Publisher/maintainer: pytest-dev / pluggy
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Authoritative source for hookspec-based registration used by the BackgroundJobRegistry pattern.
7. Source title: Kubernetes CronJob Documentation
 - URL: https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/
 - Publisher/maintainer: Kubernetes / CNCF
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Documents `concurrencyPolicy` field (Allow/Forbid/Replace) as industry-standard model for job concurrency classification. Confirms jobs should be idempotent.
8. Source title: Microsoft Azure Architecture - Best Practices for Background Jobs
 - URL: https://learn.microsoft.com/en-us/azure/architecture/best-practices/background-jobs
 - Publisher/maintainer: Microsoft
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Authoritative guidance on singleton execution, distributed locks, scaling background tasks independently, and resource isolation between web serving and background work.
9. Source title: Microsoft Azure Architecture - Leader Election Pattern
 - URL: https://learn.microsoft.com/en-us/azure/architecture/patterns/leader-election
 - Publisher/maintainer: Microsoft
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Validates lightweight locking (optimistic/pessimistic) as preferred over full leader election when coordination needs are simple.
10. Source title: ADR-0015 (Legacy - Background Services)
 - URL: docs/decisions/adr/0015-background-services.md
 - Publisher/maintainer: SRE Team
 - Accessed date (YYYY-MM-DD): 2026-04-29
 - Relevance summary: Source record being superseded. Contained APScheduler-specific implementation guidance at incorrect Tier-1 classification; codebase uses `schedule` library, not APScheduler.

## Implementation Guidance

- Required changes:
 - Add Standard 6 observability events to `app/jobs/scheduled_tasks.py`: `background_tasks_initialized` with job count, `job_started`/`job_completed`/`job_failed` events with duration measurement.
 - Add duration measurement to the `safe_run` wrapper using `time.monotonic()`.
 - Implement singleton lock infrastructure utility: DynamoDB-backed `@singleton_job` decorator (or `SingletonJobLock` wrapper) with conditional `PutItem`, TTL expiration, and skip-on-lock-held behavior. Place in `app/infrastructure/` per dependency boundary rules.
 - Apply singleton lock to Tier 2 jobs: `provision_aws_identity_center`, `notify_stale_incident_channels`, `generate_spending_data`, `reconcile_access_sync`.
 - Audit `notify_stale_incident_channels` for idempotency - singleton classification reduces but does not eliminate duplicate risk (TTL expiration edge case). Document acceptance or add deduplication.
 - Audit `generate_spending_data` for upsert semantics - ensure writes are idempotent even under singleton lock TTL edge cases.
 - Verify `BackgroundJobRegistry` enforces unique job names at registration time.
 - Add tier classification field to `BackgroundJobRegistry.register()` Protocol - `tier: Literal[1, 2] = 2`.
 - Add explicit thread join with timeout in lifespan shutdown for the scheduler thread (coordinate with ADR-0057 Standard 2 budget).
- Validation and quality gates:
 - ADR-0051 taxonomy check: confirm no library-specific code examples in normative standards (library-agnostic by design).
 - Metadata completeness check: all 18 fields populated.
 - Job idempotency audit: each registered job's idempotency posture documented and verified.
- Test strategy and acceptance criteria impact:
 - Each job function must have a unit test that invokes it directly (Standard 8 - direct invocation testing).
 - The `safe_run` wrapper must have a test that verifies exception catching and structured log emission.
 - Plugin-registered jobs must be tested via the pluggy hook mechanism in a test fixture.
 - No test should depend on time-based scheduling - use direct invocation only.

## Change Log

- 2026-04-29: Created Tier-2 standard; supersedes ADR-0015. Eight standards covering colocated worker model, production-only execution, plugin-based job registration, idempotency and horizontal scaling, error isolation, observability, scheduler thread lifecycle, and development/test parity.
- 2026-04-29: Challenge review - revised Standard 4 from "all jobs run independently with idempotency only" to two-tier concurrency classification (concurrent-safe vs. singleton) based on Kubernetes CronJob `concurrencyPolicy`, Azure Background Jobs best practices, and Azure Leader Election pattern guidance. Added DynamoDB singleton lock requirement for Tier 2 jobs. Reclassified 4 of 6 current jobs as Tier 2 (singleton). Updated non-goals to correct ADR-0059 cross-reference for queueing scope. Added 3 authoritative source references.

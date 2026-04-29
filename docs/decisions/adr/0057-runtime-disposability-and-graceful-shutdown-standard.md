---
adr_id: ADR-0057
title: "Runtime Disposability and Graceful Shutdown Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Runtime and Lifecycle
secondary_domains:
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
impacts: []
supersedes:
  - ADR-0016
superseded_by: []
review_state: current
related_records:
  - ADR-0053
  - ADR-0054
  - ADR-0058
related_packages:
  - app/server
---

# Runtime Disposability and Graceful Shutdown Standard

## Context

- Problem statement: ADR-0016 (Graceful Shutdown) described reverse-order shutdown mechanics with implementation-level code examples but was classified as Tier-1 Principle — a tier violation per ADR-0044 (principles must not contain implementation detail). It also lacked enforceable standards for shutdown timeout budgeting, resource cleanup obligations, crash resilience, and the relationship between container orchestrator signals and the ASGI lifespan protocol. ADR-0046 Invariant 4 established reverse-order graceful shutdown as a lifecycle principle but delegated the implementation standard to this record.
- Business/operational drivers:
  - Codify the shutdown contract between the container orchestrator (ECS), the ASGI server (uvicorn), and the application lifespan so that all resources are released within the termination grace period.
  - Establish explicit timeout budgeting to prevent SIGKILL from the orchestrator cutting off in-flight work.
  - Define crash resilience requirements so that sudden process death (hardware failure, OOM kill) does not corrupt durable state.
  - Ensure every resource acquired during startup has a corresponding shutdown release obligation.
  - Standardize structured observability for shutdown phases to enable incident diagnosis when shutdowns are incomplete.
- Constraints:
  - FastAPI lifespan context manager is the sole shutdown entry point (ADR-0046 Invariant 1).
  - Shutdown must execute in reverse phase order (ADR-0046 Invariant 4).
  - Shutdown must complete within the container scheduler's termination grace period (ADR-0046 Invariant 4).
  - ASGI server (uvicorn) mediates between OS signals and the lifespan protocol.
  - The application runs as a single-process ECS Fargate task; uvicorn runs as PID 1 via `exec` in the entrypoint script.
  - ALB target group deregistration delay (currently 30s) and ECS stop timeout interact to define the total shutdown window.
- Non-goals:
  - This record does not define specific resource cleanup implementations (e.g., how to close a particular client).
  - This record does not govern background task scheduling or worker isolation (delegated to ADR-0058).
  - This record does not define startup behavior (governed by ADR-0046 and ADR-0049).

## Decision

- Chosen approach: Establish a Tier-2 standard that defines the shutdown contract, timeout budget, resource cleanup obligations, crash resilience requirements, and observability expectations.
- Why this approach: ADR-0046 Invariant 4 establishes the principle (reverse-order graceful shutdown) but deliberately omits implementation-level standards. This record provides the enforceable standards that operationalize Invariant 4 for the current deployment model (ECS Fargate + uvicorn + FastAPI lifespan).

### Standard 1: Signal-to-Lifespan Contract

The application must rely exclusively on the ASGI lifespan protocol for shutdown orchestration. The signal propagation chain is:

1. ECS sends SIGTERM to the container's PID 1 (uvicorn, launched via `exec` in `entry.sh`).
2. Uvicorn receives SIGTERM and initiates ASGI lifespan shutdown — it stops accepting new connections and triggers the lifespan context manager to exit.
3. The FastAPI lifespan context manager executes cleanup code after the `yield` point.
4. After lifespan cleanup completes, uvicorn completes in-flight request draining and exits with status code 0.
5. If the process has not exited within the ECS stop timeout, ECS sends SIGKILL.

**Prohibitions:**
- Application code must not install custom `signal.signal()` handlers for SIGTERM or SIGINT. Signal handling is delegated to the ASGI server.
- Application code must not call `sys.exit()` or `os._exit()` during shutdown. The lifespan context manager must return normally to allow uvicorn to complete its shutdown sequence.
- Application code must not fork child processes that outlive the lifespan scope.

### Standard 2: Shutdown Timeout Budget

The total time available for graceful shutdown is determined by two infrastructure parameters:

| Parameter | Source | Current Value | Purpose |
|-----------|--------|---------------|---------|
| ALB deregistration delay | `terraform/alb.tf` | 30 seconds | Time allowed for in-flight HTTP requests to complete after the target is deregistered from the load balancer. |
| ECS stop timeout | ECS default | 30 seconds | Time between SIGTERM and SIGKILL. |

The application shutdown budget is the time between lifespan cleanup start and SIGKILL. This budget must be allocated across shutdown phases:

| Phase | Budget Allocation | Activity |
|-------|-------------------|----------|
| Background | ≤ 5 seconds | Stop scheduled tasks, signal daemon threads |
| Transport | ≤ 5 seconds | Close WebSocket connections, join transport threads |
| Feature | ≤ 2 seconds | Deactivate feature-specific handlers |
| Infrastructure | ≤ 5 seconds | Close clients, flush buffers, release connections |
| Reserve | ≥ 3 seconds | Margin for uvicorn request draining and OS cleanup |

**Rules:**
- No individual shutdown phase may block indefinitely. All blocking operations (thread joins, connection closes) must use explicit timeouts.
- Thread join timeouts must not exceed the phase budget (e.g., `thread.join(timeout=5)`).
- If a phase exceeds its budget, the lifespan must log a warning and proceed to the next phase rather than blocking.
- The `--timeout-graceful-shutdown` uvicorn parameter should be configured to align with the ECS stop timeout minus a safety margin.

### Standard 3: Resource Cleanup Obligation

Every resource acquired during startup must have a corresponding cleanup action during shutdown. The cleanup obligation is tracked by resource category:

| Resource Category | Acquisition Phase | Cleanup Requirement | Cleanup Phase |
|-------------------|-------------------|---------------------|---------------|
| Scheduled tasks | Background (phase 6) | Signal stop event, allow current job to finish | Background (reverse) |
| Transport connections | Transport (phase 5) | Close connections, join threads with timeout | Transport (reverse) |
| Platform providers | Feature Activation (phase 4) | Call `provider.stop()` for each enabled provider | Feature (reverse) |
| Thread pool executors | Infrastructure (phase 2) | Call `executor.shutdown(wait=True)` with bounded timeout | Infrastructure (reverse) |
| HTTP client sessions | Infrastructure (phase 2) | Close persistent sessions | Infrastructure (reverse) |
| Plugin registries | Discovery (phase 3) | No cleanup needed (immutable, GC-collected) | N/A |
| Settings singletons | Configuration (phase 1) | No cleanup needed (immutable, GC-collected) | N/A |

**Rules:**
- Resources stored in `app.state` during startup must be cleaned up during shutdown by referencing the same `app.state` attribute.
- Missing `app.state` attributes during shutdown must be handled with `getattr(app.state, attr, None)` checks — not bare `hasattr` with separate access.
- Cleanup code must not raise exceptions. If a cleanup operation fails, it must log the error and continue to the next cleanup step.
- `atexit` handlers are a last-resort safety net, not a substitute for lifespan-managed cleanup. Resources should be cleaned up in the lifespan shutdown, with `atexit` as a fallback for abnormal exits only.

### Standard 4: Crash Resilience

The application must be resilient to sudden process death (SIGKILL, OOM kill, hardware failure) without corrupting durable state. This is achieved through the following requirements:

1. **No incomplete writes to durable storage.** All writes to DynamoDB, S3, or other backing services must be atomic or idempotent. A killed process must not leave partially written records that corrupt subsequent reads.
2. **No exclusive locks held across request boundaries.** Locks (DynamoDB conditional writes, distributed locks) must be scoped to the narrowest possible window. Long-held locks must have TTL-based expiration so that a killed process's locks are automatically released.
3. **Background jobs must be reentrant.** A job interrupted by SIGKILL must be safely re-executable on the next process start or by another ECS task. This aligns with Twelve-Factor Factor IX: "all jobs are reentrant, which typically is achieved by wrapping the results in a transaction, or making the operation idempotent."
4. **No critical state in process memory.** All state that must survive process restart must be externalized to backing services. Process-local caches may be lost without data loss — only performance impact is acceptable.

### Standard 5: Shutdown Observability

Each shutdown phase must emit structured log events that enable operational monitoring and incident diagnosis:

| Event | Required Fields | Purpose |
|-------|----------------|---------|
| `application_shutdown` | (none beyond standard context) | Marks shutdown sequence start |
| `shutdown_phase_started` | `phase`, `timeout_seconds` | Marks individual phase start with its budget |
| `shutdown_phase_completed` | `phase`, `duration_seconds` | Marks successful phase completion |
| `shutdown_phase_timeout` | `phase`, `timeout_seconds`, `duration_seconds` | Phase exceeded its budget |
| `shutdown_resource_error` | `phase`, `resource`, `error` | Cleanup failed for a specific resource |
| `shutdown_complete` | `total_duration_seconds` | Marks clean shutdown completion |

**Rules:**
- Shutdown log events must use the same structured logging configuration as startup events (ADR-0054 compliance).
- Shutdown events must not log sensitive data (credentials, tokens, PII) even in error contexts.
- The `total_duration_seconds` in `shutdown_complete` enables alerting when shutdowns approach the timeout budget.

### Standard 6: Environment Parity for Shutdown

Development and test environments must exercise the same shutdown code path as production, with the following controlled exceptions:

| Concern | Production | Development/Test |
|---------|------------|------------------|
| Scheduled tasks | Running, stopped during shutdown | Not started, no stop needed |
| Transport connections | Active WebSocket/threads | Not started or mocked |
| Platform providers | Active, stopped during shutdown | May be mocked or not started |
| Shutdown log events | Emitted | Emitted (same code path) |
| Signal handling | SIGTERM via ECS | SIGTERM via Ctrl+C or test harness |

**Rules:**
- The lifespan shutdown code must not contain `if environment == "production"` guards that skip cleanup. Cleanup code runs unconditionally; resources that were not acquired (due to environment guards at startup) are handled by null-checks, not by environment branching.
- Test suites that use `TestClient` or `httpx.AsyncClient` must trigger lifespan shutdown to validate cleanup behavior.

## Alternatives Considered

1. Implement custom SIGTERM handler with explicit shutdown orchestration:
   - Pros: Full control over shutdown timing and ordering.
   - Cons: Conflicts with uvicorn's built-in signal handling; risks double-handling of SIGTERM. Violates the ASGI lifespan protocol which is the intended shutdown mechanism.
   - Why not chosen: The ASGI lifespan protocol already provides the shutdown hook. Adding a parallel signal handler creates race conditions and violates the single-entry-point principle (ADR-0046 Invariant 1).

2. Use `atexit` handlers as the primary cleanup mechanism:
   - Pros: Simple registration; no lifespan dependency.
   - Cons: `atexit` handlers do not run on SIGKILL; ordering is LIFO but not phase-aware; no structured observability; no timeout budgeting. They also run after the event loop is closed, so async cleanup is impossible.
   - Why not chosen: `atexit` is a safety net, not a primary mechanism. Lifespan-managed cleanup is more reliable, observable, and phase-ordered.

3. Rely on ECS task replacement without explicit cleanup:
   - Pros: Simplest approach — let the orchestrator kill and replace.
   - Cons: WebSocket connections drop without close frames; in-flight background jobs are interrupted without logging; thread pool executors may leave work half-done; no observability into what was interrupted.
   - Why not chosen: Violates Twelve-Factor Factor IX (graceful shutdown) and ADR-0046 Invariant 4.

## Consequences

- Positive impacts:
  - Explicit timeout budgets prevent SIGKILL from cutting off important cleanup.
  - Resource cleanup obligations create a reviewable contract between startup and shutdown.
  - Crash resilience requirements prevent data corruption from sudden process death.
  - Structured shutdown observability enables alerting on slow or incomplete shutdowns.
- Tradeoffs accepted:
  - Timeout budgets require calibration when new resources are added to the startup sequence.
  - Non-blocking cleanup (proceeding after timeout) means some resources may not be fully cleaned up in pathological cases — but this is preferable to blocking indefinitely and receiving SIGKILL.
- Risks introduced:
  - If the ECS stop timeout or ALB deregistration delay is changed in Terraform without updating the shutdown budget, the budget may be misaligned.
  - Daemon threads (`daemon=True`) terminate abruptly when the main thread exits, regardless of the lifespan shutdown sequence. Resources managed exclusively by daemon threads may not be cleaned up.
- Mitigations:
  - The shutdown budget table in Standard 2 explicitly references the Terraform source parameters for cross-reference during infrastructure changes.
  - Standard 3 requires explicit cleanup for all resource categories, including daemon thread-managed resources (via thread join with timeout before the main thread exits).

## Compliance and Boundaries

- Package/infrastructure boundary impact: Shutdown standards apply uniformly — both infrastructure services (clients, executors) and feature packages (providers, handlers) must comply with cleanup obligations.
- Type boundary impact: Not directly applicable; deferred to ADR-0065.
- Startup/plugin registration impact: Standard 3 creates a symmetric obligation: every resource registered during startup (ADR-0049 Standard 6 warmup) must have a shutdown cleanup. Feature packages that register resources must document their cleanup path.
- Settings partitioning impact: Not directly applicable.

## Best-Practice Revalidation

- Revalidation date: 2026-04-29
- Sources rechecked:
  - Twelve-Factor App Factor IX — Disposability (https://12factor.net/disposability). Confirms: fast startup, graceful SIGTERM shutdown, reentrant jobs, crash-only design.
  - Twelve-Factor App Factor VIII — Concurrency (https://12factor.net/concurrency). Confirms: processes should never daemonize or write PID files; rely on the process manager for signal handling.
  - ASGI Lifespan Protocol v2.0 (https://asgi.readthedocs.io/en/latest/specs/lifespan.html). Confirms: lifespan.shutdown event is the ASGI-level shutdown hook.
  - Uvicorn settings documentation (https://uvicorn.dev/settings/). Confirms: `--timeout-graceful-shutdown` parameter controls in-flight request draining timeout after lifespan shutdown.
  - FastAPI Lifespan Events documentation (https://fastapi.tiangolo.com/advanced/events/). Confirms: code after `yield` in lifespan context manager runs during shutdown.
  - AWS ECS documentation — Task Lifecycle. Confirms: ECS sends SIGTERM, waits `stopTimeout` (default 30s), then sends SIGKILL.
  - Crash-Only Software (Candea & Fox, 2003) — lwn.net/Articles/191059/. Confirms: designing for crash resilience by default simplifies both normal and abnormal shutdown paths.
- Alignment summary:
  - Signal-to-lifespan contract (Standard 1) aligns with ASGI lifespan protocol and uvicorn signal handling.
  - Timeout budgeting (Standard 2) operationalizes Factor IX's graceful shutdown within the ECS termination window.
  - Crash resilience (Standard 4) aligns with Factor IX's reentrant job requirement and crash-only design principles.
  - Shutdown observability (Standard 5) extends ADR-0054's structured logging posture to shutdown events.
- Intentional deviations: None.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Supersedes ADR-0016 by extracting implementation-level shutdown guidance from Tier-1 to Tier-2 standard with enforceable standards for timeout budgeting, resource cleanup, crash resilience, and observability.
- Follow-up actions:
  - Mark ADR-0016 as `status: Superseded` with `superseded_by: [ADR-0057]`.
  - Move ADR-0016 to `docs/decisions/adr/superseded/`.
  - Audit current `app/server/lifespan.py` shutdown code against Standard 2 timeout budgets and Standard 5 observability events.
  - Verify `--timeout-graceful-shutdown` is configured in uvicorn startup command or add it.
  - Ensure `app/infrastructure/events/dispatcher.py` shutdown_event_executor is called during lifespan shutdown, not only via `atexit`.

## Source References

1. Source title: The Twelve-Factor App — Disposability
   - URL: https://12factor.net/disposability
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Factor IX defines graceful shutdown via SIGTERM, reentrant jobs, and crash-only design as the disposability standard.
2. Source title: The Twelve-Factor App — Concurrency
   - URL: https://12factor.net/concurrency
   - Publisher/maintainer: 12factor contributors
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Factor VIII requires processes to not daemonize or write PID files; rely on the process manager for lifecycle management.
3. Source title: ASGI Lifespan Protocol v2.0
   - URL: https://asgi.readthedocs.io/en/latest/specs/lifespan.html
   - Publisher/maintainer: ASGI community
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Defines lifespan.shutdown event as the protocol-level shutdown mechanism for ASGI applications.
4. Source title: Uvicorn Settings — Timeouts
   - URL: https://uvicorn.dev/settings/
   - Publisher/maintainer: Marcelo Trylesinski / uvicorn
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Documents `--timeout-graceful-shutdown` parameter for controlling request draining timeout after lifespan shutdown.
5. Source title: FastAPI Lifespan Events
   - URL: https://fastapi.tiangolo.com/advanced/events/
   - Publisher/maintainer: Sebastián Ramírez / FastAPI
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Documents lifespan context manager as the recommended startup/shutdown mechanism, with code after yield running during shutdown.
6. Source title: Crash-Only Software
   - URL: https://lwn.net/Articles/191059/
   - Publisher/maintainer: Candea & Fox (2003), via LWN
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Foundational paper on designing systems where crash recovery and normal shutdown are the same code path.
7. Source title: ADR-0016 (Legacy — Graceful Shutdown)
   - URL: docs/decisions/adr/0016-graceful-shutdown.md
   - Publisher/maintainer: SRE Team
   - Accessed date (YYYY-MM-DD): 2026-04-29
   - Relevance summary: Source record being superseded. Contained implementation-level shutdown code examples at incorrect Tier-1 classification.

## Implementation Guidance

- Required changes:
  - Add structured shutdown phase logging to `app/server/lifespan.py` shutdown code (Standard 5 events).
  - Add explicit timeout parameters to all thread `.join()` calls during shutdown.
  - Wire `shutdown_event_executor()` from `app/infrastructure/events/dispatcher.py` into the lifespan shutdown sequence instead of relying solely on `atexit`.
  - Configure `--timeout-graceful-shutdown` in the uvicorn startup command in `app/bin/entry.sh`.
  - Audit all daemon threads to ensure resources they manage are cleaned up before the main thread exits the lifespan.
- Validation and quality gates:
  - ADR-0051 taxonomy check: confirm no implementation-level code examples in this record (Tier-2 permits implementation guidance but not executable code blocks as normative content).
  - Metadata completeness check: all 18 fields populated.
  - Verify shutdown sequence completes within the timeout budget by timing shutdown in staging environment.
- Test strategy and acceptance criteria impact:
  - Integration test: lifespan shutdown must complete without errors when triggered by TestClient context manager exit.
  - Timing test: shutdown duration must be measurable and within the Standard 2 budget (staging environment).
  - Crash resilience test: background jobs must be safe to re-execute after process kill (existing job tests should assert idempotency).

## Change Log

- 2026-04-29: Created Tier-2 standard; supersedes ADR-0016. Six standards covering signal-to-lifespan contract, timeout budgeting, resource cleanup obligations, crash resilience, shutdown observability, and environment parity.

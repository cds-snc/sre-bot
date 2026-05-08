---
title: "Application Lifecycle"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [lifecycle, architecture]
constrained_by: [layered-architecture.md, configuration-ownership.md, cloud-portability.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Application Lifecycle

## Context and Problem Statement

The application is a long-running process. Between process start and process exit, the process moves through a sequence of phases: configuration is loaded, infrastructure is composed, features register themselves, routes are mounted, the network port is opened, and traffic is served. The process exits through a symmetric sequence: it stops accepting new traffic, drains in-flight work, closes resources, and terminates. Between those edges, the process operates statelessly — durable state lives in external backing services per [cloud-portability.md](cloud-portability.md).

The problem this record addresses: **what is the process's startup phase order, what are the fail-fast and shutdown contracts at each phase, and what guarantees does the application offer to the orchestrator (container platform, local run command, test harness) about disposability?** The answer affects three things at once:

1. Whether boot is deterministic — does the same code path run in the same order on every start, with no implicit ordering by import side effects.
2. Whether failures during boot manifest at the deployment-readiness boundary (process exits non-zero before traffic is accepted) or later, mid-request.
3. Whether shutdown is graceful — does the process drain and clean up within the orchestrator's grace window, or does it exceed the window and get force-killed.

**Constraints:**

- The application runs as one or more stateless processes ([cloud-portability.md](cloud-portability.md), Contract 3). Crash and restart must be safe at any moment.
- Configuration is read from environment variables and validated at startup ([cloud-portability.md](cloud-portability.md) Contract 1; [configuration-ownership.md](configuration-ownership.md)). Settings classes are validated when their providers are first invoked.
- Logs go to stdout/stderr ([cloud-portability.md](cloud-portability.md) Contract 2). Lifecycle events emit log records to the same stream as request logs.
- The application is implemented on FastAPI/Uvicorn (ASGI). The ASGI lifespan protocol is the boot/shutdown signaling channel.
- The orchestrator (e.g., ECS, Kubernetes) sends `SIGTERM` and waits a bounded grace period (commonly 30 seconds) before sending `SIGKILL`.

**Non-goals:**

- This record does not define the pluggy hookspec set or feature-discovery mechanics — see [plugin-registration-discovery.md](plugin-registration-discovery.md).
- This record does not specify the dependency-injection composition root structure — see [dependency-injection.md](dependency-injection.md).
- This record does not govern background-execution job semantics (idempotency, retry, scheduling primitives) beyond when the background loop starts and stops — see [background-execution.md](background-execution.md).
- This record does not define network port binding, exposure, or local-vs-container differences — see [port-binding-exposure.md](port-binding-exposure.md).
- This record does not specify health-endpoint payload schemas — only the *meaning* and *timing* of readiness vs liveness.

## Considered Options

**Option 1 — Sequential phased lifespan with fail-fast.** A single ASGI lifespan context manager runs ordered startup phases and reverses them on shutdown. Any phase failure on startup halts the process before traffic is accepted; any phase exception on shutdown is logged and the next phase proceeds.

**Option 2 — Module-level initialization with no explicit lifespan.** Boot work executes via import side effects and module-level constants; shutdown is left to interpreter exit. Order depends on import resolution.

**Option 3 — Implicit framework lifecycle with no application-defined phases.** Rely on FastAPI/Uvicorn defaults; no explicit phase model. Components self-initialize on first use.

## Decision Outcome

**Chosen: Option 1 — sequential phased lifespan with fail-fast.**

Boot is a single, ordered, deterministic sequence executed inside the ASGI lifespan context manager. Shutdown is the reverse sequence with bounded budgets per phase. Failure to complete any startup phase halts the process before traffic is accepted; failure during a shutdown phase is logged and the next phase proceeds. The process is disposable in the 12-factor sense: idempotent boot, robust against sudden death, graceful exit within the orchestrator's grace window.

### The six startup phases

The ASGI lifespan context manager runs the following phases in order. Each phase fully completes (including its own provider/dependency calls) before the next begins.

1. **Configuration.** Every `BaseSettings` provider required for boot is invoked once. Validation happens at provider construction (per [configuration-ownership.md](configuration-ownership.md)). A missing required env var or a value that fails Pydantic validation halts boot here.
2. **Infrastructure composition.** Vendor clients are constructed (the infrastructure provider reads the relevant credential `BaseSettings` and calls the client constructor with scalar credentials, per [configuration-ownership.md](configuration-ownership.md)). Composed services in `app/infrastructure/<service>/` are wired against vendor clients and their own settings.
3. **Plugin discovery and registration.** Feature packages register their hookspec implementations through the plugin manager. Discovery enumerates feature packages; registration attaches their hookimpls to the manager.
4. **Feature activation.** Each registered feature publishes its hookimpls and any per-feature initialization (provider caches warmed where needed). Feature-owned outbound adapters are wired at the feature's local providers.
5. **Transport.** External connections are opened: socket-mode clients connected, queue consumers attached, scheduled webhook subscriptions confirmed. Connections that require an external handshake live here so handshake failures halt boot in a clearly named phase.
6. **Background.** Background loops (scheduled jobs, workers) are started. By default this phase runs only when the application is configured for production-equivalent execution; in local development and tests it is suppressed via configuration. Registration of jobs (declaring what would run) happens in phase 3; phase 6 only starts the runner.

After phase 6 completes, the lifespan reaches `yield` and the application begins accepting traffic. **The application's internal registries (plugin hooks, dependency-injection providers, route table) are frozen at that moment**: no further hookimpl registration, provider mutation, or route mounting is permitted on a running process.

### Fail-fast policy

If any phase raises an exception that is not handled within the phase, the lifespan does not reach `yield`. The ASGI server emits `lifespan.startup.failed`; the process exits non-zero before any request is accepted.

- **No silent degradation.** Catching boot exceptions and continuing to `yield` with a partially initialized application is prohibited. A "degraded" application that fails on first request is harder to diagnose than an application that refuses to start.
- **Bounded retry within a phase is permitted** for transient errors (e.g., a vendor API returning 503 during phase 5 transport). Retries must be bounded (typically ≤3 attempts) and deterministic; exhaustion re-raises into the lifespan and halts boot.
- **Configuration errors are caught at phase 1**, not lazily on first request. This is already required by [configuration-ownership.md](configuration-ownership.md); the lifespan ordering enforces it operationally.

### Graceful shutdown

On `SIGTERM`, the ASGI server initiates a two-step shutdown.

**Step A — Request draining.** Uvicorn stops accepting new connections and waits for in-flight requests to complete, bounded by the configured graceful-shutdown timeout (recommended ≤10 seconds). Connections that exceed the timeout are closed. The application does not implement draining itself; the ASGI server owns it.

**Step B — Lifespan shutdown.** After draining, the ASGI server enters the lifespan's shutdown branch (the code after `yield`). Phases run in **reverse order** (6 → 1), each with a bounded budget so the total shutdown completes within the orchestrator's grace window.

| Phase | Reverse step | Bounded budget |
| --- | --- | --- |
| 6 | Stop background loops; signal threads to exit; join with timeout | ≤5 seconds |
| 5 | Close transport connections (socket, queue, scheduled subscriptions) | ≤5 seconds |
| 4 | Feature deactivation hooks (rare; most features have nothing to release) | ≤2 seconds |
| 3 | Plugin unregistration is generally not required; freeze and exit | trivial |
| 2 | Close vendor client sessions / release pooled resources | ≤5 seconds |
| 1 | No-op (settings are immutable values) | trivial |

Reserve ≥3 seconds against the 30-second orchestrator grace window for ASGI server overhead and SIGKILL safety margin.

**Cleanup error handling:** A shutdown phase that raises is logged and the next phase proceeds. Shutdown does not abort on a cleanup exception; the goal is to release as much as can be released within the budget. Any blocking call inside a shutdown phase must take a timeout — no indefinite waits.

### Disposability

The application satisfies 12-factor Factor IX (Disposability):

- **Fast startup.** Phase 1 (configuration) is bounded by `BaseSettings` construction. Phases 2–6 perform local composition and bounded handshakes. Total cold start is bounded by the slowest external handshake in phase 5; no phase performs unbounded work.
- **Robust against sudden death.** No critical state is held in process memory across requests. Background work is idempotent or transactionally guarded. A crashed process can be replaced by a fresh process without coordination.
- **Idempotent boot.** Re-running the boot sequence on a new process produces the same registered hooks, providers, and routes. Boot does not depend on any state from a previous process instance.

### Health and readiness

The application exposes two distinct semantics:

- **Liveness** — "the process is up and the event loop is responsive." A liveness probe failing means the orchestrator should restart the process. Liveness is true from the moment the ASGI server is serving the lifespan's startup phase.
- **Readiness** — "boot has completed and the application is willing to accept business traffic." Readiness flips to true when the lifespan reaches `yield` (after phase 6 completes successfully) and flips back to false when the lifespan begins its shutdown branch.

The exact endpoint paths, payload shapes, and HTTP semantics are governed by [port-binding-exposure.md](port-binding-exposure.md). The lifecycle contract here is: readiness corresponds to "all six phases completed; registries frozen; ready to serve."

### Background loops

Background loops (schedulers, queue consumers running outside ASGI request scope) are started in phase 6 only when the application is configured for production-equivalent execution. The configuration switch is read from a `BaseSettings` provider; in local development and tests, the switch is off and phase 6 is a no-op for runner startup. Registration of jobs (declaring what *would* run) still happens in phase 3 so registration errors are caught everywhere, including in tests.

A background loop runs in a dedicated thread (or task) signalled by an event (e.g., `threading.Event`). Shutdown phase 6 (reverse) sets the event and joins with a bounded timeout. The loop checks the event between iterations and between blocking calls and exits cleanly when set.

### Test substitution

The lifespan context is the entry point for boot in tests as well as in production. Test substitution patterns:

- **FastAPI `TestClient`** (typical integration test) enters the lifespan on first use and exits it on context exit. All six phases run, with configuration test-substituted via `app.dependency_overrides` or env-var injection per [configuration-ownership.md](configuration-ownership.md). Phase 6 is suppressed by configuration as in any non-production run.
- **Direct phase exercise** (rare; for testing boot ordering or fail-fast behavior): tests construct the application with a deliberately misconfigured slice and assert that the lifespan raises before reaching `yield`.
- **Hookimpl tests** call the function directly (the implementation), not through the plugin manager. Registration is exercised separately as part of phase 3 boot tests.

## Consequences

**Positive:**

- Boot is deterministic and locatable. A failure in phase 3 is an obvious "plugin discovery failed" rather than a generic startup error.
- Configuration errors, missing credentials, and broken integrations surface at the deployment-readiness boundary, not mid-request.
- Shutdown completes within the orchestrator grace window with high probability; force-kill becomes the exception, not the norm.
- The phase-frozen registry rule prevents implicit reconfiguration on a running process, which would defeat statelessness.

**Tradeoffs accepted:**

- Strict phase ordering limits clever boot-time tricks (mutating registries from inside a route handler, lazy-initializing an integration on first traffic). The constraint is the value: no "ready except for X" states exist.
- Each shutdown phase having a bounded budget means cleanup may be incomplete under extreme conditions (slow external close). Acceptable because the alternative is missing the orchestrator grace window and being SIGKILLed mid-cleanup.

**Risks:**

- A boot phase that does unbounded work blocks the entire startup. Mitigation: code review checks that no phase performs unbounded retries or unbounded I/O; phase 5 (transport) handshakes have explicit timeouts.
- A background thread that ignores its shutdown event holds open the process past phase 6's join timeout. Mitigation: shutdown phase 6 uses `join(timeout=…)`; if the thread does not exit, shutdown proceeds and the process terminates. Operational visibility: a metric or log warns on join timeout.

## Confirmation

Compliance is verified by:

- **Code review.** Boot work is inside the ASGI lifespan, not in module-level code. No module-level network I/O, no module-level provider calls. Each shutdown step has an explicit timeout on any blocking call.
- **Static analysis.** A check forbids module-level invocation of provider functions or `BaseSettings()` constructors at import time; everything must be inside a function called from the lifespan.
- **Tests.** A boot-failure test asserts that a misconfigured `BaseSettings` causes the lifespan to raise before `yield` (the `TestClient` context exit raises). A shutdown-budget test asserts that a slow shutdown phase does not block past its bounded timeout.

## Source References

1. ASGI Lifespan Protocol (v2.0)
   - URL: <https://asgi.readthedocs.io/en/latest/specs/lifespan.html>
   - Accessed: 2026-04-28
   - Relevance: Defines the `lifespan.startup.complete`, `lifespan.startup.failed`, and `lifespan.shutdown` messages that the ASGI server uses to signal startup success/failure and orderly shutdown to the application. Grounds the use of the lifespan context manager as the single entry point for boot and shutdown.

2. FastAPI — Lifespan Events
   - URL: <https://fastapi.tiangolo.com/advanced/events/>
   - Accessed: 2026-04-28
   - Relevance: Documents the recommended FastAPI lifespan context manager pattern (`@asynccontextmanager`) that runs startup code before `yield` and shutdown code after it. Confirms that the lifespan, not deprecated `on_event` hooks, is the canonical mechanism.

3. The Twelve-Factor App — Disposability (Factor IX)
   - URL: <https://12factor.net/disposability>
   - Accessed: 2026-04-29
   - Relevance: "Maximize robustness with fast startup and graceful shutdown." Establishes the disposability contract: minimize startup time, shut down gracefully on SIGTERM, be robust against sudden death. This is the principle the phased lifecycle operationalizes.

4. The Twelve-Factor App — Concurrency (Factor VIII)
   - URL: <https://12factor.net/concurrency>
   - Accessed: 2026-04-29
   - Relevance: Establishes the process model in which the application runs as one or more stateless processes managed by an external process manager. The orchestrator-driven SIGTERM/grace-window contract follows from this model.

5. Uvicorn — Settings (`--timeout-graceful-shutdown`)
   - URL: <https://uvicorn.dev/settings/>
   - Accessed: 2026-04-29
   - Relevance: Documents Uvicorn's request-draining timeout that bounds Step A of shutdown. Grounds the recommended ≤10-second draining budget within the 30-second orchestrator grace window.

6. Crash-Only Software — George Candea & Armando Fox
   - URL: <https://lwn.net/Articles/191059/>
   - Accessed: 2026-04-29
   - Relevance: Argues that the simplest reliable shutdown path is the crash path — components must already tolerate sudden termination, so making graceful shutdown a "best-effort superset" of crash recovery is sound. Grounds the "robust against sudden death" property and the rule that shutdown errors do not abort the shutdown sequence.

7. AWS — Amazon ECS Task Lifecycle
   - URL: <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_lifecycle.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the ECS task termination flow: `SIGTERM` → `stopTimeout` (default 30 seconds) → `SIGKILL`. Grounds the bounded shutdown budget and the ≥3-second reserve for SIGKILL safety margin. The same general contract applies on Kubernetes (`terminationGracePeriodSeconds`).

## Change Log

- 2026-05-08: Created. Establishes a single-lifespan, six-phase startup sequence (Configuration → Infrastructure composition → Plugin discovery and registration → Feature activation → Transport → Background) with fail-fast on any phase exception, a reverse-order shutdown sequence with bounded per-phase budgets within the orchestrator grace window, and the disposability contract (fast startup, robust against sudden death, idempotent boot). Defines readiness as "all six phases completed; registries frozen" and liveness as "process up and event loop responsive." Defers hookspec mechanics to plugin-registration-discovery.md, composition-root structure to dependency-injection.md, background-job semantics to background-execution.md, and health-endpoint paths/payloads to port-binding-exposure.md.

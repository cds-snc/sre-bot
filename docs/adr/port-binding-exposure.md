---
title: "Port Binding and Exposure"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [operations]
concerns: [compute]
constrained_by: [cloud-portability.md, application-lifecycle.md, configuration-ownership.md, api-security.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Port Binding and Exposure

## Context and Problem Statement

The application is a self-contained HTTP service: it brings its own server (uvicorn under FastAPI), it speaks HTTP directly to whatever sits in front of it, and it lives or dies by the orchestrator's view of its responsiveness. The orchestrator sends traffic, observes liveness and readiness probes, sends `SIGTERM`, and expects a clean shutdown inside a bounded window. Getting this contract wrong produces failure modes that are worse than a crash: traffic routed to a starting process before its registries are frozen, a `502` storm during a normal deploy, a process that the orchestrator force-kills because it didn't drain in time.

The problem this record addresses: **what is the application's contract with whatever runs it — what port it binds, what health endpoints it exposes, what their semantics are, and how the shutdown timeline composes inside the orchestrator's grace window?** The answer determines:

1. Whether the orchestrator can decide "replace this task" (liveness) and "send traffic to this task" (readiness) using two distinct, well-defined signals.
2. Whether a deploy is a graceful rolling replacement (no `502`s, no half-served requests) or an outage event.
3. Whether traffic is routed to a process whose lifespan has not yet completed all phases — the "ready except for X" failure mode the lifespan record forbids.
4. Whether health endpoints leak information that should not be public, and whether they are subject to the same authentication, rate-limiting, and CORS rules as everything else (or exempt — and if exempt, on what grounds).

**Constraints:**

- The application binds one network port and listens for inbound traffic ([cloud-portability.md](cloud-portability.md), 12-factor VII). No embedded reverse proxy; no auxiliary admin port; no out-of-band management channel.
- The lifespan defines two distinct operational conditions ([application-lifecycle.md](application-lifecycle.md)): *liveness* — the process is up and the event loop is responsive; *readiness* — all six startup phases have completed, registries are frozen, the application is willing to serve. These are the two probes operations consumes.
- The orchestrator (ECS Fargate, equivalent on other platforms) sends `SIGTERM` and waits a grace period (default 30 s on ECS) before `SIGKILL`. Total shutdown — request draining plus lifespan reverse phases — must fit inside that window with margin.
- Application-layer security ([api-security.md](api-security.md)) authenticates traffic, enforces rate limits, applies CORS, and returns RFC 9457 problem-details on errors. Health probes are part of the inbound surface; this record names how they compose with that posture.
- Port and host values are settings ([configuration-ownership.md](configuration-ownership.md)), not hard-coded constants.

**Non-goals:**

- This record does not specify how a deploy is performed (image registry, task-definition revisions, rolling vs. blue/green). That is owned by [build-release-run-pipeline.md](build-release-run-pipeline.md).
- This record does not specify which orchestrator runs the application (ECS, Kubernetes, a single VM). The contract here is shaped to compose with any of them.
- This record does not own load-balancer configuration (ALB target-group settings, listener rules). The application's side of the contract is the endpoint shape; the orchestrator-side configuration is operations infrastructure.
- This record does not cover authentication of inbound traffic — that is owned by [api-security.md](api-security.md). Health probes are an exemption named here; the rest is unchanged.

## Considered Options

**Option 1 — Single-port HTTP binding via uvicorn at `0.0.0.0:$PORT`; `/health/liveness` and `/health/readiness` as dedicated unauthenticated endpoints; readiness-only routing through the load balancer; bounded shutdown timeline (≤10 s drain, ≤5 s lifespan reverse phase, ≥3 s SIGKILL safety margin) inside the 30 s grace window; one process per task, one port per process.** All inbound traffic flows through the same listener; health probes are routed by URL prefix and treated specially (no auth, no rate limit, no PII, no CORS strictness).

**Option 2 — Separate admin port for health and management.** A second listener bound to a different port for ops-only traffic.

**Option 3 — Embedded reverse proxy (nginx, Caddy) ahead of the application.** Two processes per task: the proxy and the app.

**Option 4 — Re-use a generic endpoint as a health probe.** No dedicated `/health/*` paths; orchestrator probes `/` or some app endpoint and infers health from the status code.

## Decision Outcome

**Chosen: Option 1 — single-port HTTP binding; dedicated `/health/liveness` and `/health/readiness` endpoints; readiness-only routing; bounded shutdown timeline.**

This is the only option that gives operations the two distinct signals it actually needs (replace vs. route) without coupling them to business endpoints, while staying inside the 12-factor "one process, one port" model. A separate admin port (Option 2) is operational surface this application does not need — and it doubles the number of network rules and security policies to maintain. An embedded reverse proxy (Option 3) is two processes for a problem one process solves; it adds a coordination mechanism without value at this scale. Re-using a generic endpoint as a probe (Option 4) makes the health signal entangled with whatever the endpoint is doing — including its authentication, rate limiting, and database calls — which is exactly what readiness should not depend on.

### The single port

Uvicorn is the application's HTTP server. It binds:

- **Host:** `0.0.0.0` (all interfaces). The container's network namespace makes this safe; the orchestrator owns network exposure.
- **Port:** the value of the `PORT` (or `SERVER_PORT`) settings field. The default in non-production is `8000`; production reads the value injected by the deployment platform. There are no hard-coded port literals in application code.
- **One worker per process.** The application is a single ASGI application; uvicorn's `--workers` flag is not used (the orchestrator scales by adding tasks, not workers). One process, one port, one application.
- **Graceful shutdown:** uvicorn's `--timeout-graceful-shutdown` is set to `10` seconds. Connections that have not closed within that window are forcibly closed; the lifespan's reverse phases run after.

The settings are owned by `app/infrastructure/server/settings.py` per [configuration-ownership.md](configuration-ownership.md). They are read once during lifespan phase 1; they are not mutated.

### Health probes — semantics, paths, payloads

Two endpoints, distinct in meaning:

#### `GET /health/liveness`

- **Meaning:** "the process is up and the event loop is responsive." The handler is a trivial coroutine that returns immediately.
- **Becomes true:** at the moment the ASGI server begins serving the lifespan startup phase (i.e., the process is alive and accepting connections, even before phase 1 completes).
- **Becomes false:** never on its own. A liveness failure means the process is unresponsive; the orchestrator's response is to replace the task.
- **Response (200):** `{"status": "alive"}`.
- **Response (any other condition):** the endpoint does not return any other shape. If it cannot return, the connection times out at the orchestrator's probe, which is the failure signal.

#### `GET /health/readiness`

- **Meaning:** "all six startup phases have completed, registries are frozen, the application is willing to serve business traffic."
- **Becomes true:** when the lifespan reaches `yield` (after phase 6 completes successfully).
- **Becomes false:** when the lifespan begins its shutdown branch (after `SIGTERM` and the start of request draining).
- **Response (200):** `{"status": "ready"}`.
- **Response (503):** `{"status": "not_ready"}` — emitted during the boot-incomplete window (before phases finish) and during the shutdown window (after `SIGTERM`).

Both endpoints:

- Carry no PII. The payloads are the literal strings above; no per-task identifiers, no version tags, no settings echoes. (Build/release identification is exposed through standard observability surfaces — startup log records — not through the health endpoint.)
- Return JSON with the application's standard `Content-Type: application/json` and CORS headers; they do not leak internal state.
- Are exempt from authentication ([api-security.md](api-security.md)): probes from the orchestrator do not carry application credentials.
- Are exempt from rate limiting: the orchestrator probes them on a fixed cadence (typically every 5–30 s) and a rate limit on probes is not the right defense against DOS.
- Are not subject to the application's general CORS allow-list strictness: probes do not originate in browsers and do not carry credentials. Same-origin browsers reading them is fine; the response has no security-sensitive content.

The endpoint paths (`/health/liveness`, `/health/readiness`) are stable. They are part of the deployment contract and may not be renamed without a coordinated load-balancer-configuration change.

### How the orchestrator uses the probes

Two distinct signals, two distinct consumers:

- **The compute orchestrator (ECS task agent, Kubernetes kubelet) reads the liveness probe.** A task that fails liveness is replaced. The probe is short-lived and cheap.
- **The traffic router (ALB target group, ingress controller) reads the readiness probe.** A task that returns "not_ready" is removed from the routing pool but is *not* replaced; it stays running while waiting for shutdown to complete.

This separation is what produces zero-downtime rolling deploys. A new task starts; readiness is `503` until phase 6 completes; the load balancer does not route to it; once `200`, traffic begins. An old task receives `SIGTERM`; readiness immediately goes to `503`; the load balancer drains it; in-flight requests complete; the lifespan reverse phases run; the process exits. A misconfigured probe (e.g., the load balancer reading liveness instead of readiness) defeats this contract by routing traffic to processes that are not yet ready.

### Shutdown timeline

The application's shutdown is bounded inside the orchestrator's 30-second grace window. The composition:

| Stage | Owned by | Bounded budget |
| --- | --- | --- |
| `SIGTERM` received; readiness flips to `503` | application | trivial |
| Request draining: in-flight requests complete | uvicorn (`--timeout-graceful-shutdown`) | ≤ 10 s |
| Lifespan reverse phases (6 → 1) | application | ≤ 5 s per phase, total ≤ 12 s in practice |
| `SIGKILL` safety margin | reserved | ≥ 3 s |
| **Total** | | **≤ 30 s** |

If a phase exceeds its budget, shutdown logs the timeout and proceeds to the next phase. If the cumulative time exceeds the grace window, `SIGKILL` lands. The application accepts that some long-running shutdown work may be cut short by `SIGKILL`; it keeps state durable through external storage so a hard kill does not produce inconsistent state ([cloud-portability.md](cloud-portability.md)).

### Why no admin port

The application has nothing to expose on a separate port that would not be exposed on the main port. Health is on the main port (and routed by URL); metrics are exported through the same logs ([logging-observability.md](logging-observability.md)); diagnostic access in production is through the orchestrator's task-exec mechanism, not a network listener. A second port doubles network rules, doubles security configuration, and provides no benefit.

### Why no embedded reverse proxy

uvicorn is production-ready as the front of the application. The orchestrator's ALB (or equivalent) handles TLS termination, request routing, and connection management. Adding nginx in front of uvicorn inside the same task adds a process to manage and a coordination mechanism (one process must signal the other on shutdown) without solving a problem the application has.

### What this record does not change

- The lifespan's six-phase order, fail-fast contract, and reverse-shutdown ordering remain authoritative.
- The application's general security posture (auth, rate limit, CORS, problem-details) remains. Health probes are an explicit exception with the rationale named here.
- Per-vendor settings, plugin contracts, observability shape — all unchanged.

## Consequences

**Positive:**

- One port, one server, one application: the simplest deployment topology that solves the problem.
- Operations has the two signals it needs: replace-or-not (liveness), route-or-not (readiness). Misuse of one for the other is a configuration mistake, not an architectural ambiguity.
- Rolling deploys produce zero `502`s under nominal conditions: a starting task is not in the routing pool until ready; a stopping task drains before exiting.
- Health probes do not depend on backing services, the database, or external integrations. A backing-service outage shows up as `TRANSIENT_ERROR` on real traffic, not as a flapping liveness probe.

**Tradeoffs accepted:**

- Health probes do not deeply check downstream dependencies. A task whose database is unreachable still answers `200` on `/health/readiness`. Acceptable: probe-driven cascading failures (a flapping database flapping the health probe flapping the routing table) are worse than the targeted observability on real traffic.
- The shutdown timeline is tight by design. A deploy that legitimately needs longer than 30 seconds to drain is not absorbed by this contract; the application is expected to keep request handlers fast and to push long work to background or queue paths.
- Build/release identification is not on the health endpoint. Operations consults the startup log record to identify what is running. Acceptable: the health endpoint stays minimal; identification is in the log, where it is correlated with other lifecycle events.

**Risks and mitigations:**

- **The load balancer is misconfigured to read liveness as the routing probe.** Traffic is routed to tasks that have not finished phase 6; intermittent boot-time failures result. *Mitigation:* the deployment platform's configuration is reviewed; an integration test against a staging deploy verifies that traffic does not reach a `503`-readiness task.
- **A long-running request keeps a connection open past the 10 s drain window.** It is forcibly closed; the client sees a connection reset. *Mitigation:* request handlers are kept short; long work goes through queue/background; client-facing timeouts are documented.
- **`SIGKILL` lands during a shutdown phase.** Resources are not closed cleanly. *Mitigation:* application state is held in external storage with idempotency; a hard kill does not produce inconsistent state. The probability is bounded by the budget reserve; alarms fire if the reserve is consistently consumed.
- **The health endpoint is treated as authentication-bypass for internal traffic.** A client crafts requests targeted at `/health/*` to bypass policy. *Mitigation:* the health endpoints have no business behaviour; bypassing them gets the client `{"status": "ready"}` and nothing else. The exemption is for probes, not for application data.

## Confirmation

Compliance is verified by:

- **Code review.** No port literal in application code (uvicorn binds from settings). The `/health/liveness` and `/health/readiness` paths are defined exactly once. Their handlers do not call into business services or backing services.
- **Boot test.** A test asserts that during phase 1 of lifespan startup, `/health/liveness` returns `200` while `/health/readiness` returns `503`. After lifespan yield, both return `200`. After `SIGTERM`, readiness flips to `503` while requests in flight complete; uvicorn's drain timeout is observable.
- **Shutdown test.** A test asserts that the lifespan's reverse phases complete within their bounded budgets; a phase that exceeds is logged with the timeout marker and shutdown proceeds.
- **Operational checks.** Dashboards visualize shutdown phase durations; alarms fire on shutdown budget exceeding the grace window minus reserve.

## Source References

1. The Twelve-Factor App — Port Binding (Factor VII)
   - URL: <https://12factor.net/port-binding>
   - Accessed: 2026-04-29
   - Relevance: Establishes that "the twelve-factor app is completely self-contained" and exposes its service via a port, with no runtime injection of a web server. Grounds the rule that uvicorn binds the application's only port and the orchestrator routes to it.

2. ASGI Lifespan Protocol (v2.0)
   - URL: <https://asgi.readthedocs.io/en/latest/specs/lifespan.html>
   - Accessed: 2026-04-28
   - Relevance: Defines the lifespan messages (`startup.complete`, `startup.failed`, `shutdown.complete`) the ASGI server uses to coordinate boot and shutdown. Grounds the rule that `/health/readiness` flips on the basis of lifespan state.

3. Uvicorn — Settings (`--timeout-graceful-shutdown`)
   - URL: <https://uvicorn.dev/settings/>
   - Accessed: 2026-04-29
   - Relevance: Documents Uvicorn's request-draining timeout. Grounds the ≤10 s drain budget within the 30 s grace window.

4. AWS — Amazon ECS Task Lifecycle and `stopTimeout`
   - URL: <https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_lifecycle.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the ECS task termination flow: `SIGTERM` → `stopTimeout` (default 30 seconds) → `SIGKILL`. Grounds the shutdown-timeline composition. The same general contract applies on Kubernetes via `terminationGracePeriodSeconds`.

5. AWS — ALB Target Group Health Checks
   - URL: <https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html>
   - Accessed: 2026-05-08
   - Relevance: Documents the ALB-side configuration of the readiness probe (path, success codes, healthy/unhealthy thresholds). Grounds the contract that the ALB reads `/health/readiness` and routes only to `200`-returning tasks.

6. Kubernetes — Liveness, Readiness and Startup Probes
   - URL: <https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes>
   - Accessed: 2026-05-08
   - Relevance: Documents the canonical separation of liveness and readiness probes and the operational consequences of conflating them. Grounds the rule that liveness is "replace this task," readiness is "route to this task," and they are distinct signals.

7. RFC 9110 — HTTP Semantics, §15.6.4 "503 Service Unavailable"
   - URL: <https://www.rfc-editor.org/rfc/rfc9110.html#section-15.6.4>
   - Accessed: 2026-05-08
   - Relevance: Defines `503` semantics ("server is currently unable to handle the request… the implication is that this is a temporary condition"). Grounds the use of `503` as the readiness-not-yet response, distinct from a `200` "ready" response.

## Change Log

- 2026-05-08: Created. Establishes single-port HTTP binding via uvicorn at `0.0.0.0:$PORT` (settings-driven). Specifies `/health/liveness` (process up, event loop responsive — probes consumed by the compute orchestrator) and `/health/readiness` (lifespan complete; phases 1–6 done — probes consumed by the traffic router). Names the bounded shutdown timeline (`SIGTERM` → readiness `503` → ≤10 s drain → ≤5 s × phases lifespan reverse → ≥3 s `SIGKILL` reserve, total ≤30 s ECS grace window). Exempts health probes from authentication, rate limiting, and CORS strictness with explicit rationale. Forbids embedded reverse proxy and admin-port topologies. Defers deploy mechanics to build-release-run-pipeline.md.

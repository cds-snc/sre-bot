---
title: "Operation Result Pattern"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture, api]
constrained_by: [layered-architecture.md, type-boundaries.md, api-design-error-mapping.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Operation Result Pattern

## Context and Problem Statement

Outbound integrations to external systems — cloud SDKs, third-party APIs, queues, identity stores — produce a small, *expected* set of outcomes (success, not-found, retriable failure, permanent failure, unauthorized) that the calling application is contractually required to act on. Vendor SDKs communicate these outcomes through typed exceptions. The application needs a single, uniform return type at the layer above the adapter so that consumers can branch on integration outcomes without holding a vendor-specific exception hierarchy.

The problem this record addresses: **what shape and status set does that uniform return type carry, and where in the codebase does it appear?** The contract has to satisfy three needs simultaneously:

1. The secondary adapter — Path A composed-service implementation or Path B feature-owned adapter — needs a well-known set of statuses to map SDK exceptions into ([client-adapter-responsibilities.md](client-adapter-responsibilities.md)).
2. The feature service consuming the adapter Protocol needs to branch on the result without depending on the SDK's exception hierarchy.
3. The HTTP and platform-message edges that ultimately surface the outcome need a stable mapping from result statuses to wire-format errors (governed by [api-design-error-mapping.md](api-design-error-mapping.md)).

**Constraints:**

- `OperationResult` is the uniform cross-layer return contract for outbound integration outcomes. It is returned by secondary-adapter Protocol methods to feature services, and by feature services to handlers (see Boundary scope below).
- Vendor clients do not return `OperationResult`. They raise typed SDK exceptions that the adapter catches and maps ([client-adapter-responsibilities.md](client-adapter-responsibilities.md)).
- Internal application logic uses Python exceptions for programming errors and invariant violations; `OperationResult` is for *expected* integration outcomes only.
- The status set must be closed (a fixed enumeration) so that consumer branching can be exhaustive and HTTP/platform-edge mapping can be total.

**Non-goals:**

- This record does not define the HTTP wire format produced from `OperationResult` (RFC 9457 Problem Details mapping) — see [api-design-error-mapping.md](api-design-error-mapping.md).
- This record does not define retry policy (backoff algorithm, max attempts, jitter) or idempotency on retry — see [handler-idempotency.md](handler-idempotency.md) for handler-driven retries and [message-queuing.md](message-queuing.md) for queue-driven retries.
- This record does not specify the type construct (frozen dataclass, Pydantic model, etc.) — see [type-boundaries.md](type-boundaries.md).

## Considered Options

**Option 1 — Closed-status `OperationResult` envelope at integration boundaries; exceptions internally.** A single envelope type with a closed status enumeration covers integration outcomes. Adapters produce it; consumers branch on it. Internal logic uses Python exceptions. The envelope is mandatory at the secondary-adapter boundary and absent everywhere else.

**Option 2 — Exceptions throughout, no envelope.** Adapters re-raise SDK exceptions, possibly normalized into project-specific exception classes. Feature code catches them.

**Option 3 — Pervasive Result type for all internal calls.** Every function returns a `Result`-typed value; no internal code uses exceptions. Composition (`map`, `bind`) replaces try/except across the application.

## Decision Outcome

**Chosen: Option 1 — closed-status `OperationResult` envelope at integration boundaries; exceptions internally.**

This allocation matches Wlaschin's scope guidance: result types belong at integration boundaries where outcomes are part of the contract, not pervasively throughout internal code where Python exceptions are the natural idiom. It also matches the responsibility split decided in [client-adapter-responsibilities.md](client-adapter-responsibilities.md): the boundary between client and adapter is exception-based; the boundary between adapter and the application above is `OperationResult`-based.

### The status set

`OperationResult` carries a status from a **closed enumeration of five values**:

| Status | Meaning | Retriable by consumer? |
| --- | --- | --- |
| `SUCCESS` | The operation completed and produced its expected outcome (a successful "absent" lookup that returns no payload is also `SUCCESS`). | n/a |
| `NOT_FOUND` | The targeted resource does not exist. This is not a failure of the call — it is the answer. | No |
| `TRANSIENT_ERROR` | The call failed for reasons likely to clear on retry (rate limit, throttling, timeout, upstream 5xx, network blip). The result carries `retry_after` indicating when retry is appropriate. | Yes |
| `PERMANENT_ERROR` | The call failed for reasons that will not clear on retry (validation error, malformed request, unrecoverable upstream 4xx). | No |
| `UNAUTHORIZED` | Authentication or authorization failed. Retrying with the same credentials will not succeed; credential refresh is required first. | Conditional (after credential refresh) |

The set is closed. New statuses are added by amending this record, not by ad-hoc extension at adapter sites. Exhaustive branching by consumers is therefore safe, and the HTTP/platform mapping in [api-design-error-mapping.md](api-design-error-mapping.md) is total.

### The shape

Every `OperationResult` carries:

- `status` — one of the five values above.
- `payload` — the success value, typed by the Protocol's return contract. Present on `SUCCESS`; absent on all other statuses.
- `error_code` — a machine-readable identifier (e.g., `RATE_LIMITED`, `UPSTREAM_TIMEOUT`, `INVALID_REQUEST`). Mandatory on non-`SUCCESS`; absent on `SUCCESS`.
- `message` — a short human-readable description for logs and operational dashboards (not for end users — that is the HTTP/platform edge's responsibility). Mandatory on non-`SUCCESS`.
- `retry_after` — seconds until retry is appropriate. **Mandatory on `TRANSIENT_ERROR`**, absent on all other statuses.

The exact type construct (frozen dataclass, Pydantic model, etc.) is governed by [type-boundaries.md](type-boundaries.md).

### Boundary scope

`OperationResult` is the **internal** contract between an outbound-integration boundary and the layer that consumes it. It appears at two such boundaries:

1. **Secondary adapter → feature service.** The return type of secondary-adapter Protocol methods (Path A composed-service implementations and Path B feature-owned adapters). The adapter is the place where SDK exceptions are caught and mapped onto the closed status set per [client-adapter-responsibilities.md](client-adapter-responsibilities.md).
2. **Feature service → handler.** The return type of the feature-service methods that handlers call. Handlers receive `OperationResult` and pass it to the platform-specific rendering helper (HTTP via the helper governed by [api-design-error-mapping.md](api-design-error-mapping.md); per-platform helpers governed by their respective transport records). Handlers do not synthesize, unwrap to a different envelope, or branch into ad-hoc shapes.

It does not appear:

- Inside vendor client modules under `app/clients/` (which raise typed SDK exceptions — see [client-adapter-responsibilities.md](client-adapter-responsibilities.md) and [client-module-placement.md](client-module-placement.md)).
- Inside the feature service's **internal** control flow. The service consumes adapter-returned `OperationResult` and branches on it; for its own invariant violations and programming errors, the service uses Python exceptions (which propagate to the host's central exception handler when uncaught). The envelope is the service's **output** contract, not its internal coordination type.
- Inside feature domain types. Domain values are frozen dataclasses or Pydantic value types per [type-boundaries.md](type-boundaries.md); they do not depend on `OperationResult`.
- On HTTP route response bodies (mapped to RFC 9457 Problem Details — see [api-design-error-mapping.md](api-design-error-mapping.md)).
- On platform-message bodies sent to Slack, Teams, or other channels (rendered by per-platform helpers; the envelope itself does not cross the wire).

The envelope is internal at every boundary it appears on; the application's edges (HTTP responses, platform messages) translate it into wire-format outputs through dedicated per-platform rendering helpers.

### Relationship with exceptions

Python exceptions remain the idiom for:

- **Programming errors and invariant violations** — they bubble up; they are not modeled in `OperationResult`.
- **Startup and initialization failures** — fail-fast at boot.
- **Internal control flow inside a feature** that does not cross an adapter boundary.

`OperationResult` is the idiom for:

- **Expected integration outcomes** that the calling layer is contractually required to handle.

The boundary between the two is the secondary-adapter file. Below it (in the client and the SDK), exceptions. Above it (in the feature service and the HTTP/platform edges), `OperationResult`.

### Retry semantics

Whether to retry on `TRANSIENT_ERROR` is the consumer's decision, informed by the `retry_after` hint and by the retry/idempotency policy governed by [handler-idempotency.md](handler-idempotency.md) (handler-driven retries) and [message-queuing.md](message-queuing.md) (queue-driven retries). `OperationResult` itself does not retry; it carries the *information* needed for the consumer to retry safely.

### Composition

When a feature service calls multiple adapters, two styles are permitted:

- **Per-call branching** (default): the consumer inspects each `OperationResult` and decides what to do. Readable for two or three calls.
- **Railway-style chaining** (`map`, `bind`, `unwrap_or`): chained operations short-circuit on the first non-`SUCCESS`. Useful when many integration calls are sequenced and the failure path is uniform.

Neither style is mandated. Pervasive railway-style code across internal (non-integration) logic is explicitly out of scope.

## Consequences

**Positive:**

- The set of integration outcomes is fixed and exhaustively branchable; consumers and edges can be made total without escape hatches.
- Adapters have a single mapping target (the closed status set), making review of an adapter's exception → status table a one-page exercise.
- The HTTP and platform edges have a single source-of-truth status set to map from, governed by a separate ADR.
- The envelope's scope is narrow enough that it does not infect internal logic with railway plumbing.

**Tradeoffs accepted:**

- Adding a new status requires amending this record. This is the cost of closure; the benefit is exhaustive branching and total mapping.
- Adapter authors must choose the most accurate status for each SDK exception they encounter — a case-by-case decision that code review must check.

**Risks:**

- A consumer that does not handle one of the five statuses degrades silently (e.g., treats `NOT_FOUND` as failure or `UNAUTHORIZED` as retriable). Mitigation: the type checker treats the status enumeration as a closed `Literal` so missing branches produce a type error.
- Adapter authors might encode SDK detail into `message`, leaking vendor specifics upward. Mitigation: code review confirms `message` is capability-level, not SDK-call-level.

## Confirmation

Compliance is verified by:

- **Code review (adapters).** Every secondary-adapter Protocol method that performs outbound integration returns `OperationResult`. Every non-`SUCCESS` result populates `error_code` and `message`; every `TRANSIENT_ERROR` result populates `retry_after`.
- **Code review (feature services).** Feature service code branches exhaustively on `OperationResult.status`. `OperationResult` does not appear in domain models, HTTP responses, or platform-message payloads.
- **Code review (clients).** Vendor client modules under `app/clients/` do not import `OperationResult` or any status value.
- **Static analysis.** The status enumeration is typed as a closed `Literal` so omitting a status produces a type-checker error. Import-linter (or equivalent) forbids `OperationResult` imports inside `app/clients/`.
- **Tests.** Adapter unit tests cover the mapping for each status the adapter can produce. Feature service tests cover the consumer's behavior for each status the adapter Protocol declares.

## Source References

1. Rust — `Result` Type Documentation
   - URL: <https://doc.rust-lang.org/std/result/>
   - Accessed: 2026-04-28
   - Relevance: Establishes the canonical Result-typed envelope for operations with expected failure modes — status carried in the type, consumers branching exhaustively. Industry-standard precedent for the envelope's role and shape.

2. Railway-Oriented Programming — Scott Wlaschin
   - URL: <https://fsharpforfunandprofit.com/rop/>
   - Accessed: 2026-04-28
   - Relevance: Establishes Result-typed envelopes for cross-boundary operations and the chaining (`map`, `bind`) operations that compose them. Supports the optional composition style.

3. Against Railway-Oriented Programming — Scott Wlaschin
   - URL: <https://fsharpforfunandprofit.com/posts/against-railway-oriented-programming/>
   - Accessed: 2026-04-28
   - Relevance: Argues that result types belong at integration boundaries, not pervasively throughout internal code. Grounds the boundary-scope rule that keeps `OperationResult` out of feature internal logic.

4. The Twelve-Factor App — Backing Services
   - URL: <https://12factor.net/backing-services>
   - Accessed: 2026-04-28
   - Relevance: Backing services are attached resources reachable through a uniform interface. `OperationResult` is the application-level expression of that uniform interface for integration outcomes.

5. RFC 9457 — Problem Details for HTTP APIs
   - URL: <https://www.rfc-editor.org/rfc/rfc9457>
   - Accessed: 2026-04-29
   - Relevance: Defines the standard wire format that `OperationResult` is mapped to at the HTTP edge. Cited here to establish the relationship; the actual mapping is governed by api-design-error-mapping.md.

6. Zalando RESTful API Guidelines — Problem JSON
   - URL: <https://opensource.zalando.com/restful-api-guidelines/#176>
   - Accessed: 2026-04-29
   - Relevance: Industry guidance on RFC 9457 application, including extension fields analogous to `error_code` and `retry_after`. Confirms that the proposed shape maps cleanly to the HTTP wire format.

## Change Log

- 2026-05-08: Created. Establishes `OperationResult` as the uniform cross-layer return contract for outbound integration calls, with a closed five-status set (`SUCCESS`, `NOT_FOUND`, `TRANSIENT_ERROR`, `PERMANENT_ERROR`, `UNAUTHORIZED`) and a shape carrying `payload`, `error_code`, `message`, and `retry_after`. The envelope is scoped to the secondary-adapter return; clients raise SDK exceptions, internal logic uses Python exceptions, and HTTP/platform edges translate to wire formats. Composition is per-call branching by default, with railway-style chaining permitted but not mandated.
- 2026-05-08: Broadened the Boundary scope rule from "exactly one boundary" to two. The envelope appears at (1) secondary-adapter → feature service (the original primary boundary, where SDK exceptions are mapped) and (2) feature service → handler (the boundary `api-design-error-mapping.md` and `feature-handler-standard.md` presuppose when they require route handlers to call `operation_result_to_response(result, request_id)` — handlers can only do that if they have an `OperationResult` in hand, which means the service returned one). The "does not appear inside service logic" rule is preserved as "does not appear in the service's **internal** control flow" — the service's *output* contract is `OperationResult`, but its internal flow uses Python exceptions for invariant violations and branches on adapter-returned envelopes for expected outcomes. No architectural change; the wording now matches how the corpus already uses the envelope across both boundaries. The Constraints bullet was updated correspondingly.

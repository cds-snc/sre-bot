---
title: "Client and Adapter Responsibilities"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, operation-result-pattern.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Client and Adapter Responsibilities

## Context and Problem Statement

Two distinct architectural elements sit at the integration boundary between the application and external systems: **vendor clients** (pre-authenticated SDK wrappers such as `AWSClients`, `GoogleWorkspaceClients`, Slack and Teams platform clients) and **secondary adapters** (composed-service concrete implementations under `app/infrastructure/<service>/` and feature-owned `adapters/<provider>.py` classes inside feature packages). The layer model in [layered-architecture.md](layered-architecture.md) names both elements but does not allocate concerns between them.

The problem this record addresses: **which element owns which concern at the integration boundary, and where does resilience (retry, backoff, error classification) belong?** Three questions drive the contract:

1. Where should retryable errors (rate limits, transient failures, timeouts) be handled—at the client level (uniformly for all callers) or at the adapter level (individually per capability)?
2. Which element catches typed SDK exceptions and translates them into the cross-layer return contract — the `OperationResult` envelope defined in [operation-result-pattern.md](operation-result-pattern.md)?
3. Where do the two *types* of error classification occur: (a) **transport-level** — what is retriable based on HTTP status/SDK semantics; and (b) **domain-level** — what `NOT_FOUND` or `PERMANENT_ERROR` means for a specific capability?

The boundary must be precise enough that two engineers asked "where does this code go?" reach the same answer. It must also keep clients replaceable on their own axis (SDK upgrade, provider swap) without forcing changes to the adapters and feature code that sit above them. The contract must hold for both Path A (composed services) and Path B (feature-owned adapters) per [layered-architecture.md](layered-architecture.md).

**Constraints:**

- `OperationResult` is the **primary integration boundary return contract**: clients expose methods that return `OperationResult`, not typed SDK exceptions. This means clients own the initial exception-to-result mapping.
- Resilience at the boundary (retry, backoff, connection-level error classification) is a **client concern**, not scattered across adapters. The executor pattern (per the Google Workspace implementation) is the canonical approach.
- Vendor SDKs are the authoritative source of typed connection-level errors and pagination semantics; the application uses what the SDK provides rather than re-implementing those primitives.
- Clients must be replaceable independently of adapters and features (provider-swap and SDK-upgrade axes per [layered-architecture.md](layered-architecture.md)).
- Feature domain and service code never holds a reference to a concrete vendor type — the boundary is the adapter file, not the service layer (the invariant in [layered-architecture.md](layered-architecture.md)).
- Both Path A (composed-service implementations) and Path B (feature-owned adapters) consume the same resilient client boundary; they must not duplicate resilience logic.

**Non-goals:**

- This record does not define the `OperationResult` shape, status set, or retry semantics — see [operation-result-pattern.md](operation-result-pattern.md).
- This record does not decide where vendor client modules physically live in the source tree — see [client-module-placement.md](client-module-placement.md).
- This record does not prescribe the Category A/B/C taxonomy for shared infrastructure services — see [infrastructure-service-classification.md](infrastructure-service-classification.md).
- This record does not govern feature package internal structure or where feature-owned adapters live within a package — see [feature-package-structure.md](feature-package-structure.md).

## Considered Options

**Option 1 — Clients raise typed exceptions; secondary adapters catch and map to `OperationResult`.**

The client surface is exception-based, idiomatic Python: callers use ordinary control flow (`try`/`except`) against typed SDK errors. Each secondary adapter independently catches SDK exceptions, implements retry logic for the exceptions it encounters, and maps them to `OperationResult` statuses. Domain translation and resilience logic are scattered across adapters.

**Option 2 — Clients implement resilient execution and return `OperationResult` directly; adapters own domain translation.**

The client surface is `OperationResult`-based. Each client implements an executor pattern (retryable execution with exponential backoff, connection-level error classification, exception-to-result mapping) so that all SDK calls return `OperationResult` with built-in resilience. Adapters then consume `OperationResult` and perform domain-level interpretation and type translation. Both Path A and Path B get resilience as a boundary primitive; they focus on domain logic.

**Option 3 — Clients return raw SDK responses; adapters interpret entirely.**

Clients pass through SDK return values and exceptions without translation. Adapters receive raw SDK shapes and SDK exceptions, and own all interpretation — both transport classification (what is retriable) and domain classification (what is not-found in the domain sense). Resilience logic is duplicated across every adapter.

## Decision Outcome

**Chosen: Option 2 — Clients implement resilient execution and return `OperationResult` directly; adapters own domain translation.**

Resilience and connection-level error handling are *boundary concerns*, not application concerns. They belong at the integration point, not scattered across every adapter. By implementing the executor pattern at the client level, we ensure that:

1. All calls to external systems have consistent retry, backoff, and error classification out of the box.
2. Both Path A (composed-service implementations) and Path B (feature-owned adapters) benefit from resilience uniformly — they are not forced to reimplement the same logic.
3. The adapter layer is freed to focus on domain translation and capability-specific semantics, not on rebuilding transport resilience.
4. Clients remain replaceable on their own axis: a new provider or SDK upgrade changes the client and its executor; it does not affect adapters or features above.

This allocation preserves the Ports and Adapters separation: **the port (Protocol) describes what the application needs in domain terms; the adapter translates between the Protocol and the vendor surface; the client is the executor layer that makes all calls to the vendor resilient by default.**

The pattern's canonical shape is defined in [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md) : the vendor client wires SDK-native retry at construction and exposes `execute(awaitable) -> OperationResult` as a thin classification boundary. The current [Google Workspace executor](../infrastructure/clients/google_workspace/executor.py) and [AWS executor](../infrastructure/clients/aws/executor.py) hand-roll retry loops above the SDK using `time.sleep` and predate the construction-time-retry decision; they are pending refactor and are **not** reference implementations of this contract.

### Path-agnostic application

The contract is the same for Path A (portable capabilities like storage or queuing) and Path B (feature-specific integrations like AWS Identity Center provisioning). Both consume resilient clients; both receive `OperationResult`; both are freed from transport-layer error handling.

### Two types of error classification

The model distinguishes between two layers of error interpretation:

- **Transport-level (client responsibility)**: Is a 429 rate-limit retriable? Is a 503 timeout transient? Is a connection error temporary? The client, in concert with the SDK, answers these. The SDK's retry policy and connection semantics are the source of truth. The executor pattern wraps this and produces `OperationResult` with one of the canonical statuses (`SUCCESS`, `NOT_FOUND`, `TRANSIENT_ERROR`, `PERMANENT_ERROR`, `UNAUTHORIZED`).

- **Domain-level (adapter responsibility)**: For *this capability*, what does `TRANSIENT_ERROR` mean operationally? Can the caller safely retry? For *this capability*, is an empty response `NOT_FOUND` (a legitimate answer) or `PERMANENT_ERROR` (a misconfiguration)? The adapter answers these by interpreting `OperationResult` in the context of what the Protocol promises. The adapter does not re-examine the SDK exception; it interprets the result the client already classified.

### Vendor client responsibilities

A vendor client owns transport-level resilience and the initial boundary translation from SDK semantics to the cross-layer contract:

- **Authentication and session management.** Acquiring credentials (from environment-supplied configuration), creating and reusing authenticated sessions, refreshing tokens. Authentication is performed once per client lifetime, not per call.
- **SDK initialization.** Instantiating boto3, Google API client, Slack/Teams SDK objects with the chosen configuration (region, timeouts, connection pooling). Holding those instances for reuse.
- **Resilience by construction (not by loop).** Wiring the SDK's native retry, backoff, jitter, and `Retry-After` handling at construction time, against the standard parameters in [outbound-retry-policy.md](outbound-retry-policy.md). Concretely:
  - boto3: `Config(retries={"max_attempts": ..., "mode": "standard"})` on the client at construction.
  - `slack_sdk` `AsyncWebClient`: `AsyncConnectionErrorRetryHandler`, `AsyncRateLimitErrorRetryHandler`, `AsyncServerErrorRetryHandler` passed via `retry_handlers=[...]` at construction.
  - `google-api-python-client`: `request.execute(num_retries=N)` at the call site, threaded by the client's executor.
  - Microsoft Graph (`msgraph-sdk` / kiota): `RetryHandlerOption` configured on the middleware chain at construction.
  Hand-rolled retry loops above SDK calls — `for attempt in range(): try: ... except: time.sleep(...)` — are explicitly forbidden by [outbound-retry-policy.md](outbound-retry-policy.md) and not appropriate at this layer. They duplicate SDK behaviour less correctly (typically without jitter and with blocking sleep that stalls async event loops) and nest on top of working SDK retry to produce multiplicative attempts.
- **Transport-level classification (the client's executor).** Implementing a thin classifier — the awaitable-wrapping executor named in [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md)  — that:
  - Awaits the SDK call (or invokes a sync callable for sync SDKs).
  - Applies the per-call wall-clock budget from [outbound-retry-policy.md](outbound-retry-policy.md) via `asyncio.wait_for(...)` for async paths.
  - Catches typed SDK exceptions (e.g., `botocore.exceptions.ClientError`, `googleapiclient.errors.HttpError`, `slack_sdk.errors.SlackApiError`) **after** the SDK's native retry has run inside the call.
  - Classifies the exception (or, where the SDK signals failure in-band, the response shape) into the closed five-status set from [operation-result-pattern.md](operation-result-pattern.md): is this retriable? Is this a permanent failure? Is this an authorization failure?
  - Produces `OperationResult` with appropriate status, error code, message, and `retry_after` on `TRANSIENT_ERROR`.
  - Ensures that **all SDK calls return `OperationResult`, never raise exceptions above the client boundary.**
  The executor does not retry. It classifies. Retry happens inside the awaitable, configured at SDK construction time per the bullet above.
- **Pagination.** Iterating SDK pagination tokens to produce a complete result set; surfacing the result as a normal Python iterable or collecting into a single response. Pagination semantics are vendor-specific (boto3 `client.get_paginator(...)`, googleapiclient `service.<resource>().list_next(prev_req, prev_resp)`) and do not belong in domain code.
- **Concurrency and rate-limit primitives where the SDK does not provide them.** When required, applying low-level concurrency controls (semaphores, pool sizing) at the transport level.

A vendor client does **not**:

- Import feature-domain types or decision logic.
- Decide what "not found" means in the context of a specific business capability.
- Depend on any module from `app/packages/` or `app/infrastructure/<service>/` (except for injected configuration).

**The thin classification executor is the canonical implementation.** Each vendor client wires SDK-native retry at construction and exposes — per [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md)  — both a typed SDK handle and an `execute(awaitable) -> OperationResult` classifier. The executor does not retry; it awaits, applies the per-call wall-clock budget, catches typed SDK exceptions, classifies, returns. Resilience is centralized at the *construction* boundary (one SDK config per vendor); classification is centralized at the *call* boundary (one executor per vendor). Optional curated facades may sit alongside the executor for high-frequency or composed capabilities.

### Secondary adapter responsibilities

A secondary adapter — the concrete implementation of a Protocol, whether a composed-service implementation in `app/infrastructure/<service>/` or a feature-owned adapter at `app/packages/<feature>/adapters/<provider>.py` — owns the translation between the cross-layer result envelope and domain semantics:

- **Domain-level result interpretation.** Consuming `OperationResult` from the client and interpreting what each status means *for this capability*. For example:
  - If a GET returns `NOT_FOUND`, is that a legitimate "resource does not exist" answer (return it as-is) or a misconfiguration (convert to `PERMANENT_ERROR`)?
  - If a POST returns `TRANSIENT_ERROR` with a `retry_after`, should the adapter retry internally or let the caller decide? (Usually: let the caller decide; the adapter returns it as-is.)
  - If a validation endpoint returns `PERMANENT_ERROR`, what does that mean for this capability's correctness contract?
- **Type translation.** Converting the `OperationResult.payload` (SDK response shape) into domain types defined by the Protocol. The Protocol's input and output types are the domain contract; the SDK's response shapes do not appear above the adapter.
- **Capability-level error enrichment.** When needed, augmenting `OperationResult.message` or `OperationResult.error_code` with domain-specific context (e.g., including the resource ID being fetched, or explaining what the failure means operationally for this specific capability).

An adapter does **not** re-examine SDK exceptions (it receives `OperationResult`, not exceptions). It does not reimplement retry or backoff logic. It trusts that the client's `OperationResult` has already classified the failure appropriately at the transport level.

**The adapter's job is to bridge the capability boundary, not the transport boundary.** The client bridges the transport boundary; the adapter bridges the domain boundary.

### The control-flow contract

**The boundary between clients and adapters is `OperationResult`-based.** Clients do not raise exceptions above their boundary; adapters do not catch SDK exceptions directly.

### Replaceability axes

The contract preserves two independent replacement axes:

- **SDK or provider replacement.** Swapping boto3 for another AWS SDK, or replacing Google API client, or upgrading to a new version — changes the client's executor and facade; it does not change the Protocol, the adapter, or feature code. The adapter consumes the same `OperationResult` interface.
- **Domain mapping refinement.** Changing how a capability interprets a result status (e.g., "this SDK error should be treated as NOT_FOUND instead of PERMANENT_ERROR for this capability") — changes only the adapter's interpretation logic; it does not change the client or the Protocol. The client continues to produce the same `OperationResult` statuses; the adapter's handling of them changes.

## Consequences

**Positive:**

- **Unified resilience boundary.** All external calls have consistent retry, backoff, and error handling out of the box. Both Path A and Path B benefit equally; neither duplicates transport-layer logic.
- **Simplified adapters.** Adapters focus on domain translation, not on rebuilding retry logic or exception classification. They consume `OperationResult` and interpret it in domain terms—a simpler, more focused responsibility.
- **Standardizable client pattern.** The executor pattern (used in Google Workspace and applicable to AWS, Slack, Teams, and other vendors) is a reusable reference implementation, reducing variation across client modules.
- **Each capability's domain semantics live in one place.** The adapter, not scattered across retry loop conditions or exception handler catch clauses. The adapter is auditable and reviewable as the canonical source of domain interpretation.
- **Clients remain idiomatic and replaceable.** The executor wraps the SDK; it does not impose a parallel error taxonomy on engineers familiar with boto3 or googleapiclient. Swapping one SDK for another requires changing the client's executor; it does not propagate to adapters or features.

**Tradeoffs accepted:**

- **Clients are no longer thin wrappers.** They encapsulate resilience logic and are stateful (holding session/client instances, managing retry configuration). This is a necessary boundary concern, not a regression.
- **Executor pattern introduces a layer inside the client.** This is justified because the executor isolates complexity and standardizes a reusable pattern across all vendors, reducing per-adapter resilience code.
- **Transport-level classification (retriable vs permanent) must be sound.** A misconfigured executor (incorrectly classifying a 429 as PERMANENT_ERROR, for example) will mislead adapters. Mitigation: executor logic is reviewed and tested independently of any one adapter.

**Risks:**

- **Executor misconfiguration can affect many consumers.** If the executor incorrectly classifies an SDK error, all adapters consuming that client inherit the mistake. Mitigation: executor unit tests explicitly cover each classified status; retry logic is validated independently.
- **Adapters that do not interpret results correctly lose the benefit of the resilient boundary.** An adapter that converts every non-success result to a different status is masking the client's signal. Mitigation: code review emphasizes that adapters should preserve transient results for caller-side retry decisions when appropriate.

## Confirmation

Compliance is verified by:

- **Code review (clients).** Vendor client modules expose facade methods that return `OperationResult`. Each facade is backed by an executor or resilient wrapper that catches typed SDK exceptions and maps them to `OperationResult` statuses. Clients do not raise exceptions above the boundary; they always return `OperationResult`. Clients do not import feature-domain types or depend on `app/packages/` or `app/infrastructure/<service>/` modules (except for injected configuration).
- **Code review (adapters).** Each secondary adapter consumes `OperationResult` from client methods (not exceptions). The adapter interprets each status in domain terms; it does not re-examine SDK exceptions or re-implement retry logic. Adapters may preserve transient results for caller-side decisions or enrich error context with domain-specific information.
- **Static analysis.** Import-linter forbids `from ... import OperationResult` inside low-level client executor modules (clients own one canonical mapping per capability). It permits `from ... import OperationResult` in adapter modules.
- **Tests:**
  - **Executor unit tests.** For each classified SDK exception type and status outcome, verify that the executor produces the correct `OperationResult` status, error code, and message. Verify retry and backoff behavior independently.
  - **Adapter unit tests.** For each result status the client can produce, verify that the adapter interprets it correctly in domain terms. Mock or stub the client to return specific `OperationResult` statuses; do not test SDK exception handling (the executor is responsible for that).
- **Integration tests.** Verify that end-to-end flows (handler → service → adapter → resilient client → SDK) produce the correct HTTP responses or domain outcomes. Failures should be classified consistently.

## Source References

1. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-04-29
   - Relevance: Establishes that the application core communicates with external systems through abstract ports. **Adapters** are the boundary layer that translates between vendor semantics and application semantics. This record expands the adapter concept: there are two tiers of adaptation. The **client executor** adapts SDK exceptions and responses into `OperationResult` (transport level); the **secondary adapter** interprets `OperationResult` in domain terms. Both are necessary boundaries.

2. Architecture Patterns with Python (Cosmic Python) — Repository Pattern (Chapter 2) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_02_repository.html>
   - Accessed: 2026-04-29
   - Relevance: Concrete adapters live in an `adapters/` module and are permitted to import concrete storage clients directly. The adapter is the infrastructure boundary; domain and service code see only the Protocol. This record preserves that model and adds: clients themselves implement resilient execution so that adapters are freed to focus on domain translation.

3. Architecture Patterns with Python (Cosmic Python) — Dependency Injection and Bootstrapping (Chapter 13) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_13_dependency_injection.html>
   - Accessed: 2026-04-29
   - Relevance: The composition root wires concrete adapters; client primitives are constructed once and injected. Grounds the construction-time relationship between a resilient client (now carrying executor state) and the adapter that consumes its `OperationResult`-returning methods.

4. Layers, Onions, Ports, Adapters — Mark Seemann
   - URL: <https://blog.ploeh.dk/2013/12/03/layers-onions-ports-adapters-its-all-the-same/>
   - Accessed: 2026-04-29
   - Relevance: Clarifies that adapters at the infrastructure boundary are architecturally expected to know the specifics of external systems. This record places **two** adaptation layers at the boundary: the client executor (which knows the SDK and classifies errors) and the secondary adapter (which knows the domain and interprets results). Inner-layer code sees only the Protocol and does not see either adapter directly.

5. PEP 544 — Protocols: Structural Subtyping (Static Duck Typing) — Python Enhancement Proposals
   - URL: <https://peps.python.org/pep-0544/>
   - Accessed: 2026-04-29
   - Relevance: Defines the `typing.Protocol` mechanism that adapters satisfy. The Protocol's input and output types form the domain contract; the SDK's shapes do not appear in the Protocol surface and therefore do not appear in feature code.

6. Railway-Oriented Programming — Scott Wlaschin
   - URL: <https://fsharpforfunandprofit.com/rop/>
   - Accessed: 2026-04-28
   - Relevance: Establishes that result-typed envelopes belong at **integration boundaries** where outcomes are part of the contract. This record identifies **two integration boundaries**: the client-to-adapter boundary (where `OperationResult` encapsulates SDK semantics) and the adapter-to-feature boundary (where `OperationResult` carries domain semantics). Both benefit from result-based control flow; inner code uses exceptions.

7. Against Railway-Oriented Programming — Scott Wlaschin
   - URL: <https://fsharpforfunandprofit.com/posts/against-railway-oriented-programming/>
   - Accessed: 2026-04-28
   - Relevance: Argues against result types pervasively inside code — they belong at boundaries, not throughout. This record agrees: `OperationResult` appears at two client-external boundaries (client executor output, adapter output to feature). Internal feature code that encounters a programming error or invariant violation still uses Python exceptions; `OperationResult` is not pervasive.

8. Resilience and Chaos Engineering — O'Reilly — Higgins
   - URL: <https://www.oreilly.com/library/view/resilience-and-chaos/9781491988459/>
   - Accessed: 2026-05-11
   - Relevance: Establishes that retry, backoff, and timeout management are fundamental resilience patterns that should be standard at integration boundaries, not ad-hoc per consumer. Grounds the placement of the executor pattern at the client layer: resilience is a boundary concern, not optional per adapter.

9. Boto3 — Retries Configuration — AWS SDK for Python
   - URL: <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html>
   - Accessed: 2026-05-08
   - Relevance: Confirms that SDKs provide retry modes (standard, adaptive) and connection timeouts as first-class configurable concerns. The executor pattern wraps these SDK capabilities and adds application-level retry behavior to ensure all calls are resilient.

10. The Twelve-Factor App — Backing Services

- URL: <https://12factor.net/backing-services>
- Accessed: 2026-04-28
- Relevance: Backing services are attached resources reachable through a uniform interface. The client executor and adapter together produce that uniform interface (the Protocol surface) regardless of which SDK or provider is configured against.

1. Google Workspace Clients — Pending-Refactor Executor (Not Canonical)

- URL: [../infrastructure/clients/google_workspace/executor.py](../infrastructure/clients/google_workspace/executor.py)
- Accessed: 2026-05-12
- Relevance: Current implementation. Hand-rolls a retry loop above the SDK using `time.sleep`, lacks jitter, ignores any `Retry-After` hint (hardcoded 60s on 429), and mis-classifies exhausted-transient outcomes as `PERMANENT_ERROR`. **Not** the canonical reference for this record. The `google-api-python-client` SDK ships native retry via `HttpRequest.execute(num_retries=N)` which this executor duplicates less correctly. The canonical client shape is defined in [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md); this executor is a pending refactor target.

1. AWS Clients — Pending-Refactor Executor (Not Canonical)

- URL: [../infrastructure/clients/aws/executor.py](../infrastructure/clients/aws/executor.py)
- Accessed: 2026-05-12
- Relevance: Current implementation. Hand-rolls a retry loop with blocking `time.sleep` above boto3 calls that are not configured with a `botocore.config.Config(retries=...)`, so boto3's own retry mode runs alongside ours (nested attempts). Re-creates the boto3 client (and re-runs `sts.assume_role` for cross-account paths) on every retry attempt — wasteful and STS-rate-limit-prone. Leaks the `treat_conflict_as_success` flag and `conflict_callback` into the executor — domain interpretation that belongs in adapters. **Not** the canonical reference. Pending refactor to configure boto3's `standard` retry mode at construction and reduce the executor to a thin classifier.

1. Slack Python SDK — `RetryHandler` framework

- URL: <https://tools.slack.dev/python-slack-sdk/web/#retryhandler>
- Accessed: 2026-05-12
- Relevance: Documents the `slack_sdk` native retry primitives — `AsyncConnectionErrorRetryHandler`, `AsyncRateLimitErrorRetryHandler`, `AsyncServerErrorRetryHandler` — wired onto `AsyncWebClient` at construction via the `retry_handlers=[...]` kwarg. Grounds the construction-time wiring for the Slack shield: native retry lives inside the SDK; the shield's executor only awaits + classifies.

1. google-api-python-client — `HttpRequest.execute(num_retries=N)`

- URL: <https://googleapis.github.io/google-api-python-client/docs/epy/googleapiclient.http.HttpRequest-class.html#execute>
- Accessed: 2026-05-12
- Relevance: Documents the SDK-native retry primitive for the discovery-based Google client (Admin SDK, Drive, Calendar, Gmail). When `num_retries > 0`, the SDK retries `HttpError` 429 and 5xx with jittered exponential backoff (`random.random() * 2^retry_num`). Grounds the rule that the Google Workspace executor refactor uses `num_retries=` rather than a hand-rolled loop.

1. SDK Capability Audit — Research Document

- URL: [../../tmp/research-shield-pattern-sdk-capabilities.md](../../tmp/research-shield-pattern-sdk-capabilities.md)
- Accessed: 2026-05-12
- Relevance: SDK-by-SDK audit (Slack, AWS, Google Workspace, Microsoft Graph) confirming that every SDK we depend on ships first-class retry primitives the application currently does not use. Identifies the concrete regressions in the existing Google Workspace and AWS executors and grounds the 2026-05-12 revision of this record from "client implements resilient execution" to "client is resilient by construction; executor is a thin classifier."

## Change Log

- 2026-05-08: Created. Establishes the responsibility contract for vendor clients (transport-level concerns including authentication, retry, pagination) and secondary adapters (typed-exception → `OperationResult` mapping, type translation, capability-level error semantics). Adopts an exception-based client surface with adapter-level translation, grounded in Ports and Adapters and the Repository Pattern. Anchored to the path-agnostic application of the contract: it applies identically to Path A composed-service implementations and Path B feature-owned adapters defined in layered-architecture.md.

- 2026-05-11: **Reassessed and revised.** Recognized that `OperationResult` should be the primary integration boundary contract at the client layer (not just at the adapter layer). Clients should implement resilient execution using the executor pattern, returning `OperationResult` directly rather than raising exceptions. This ensures both Path A (composed services) and Path B (feature-owned adapters) benefit from consistent retry, backoff, and error classification out of the box. Adapters now focus on domain-level result interpretation rather than rebuilding transport resilience. The Google Workspace executor.py is adopted as the canonical reference implementation. Decision shifts from Option 1 (exception-based clients) to Option 2 (resilient-execution clients returning OperationResult).
- 2026-05-12: **Clarified — resilience is construction-time, classification is call-time.** An SDK-capability audit ([../../tmp/research-shield-pattern-sdk-capabilities.md](../../tmp/research-shield-pattern-sdk-capabilities.md)) established that every SDK the application depends on (boto3, `slack_sdk`, `google-api-python-client`, Microsoft Graph `msgraph-sdk` / kiota) ships first-class retry, backoff, and `Retry-After` handling — and that the existing Google Workspace and AWS executors hand-roll retry loops above the SDK that duplicate these primitives less correctly (no jitter, blocking `time.sleep`, mis-classified exhausted-transient as `PERMANENT_ERROR`, nested attempts when SDK retry is also active, repeated client reconstruction including `sts.assume_role` on every retry). The 2026-05-11 framing ("clients implement resilient execution using the executor pattern") was read as a license to hand-roll those loops; that reading is incorrect. The decision (Option 2 — clients return `OperationResult` directly) is unchanged, but the vendor-client responsibility is now split into two distinct bullets: (a) **Resilience by construction** — the client wires the SDK's native retry/backoff/`Retry-After` primitives at construction time, per the standard policy in [outbound-retry-policy.md](outbound-retry-policy.md) Shape A; (b) **Transport-level classification** — the client exposes the thin awaitable-wrapping executor named in [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md)  that awaits, applies the per-call wall-clock budget via `asyncio.wait_for`, catches typed SDK exceptions, classifies, and returns `OperationResult`. The executor does not retry. The Google Workspace and AWS executors are reclassified as pending-refactor pre-canonical implementations, not reference implementations. The contract for adapters is unchanged.

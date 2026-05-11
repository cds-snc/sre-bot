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

The pattern is exemplified by [executor.py](../infrastructure/clients/google_workspace/executor.py) in the Google Workspace implementation: `execute_google_api_call()` encapsulates retry logic, backoff, SDK exception handling, and `OperationResult` production, so that facade methods expose `OperationResult`-returning operations without individually handling exceptions.

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
- **Resilient execution with retry and backoff.** Implementing an executor or facade layer (per the [Google Workspace executor.py](../infrastructure/clients/google_workspace/executor.py) pattern) that:
  - Wraps each SDK call in a retry loop with configurable max attempts.
  - Applies exponential backoff for transient errors (5xx, rate limits, timeouts).
  - Catches typed SDK exceptions (e.g., `botocore.exceptions.ClientError`, `googleapiclient.errors.HttpError`, `slack_sdk.errors.SlackApiError`).
  - Classifies exceptions into transport-level statuses: is this retriable? Is this a permanent failure? Is this an authorization failure?
  - Produces `OperationResult` with appropriate status, error code, and message.
  - Ensures that **all SDK calls return `OperationResult`, never raise exceptions above the client boundary.**
- **Pagination.** Iterating SDK pagination tokens to produce a complete result set; surfacing the result as a normal Python iterable or collecting into a single response. Pagination semantics are vendor-specific and do not belong in domain code.
- **Concurrency and rate-limit primitives where the SDK does not provide them.** When required, applying low-level concurrency controls (semaphores, pool sizing) at the transport level.

A vendor client does **not**:

- Import feature-domain types or decision logic.
- Decide what "not found" means in the context of a specific business capability.
- Depend on any module from `app/packages/` or `app/infrastructure/<service>/` (except for injected configuration).

**The executor pattern is the canonical implementation.** Each vendor client should expose facade methods that return `OperationResult`. Each facade method invokes SDK operations through a resilient executor that handles retry, backoff, and exception mapping. This centralizes resilience as a boundary concern.

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

1. Google Workspace Clients — Executor Pattern Reference Implementation

- URL: [../infrastructure/clients/google_workspace/executor.py](../infrastructure/clients/google_workspace/executor.py)
- Accessed: 2026-05-11
- Relevance: Demonstrates the canonical executor pattern for this record: `execute_google_api_call()` wraps SDK operations in retry/backoff logic, catches typed SDK exceptions (`HttpError`), and returns `OperationResult` with transport-level status classification. The pattern is reusable across AWS, Slack, Teams, and other vendors.

## Change Log

- 2026-05-08: Created. Establishes the responsibility contract for vendor clients (transport-level concerns including authentication, retry, pagination) and secondary adapters (typed-exception → `OperationResult` mapping, type translation, capability-level error semantics). Adopts an exception-based client surface with adapter-level translation, grounded in Ports and Adapters and the Repository Pattern. Anchored to the path-agnostic application of the contract: it applies identically to Path A composed-service implementations and Path B feature-owned adapters defined in layered-architecture.md.

- 2026-05-11: **Reassessed and revised.** Recognized that `OperationResult` should be the primary integration boundary contract at the client layer (not just at the adapter layer). Clients should implement resilient execution using the executor pattern, returning `OperationResult` directly rather than raising exceptions. This ensures both Path A (composed services) and Path B (feature-owned adapters) benefit from consistent retry, backoff, and error classification out of the box. Adapters now focus on domain-level result interpretation rather than rebuilding transport resilience. The Google Workspace executor.py is adopted as the canonical reference implementation. Decision shifts from Option 1 (exception-based clients) to Option 2 (resilient-execution clients returning OperationResult).

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

The problem this record addresses: **which element owns which concern at the integration boundary?** Two questions in particular drive the contract:

1. Which element catches typed SDK exceptions (e.g., `botocore.exceptions.ClientError`, `googleapiclient.errors.HttpError`, `slack_sdk.errors.SlackApiError`) and translates them into the cross-layer return contract — the `OperationResult` envelope defined in [operation-result-pattern.md](operation-result-pattern.md)?
2. Which element decides what an SDK-level outcome means in domain terms — whether an empty `get_item` response is `NOT_FOUND` or a misconfiguration; whether a 429 is `TRANSIENT_ERROR` or `PERMANENT_ERROR`; whether a partial success is success or failure?

The boundary must be precise enough that two engineers asked "where does this code go?" reach the same answer. It must also keep clients replaceable on their own axis (SDK upgrade, provider swap) without forcing changes to the adapters and feature code that sit above them.

**Constraints:**

- `OperationResult` is the cross-layer return contract for outbound integrations; it is not redefined here.
- Vendor SDKs are the authoritative source of typed connection-level errors and pagination semantics; the application uses what the SDK provides rather than re-implementing those primitives.
- Clients must be replaceable independently of adapters and features (provider-swap and SDK-upgrade axes per [layered-architecture.md](layered-architecture.md)).
- Feature domain and service code never holds a reference to a concrete vendor type — the boundary is the adapter file, not the service layer (the invariant in [layered-architecture.md](layered-architecture.md)).

**Non-goals:**

- This record does not define the `OperationResult` shape, status set, or retry semantics — see [operation-result-pattern.md](operation-result-pattern.md).
- This record does not decide where vendor client modules physically live in the source tree — see [client-module-placement.md](client-module-placement.md).
- This record does not prescribe the Category A/B/C taxonomy for shared infrastructure services — see [infrastructure-service-classification.md](infrastructure-service-classification.md).
- This record does not govern feature package internal structure or where feature-owned adapters live within a package — see [feature-package-structure.md](feature-package-structure.md).

## Considered Options

**Option 1 — Clients raise typed exceptions; secondary adapters catch and map to `OperationResult`.**

The client surface is exception-based, idiomatic Python: callers use ordinary control flow (`try`/`except`) against typed SDK errors. Each secondary adapter (composed-service implementation or feature-owned adapter) holds the single mapping between SDK exceptions and domain-level `OperationResult` statuses for the capability it implements. Domain translation lives in one place per capability.

**Option 2 — Clients return `OperationResult`; secondary adapters check `is_success` and re-wrap.**

The client surface is `OperationResult`-based. Adapters consume `OperationResult` and produce their own `OperationResult`, branching on result state rather than on exceptions. The same envelope appears at both layers, and the client takes responsibility for assigning the initial domain status (e.g., `TRANSIENT_ERROR` vs `PERMANENT_ERROR`) before any adapter sees the call.

**Option 3 — Clients return raw SDK responses; adapters interpret entirely.**

Clients pass through SDK return values and exceptions without translation. Adapters receive raw SDK shapes and SDK exceptions, and own all interpretation — both transport classification (what is retriable) and domain classification (what is not-found in the domain sense).

## Decision Outcome

**Chosen: Option 1 — clients raise typed exceptions; secondary adapters catch and map to `OperationResult`.**

This allocation tracks the Ports and Adapters separation: ports (Protocols) describe what the application needs in domain terms; secondary adapters translate between vendor semantics and domain semantics; the client surface inside the adapter is the vendor-specific layer below. Putting domain translation in the adapter — not in the client — keeps the client free to be replaced on its own axis and keeps each capability's mapping policy in one place.

The contract is path-agnostic. A Path A composed-service implementation (a vendor-specific backing for a portable capability — e.g., a DynamoDB-backed `StorageService`) and a Path B feature-owned adapter (a feature whose domain is to act on a specific third-party API — e.g., the AWS Identity Center adapter in `app/packages/access/sync`) are both *secondary adapters* under this allocation. The responsibility split between client and adapter is the same in either case; only the *purpose* of the integration (per [layered-architecture.md](layered-architecture.md)) differs.

### Vendor client responsibilities

A vendor client owns transport-level and SDK-level concerns:

- **Authentication and session management.** Acquiring credentials (from environment-supplied configuration), creating and reusing authenticated sessions, refreshing tokens. Authentication is performed once per client lifetime, not per call.
- **SDK initialization.** Instantiating boto3, Google API client, Slack/Teams SDK objects with the chosen configuration (region, timeouts, retry policy). Holding those instances for reuse.
- **Retry policy and exponential backoff.** Configuring the SDK's retry mode (e.g., boto3 standard or adaptive mode) so that connection-level failures, throttling, and transient infrastructure errors are retried inside the SDK before any exception escapes. Retries are a vendor-transport concern, not a domain concern.
- **Pagination.** Iterating SDK pagination tokens to produce a complete result set; surfacing the result as a normal Python iterable. Pagination semantics are vendor-specific and do not belong in domain code.
- **Connection-level error normalization.** Letting the SDK's typed exception hierarchy through unchanged, or wrapping connection-level concerns (timeouts, DNS failures) in the SDK's own exception types. Clients do not invent a parallel error classification.
- **Concurrency and rate-limit primitives where the SDK does not provide them.** When required, applying low-level concurrency controls (semaphores, pool sizing) at the transport level.

A vendor client does **not** import `OperationResult`, define domain status values, decide what "not found" means in domain terms, or translate SDK shapes to domain types.

### Secondary adapter responsibilities

A secondary adapter — the concrete implementation of a Protocol, whether a composed-service implementation in `app/infrastructure/<service>/` or a feature-owned adapter at `app/packages/<feature>/adapters/<provider>.py` — owns the translation between vendor semantics and domain semantics:

- **Typed-exception → `OperationResult` mapping.** Catching the SDK's typed exceptions (e.g., `ClientError`, `HttpError`, `SlackApiError`) and producing the appropriate `OperationResult` status. Each adapter exposes a single point of mapping for the capability it implements; the same SDK error code does not get classified differently in two places within the same adapter.
- **Domain status assignment.** Deciding whether an SDK outcome is `SUCCESS`, `NOT_FOUND`, `TRANSIENT_ERROR`, or `PERMANENT_ERROR` *for this capability*. The same SDK error may be `NOT_FOUND` for one capability and `PERMANENT_ERROR` for another; the adapter is the place where that decision is made because the adapter is the layer that knows what the capability promises.
- **Type translation.** Converting SDK response shapes (e.g., a DynamoDB item dict, a Google API resource dict, a Slack API payload) into domain types defined by the Protocol. The Protocol's input and output types are the domain contract; the SDK's shapes never appear above the adapter.
- **Capability-level error messages.** Producing error messages and `OperationResult.metadata` content that describe the failure in terms of the capability the adapter implements, not in terms of the SDK call that produced it.

### The control-flow contract

Inside an adapter, the canonical pattern is exception-based:

```python
try:
    response = self._client.some_call(...)
except KnownDomainNotFoundException:
    return OperationResult.not_found(...)
except KnownTransientError:
    return OperationResult.transient_error(...)
except SdkClientError as e:
    return OperationResult.permanent_error(...)
return OperationResult.success(translate(response))
```

Adapters do not call `result.is_success` on a client return value. The boundary between clients and adapters is exception-based; the boundary between adapters and the application above is `OperationResult`-based.

### Replaceability axes

The contract preserves two independent replacement axes:

- **SDK or provider replacement** changes the client and the adapter together (the adapter knows how to translate the new SDK's exceptions); it does not change the Protocol or any feature code.
- **Domain mapping change** (e.g., reclassifying a specific SDK error as `TRANSIENT_ERROR` rather than `PERMANENT_ERROR` for a given capability) changes the adapter; it does not change the client or any feature code.

## Consequences

**Positive:**

- Each capability's domain mapping policy lives in one place (its adapter), making error semantics auditable and reviewable.
- Clients are idiomatic Python wrappers that engineers familiar with boto3, Google API client, or Slack SDK can read without learning a project-specific envelope at the SDK layer.
- Adapters use ordinary Python control flow (`try`/`except`) rather than nested `is_success` checks, eliminating double-wrapping.
- Clients can be upgraded or replaced independently of the adapters that consume them, provided the new client raises a comparable typed exception hierarchy.

**Tradeoffs accepted:**

- Each adapter must define its mapping table for the SDK exceptions it reasonably encounters. This is necessary structure: the mapping is the capability's domain contract for failure, and centralizing it is the value the adapter provides.
- Adapter authors must understand the SDK's typed exception hierarchy for the operations they invoke. This knowledge does not propagate beyond the adapter.

**Risks:**

- An adapter that catches a too-broad exception (e.g., `Exception`) loses the precision the contract is meant to provide. Mitigation: code review explicitly checks that adapters catch SDK-typed exceptions, not broad bases.
- Two adapters mapping the same SDK error to different `OperationResult` statuses is not a violation in itself — capabilities differ — but an unjustified divergence is a smell. Mitigation: when a mapping is non-obvious, the adapter records the rationale inline.

## Confirmation

Compliance is verified by:

- **Code review (clients).** Vendor client modules do not import `OperationResult`, do not define or reference domain status values, and do not import any module from `app/packages/` or `app/infrastructure/<service>/`. Client surfaces raise typed exceptions; their return types are SDK or domain-neutral primitives, not `OperationResult`.
- **Code review (adapters).** Each secondary adapter exposes a single, locatable mapping from SDK exceptions to `OperationResult` for the capability it implements. Adapters do not branch on `result.is_success` of a client return value.
- **Static analysis.** Import-linter (or equivalent) forbids `from ... import OperationResult` inside client modules.
- **Tests.** Adapter unit tests cover each mapped SDK exception path with a fake or stubbed client that raises the relevant SDK exception type; the test asserts the resulting `OperationResult` status. Client unit tests do not assert `OperationResult` outputs because clients do not produce them.

## Source References

1. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-04-29
   - Relevance: Establishes that the application core communicates with external systems through abstract ports, and that *adapters* — not the underlying clients and not the ports themselves — are the layer that translates between vendor semantics and application semantics. Directly supports placing typed-exception → domain-result mapping in the adapter.

2. Architecture Patterns with Python (Cosmic Python) — Repository Pattern (Chapter 2) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_02_repository.html>
   - Accessed: 2026-04-29
   - Relevance: Concrete adapters (e.g., `SqlAlchemyRepository`) live in an `adapters/` module and are permitted to import concrete storage clients directly. The adapter is the infrastructure boundary; domain and service code see only the Protocol. Models the adapter-as-translator role used in this record.

3. Architecture Patterns with Python (Cosmic Python) — Dependency Injection and Bootstrapping (Chapter 13) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_13_dependency_injection.html>
   - Accessed: 2026-04-29
   - Relevance: The composition root wires concrete adapters; client primitives are constructed once and injected into adapters. Grounds the construction-time relationship between a client and the adapter that consumes it.

4. Layers, Onions, Ports, Adapters — Mark Seemann
   - URL: <https://blog.ploeh.dk/2013/12/03/layers-onions-ports-adapters-its-all-the-same/>
   - Accessed: 2026-04-29
   - Relevance: Clarifies that adapter files at the infrastructure boundary are architecturally expected to hold and use concrete vendor types — that is the role of an adapter. The constraint applies only to inner-layer code (domain, service), which never sees the concrete adapter or its client. Grounds the asymmetry between adapter responsibilities (knows the SDK) and feature service responsibilities (knows only the Protocol).

5. PEP 544 — Protocols: Structural Subtyping (Static Duck Typing) — Python Enhancement Proposals
   - URL: <https://peps.python.org/pep-0544/>
   - Accessed: 2026-04-29
   - Relevance: Defines the `typing.Protocol` mechanism that the adapter satisfies. The Protocol's input and output types form the domain contract; the SDK's shapes do not appear in the Protocol surface and therefore do not appear in feature code.

6. Railway-Oriented Programming — Scott Wlaschin
   - URL: <https://fsharpforfunandprofit.com/rop/>
   - Accessed: 2026-04-28
   - Relevance: Establishes the use of result-typed envelopes for cross-boundary operations subject to expected failure modes. The adapter is the boundary at which the application enters this envelope; the client below it remains in idiomatic exception-based code.

7. Against Railway-Oriented Programming — Scott Wlaschin
   - URL: <https://fsharpforfunandprofit.com/posts/against-railway-oriented-programming/>
   - Accessed: 2026-04-28
   - Relevance: Argues against using result types pervasively — they belong at integration boundaries, not throughout internal code. Supports keeping `OperationResult` out of the client layer, where exception-based control flow is the natural Python idiom for SDK errors.

8. Boto3 — Retries Configuration — AWS SDK for Python
   - URL: <https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html>
   - Accessed: 2026-05-08
   - Relevance: Confirms that retry policy and exponential backoff are first-class SDK concerns configurable at client construction time. Grounds the placement of retry policy at the client layer rather than the adapter layer.

9. The Twelve-Factor App — Backing Services
   - URL: <https://12factor.net/backing-services>
   - Accessed: 2026-04-28
   - Relevance: Backing services are attached resources reachable through a uniform interface. The adapter is the layer that produces that uniform interface (the Protocol surface) regardless of which concrete client the application is configured against.

## Change Log

- 2026-05-08: Created. Establishes the responsibility contract for vendor clients (transport-level concerns including authentication, retry, pagination) and secondary adapters (typed-exception → `OperationResult` mapping, type translation, capability-level error semantics). Adopts an exception-based client surface with adapter-level translation, grounded in Ports and Adapters and the Repository Pattern. Anchored to the path-agnostic application of the contract: it applies identically to Path A composed-service implementations and Path B feature-owned adapters defined in layered-architecture.md.

---
title: "Client and Adapter Responsibilities (Draft v2)"
status: Draft
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, operation-result-pattern.md]
date: 2026-05-12
decision_makers:
  - SRE Team
---

# Client and Adapter Responsibilities (Draft v2)

## Context and Problem Statement

Clients and adapters must split concerns clearly without introducing a costly rule that every SDK method needs its own facade. The goal is consistent resilience and error semantics with maintainable integration surfaces.

## Decision Outcome

Use a layered responsibility model:

- Clients own transport concerns and resilient execution.
- Adapters own capability/domain interpretation.
- Above adapter/service boundaries, expected integration outcomes are represented as `OperationResult`.

This draft formalizes enforcement levels for implementation flexibility.

## Responsibilities

### Vendor Client Responsibilities

Clients own transport-level behavior:

- Authentication/session initialization.
- Retry/backoff/timeout behavior.
- Typed SDK exception capture.
- Exception classification into `OperationResult` status outcomes.
- Pagination and low-level transport mechanics.

Clients should expose:

1. A generic resilient executor path for broad SDK coverage.
2. Explicit convenience methods for high-traffic operations.

Clients do not own feature-domain decisions.

### Secondary Adapter Responsibilities

Adapters own domain-level interpretation:

- Convert capability semantics from client `OperationResult` into feature-level decisions.
- Perform payload translation into domain-facing types.
- Add capability-specific error context where useful.

Adapters do not reimplement retry/backoff or SDK exception handling.

## Enforcement Profile

### MUST

- Expected outbound integration outcomes MUST be normalized to `OperationResult` before crossing adapter/service boundaries.
- Services/handlers MUST not depend on vendor SDK exception classes.
- Outbound calls used by shared services MUST route through standardized resilient execution.

### SHOULD

- Shared clients SHOULD provide explicit methods for most common operations to improve discoverability and reduce stringly-typed call sites.
- New integration points SHOULD default to executor-backed client paths.

### MAY

- Feature-specific, low-frequency operations MAY use generic executor invocation instead of explicit per-method facades.
- Inbound framework registration DSLs MAY remain native (for example Slack Bolt listener registration) when no outbound transport call is being performed.

## Slack Application of This Rule

For Slack specifically:

- Do not require one-to-one facades for the entire Bolt/Web API surface.
- Require executor-backed normalization for outbound Web API calls.
- Keep listener registration native via the Slack hookspec (`register_slack_listeners`).
- Encourage feature code to send outbound messages via service/client executor paths rather than bypassing with ad hoc direct helpers.

## Consequences

### Positive

- Uniform resilience and status mapping where it matters most.
- Lower long-term maintenance cost versus exhaustive facade generation.
- Better fit for large vendor SDKs with rapidly evolving surfaces.

### Risks

- Generic executor usage can reduce type safety and autocomplete.
- Teams may accidentally bypass standardized execution if boundaries are not enforced.

### Mitigations

- Add lint/import rules for boundary enforcement.
- Add tests for executor status mapping and adapter/service exhaustive branching.
- Require review checks for new outbound integration call paths.

## Confirmation

Compliance is verified by:

- Client tests for exception-to-status mapping and retry behavior.
- Adapter tests for status interpretation by capability.
- Service/handler tests for exhaustive handling of all `OperationResult` statuses.
- Static checks preventing disallowed vendor imports in upper layers.

## Change Summary vs Accepted Record

This draft preserves the resilient-client direction and clarifies that standardization is achieved through a mandatory executor path plus boundary-level `OperationResult`, not through blanket one-to-one facades for all SDK methods.

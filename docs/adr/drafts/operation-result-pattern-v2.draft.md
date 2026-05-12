---
title: "Operation Result Pattern (Draft v2)"
status: Draft
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture, api]
constrained_by: [layered-architecture.md, type-boundaries.md, api-design-error-mapping.md, client-adapter-responsibilities.md]
date: 2026-05-12
decision_makers:
  - SRE Team
---

# Operation Result Pattern (Draft v2)

## Context and Problem Statement

The application needs one predictable outcome contract for expected outbound integration results while avoiding high-maintenance abstraction rules that force one-to-one wrappers for large SDK surfaces.

The current corpus is directionally aligned but has drift in wording about whether vendor clients may return `OperationResult`. This draft clarifies enforcement by boundary and keeps the closed status model unchanged.

## Decision Outcome

`OperationResult` remains the canonical contract for expected outbound integration outcomes, with a closed status set:

- `SUCCESS`
- `NOT_FOUND`
- `TRANSIENT_ERROR`
- `PERMANENT_ERROR`
- `UNAUTHORIZED`

The existing shape is unchanged:

- `status`
- `payload` on `SUCCESS`
- `error_code` and `message` on non-`SUCCESS`
- `retry_after` on `TRANSIENT_ERROR`

## Boundary Enforcement Levels

### MUST

- Any boundary consumed by feature services or handlers MUST expose `OperationResult` for expected integration outcomes.
- Feature service methods consumed by handlers MUST return `OperationResult` for fallible integration-backed operations.
- Handlers and transport renderers MUST map all five statuses exhaustively.
- No raw SDK exception types or vendor payload types may cross into domain/service/handler layers.

### SHOULD

- Vendor clients SHOULD return `OperationResult` via a shared executor pattern where the client surface is reused across multiple features or shared infrastructure services.
- Shared outbound operations SHOULD have explicit convenience methods for high-frequency use.

### MAY

- Low-frequency, feature-specific SDK operations MAY use a generic executor call path rather than explicit one-to-one method facades, as long as outcomes are normalized to `OperationResult` before leaving adapter/service boundaries.
- Native framework wiring APIs (for example Slack listener registration APIs) MAY remain unwrapped when they are not outbound call surfaces.

## Clarified Scope Rules

`OperationResult` appears at:

1. Client-to-adapter boundaries when a resilient client surface is used.
2. Adapter-to-feature-service boundaries.
3. Feature-service-to-handler boundaries.

`OperationResult` does not appear as:

- A wire format (HTTP/platform outputs still render to transport-specific formats).
- A domain entity type.
- A blanket return type for all internal function calls.

Internal invariant/programming failures continue to use Python exceptions.

## Slack-Specific Interpretation

This pattern does not require wrapping every Slack SDK/Bolt method.

The requirement is to standardize outbound outcome handling, not to mirror all vendor APIs:

- Outbound Web API calls must pass through resilient execution and be normalized to `OperationResult`.
- Inbound listener registration can stay native to Bolt APIs.
- Explicit facades are reserved for commonly used operations; long-tail operations can use generic executor dispatch.

## Consequences

### Positive

- Preserves exhaustive branching and stable edge mapping.
- Removes pressure to generate high-maintenance one-to-one facades for very large SDKs.
- Aligns resilience goals with practical implementation velocity.

### Tradeoffs

- Generic dispatch paths have weaker IDE discoverability than explicit methods.
- Review discipline is required to prevent bypassing the executor path.

## Confirmation

Compliance is verified by:

- Static import boundaries preventing raw vendor imports in domain/service/handler layers.
- Tests proving status mapping and exhaustive service/handler branching.
- Code review confirmation that new outbound calls route through standardized resilient execution.

## Change Summary vs Accepted Record

This draft keeps the status set and envelope shape unchanged, and updates enforcement language to a boundary-tier model (`MUST`/`SHOULD`/`MAY`) so standardization is strict where contract stability matters and flexible where blanket facades would create long-term maintenance burden.

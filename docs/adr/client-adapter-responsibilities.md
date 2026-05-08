---
title: "Client and Adapter Responsibilities"
status: Draft
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

[layered-architecture.md](layered-architecture.md) defines two distinct architectural elements that sit at the vendor boundary: **vendor clients** (pre-authenticated SDK wrappers) and **secondary adapters** (composed-service concrete implementations and feature-owned `adapters/<provider>.py` classes). The layer model says clients supply connectivity and adapters cross the layer boundary, but it does not prescribe what each is responsible for in practice. Without that contract, domain-level decisions (what a missing record means, whether an SDK error is transient, how `OperationResult` statuses are assigned) drift into the client layer, producing double-wrapping, leaked SDK semantics, and adapters that cannot use clean exception-based control flow.

The problem this record addresses: **what concerns belong in a vendor client, and what concerns belong in a secondary adapter?** The boundary must be precise enough that two engineers asked "where does this code go?" arrive at the same answer.

**Constraints:**

- TODO: List constraints that bound the solution space (e.g., `OperationResult` is the cross-layer return contract per [operation-result-pattern.md](operation-result-pattern.md); clients must remain replaceable without changing adapters or features).

**Non-goals:**

- This record does not define the `OperationResult` shape or status enum — see [operation-result-pattern.md](operation-result-pattern.md).
- This record does not decide where vendor client modules physically live — see [client-module-placement.md](client-module-placement.md).
- This record does not prescribe the Category A/B/C taxonomy — see [infrastructure-service-classification.md](infrastructure-service-classification.md).

## Considered Options

- TODO: Option 1 — Clients raise typed exceptions; adapters catch and map to `OperationResult` (Cosmic Python / Hexagonal target state).
- TODO: Option 2 — Clients return `OperationResult`; adapters re-wrap (current state — produces double-wrapping).
- TODO: Option 3 — Clients return raw SDK responses; adapters interpret entirely.

## Decision Outcome

TODO: Which option was chosen and why. Capture explicitly:

- The transport-level concerns clients own (authentication, session management, SDK initialization, retry policy, pagination, exponential backoff, connection-level error normalization).
- The domain-level concerns secondary adapters own (typed exception → `OperationResult` mapping, `NOT_FOUND` vs `PERMANENT_ERROR` semantic decisions, type translation between SDK shapes and domain types, capability-level error messages).
- The migration position toward the target state, given the current code wraps `OperationResult` at the client layer.

## Consequences

- TODO: Positive impacts (clean exception-based control flow in adapters, no double-wrapping, clients replaceable independently).
- TODO: Accepted tradeoffs (migration cost from current state).
- TODO: Risks and mitigations (partial migration creating mixed conventions).

## Confirmation

TODO: How compliance with this decision will be verified (e.g., code review checklist that clients do not import `OperationResult`; adapters define a single mapping function for SDK exceptions; test that asserts a client method raises rather than returns a wrapped failure).

## Source References

1. Architecture Patterns with Python (Cosmic Python) — Service Layer and Secondary Adapters (Chapter 4) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_04_service_layer.html>
   - Accessed: 2026-05-08
   - Relevance: Establishes that secondary (driven) adapters are the place where SDK-specific error handling and type translation belong; the application core sees only domain-level results.

2. Hexagonal Architecture / Ports and Adapters — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-05-08
   - Relevance: The adapter — not the port and not the client — is the layer that translates between vendor semantics and application semantics.

3. TODO: Add additional authoritative sources (e.g., Clean Architecture on the role of "Frameworks and Drivers"; boto3 / vendor SDK exception model documentation).

## Change Log

- 2026-05-08: Created as placeholder. Scope extracted from layered-architecture.md to govern the responsibility boundary between vendor clients and secondary adapters. Drafting deferred pending decision on target state (typed-exception model vs current `OperationResult`-at-client-layer model).

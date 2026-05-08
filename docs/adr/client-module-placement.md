---
title: "Client Module Placement"
status: Draft
type: Selection
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, import-governance.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Client Module Placement

## Context and Problem Statement

[layered-architecture.md](layered-architecture.md) defines vendor clients as a shared primitive consumed by both composed-service concrete implementations (Path A) and feature-owned outbound adapters (Path B). The layer model is independent of where client modules physically live in the source tree, but the placement choice determines whether a feature-owned adapter importing a vendor client is treated as a layer-boundary crossing or as an ordinary dependency on a shared primitive.

The problem this record addresses: **where do vendor client modules live in the source tree, and what does that placement imply for import rules?** Two candidate placements produce materially different import semantics:

- Nested under infrastructure (`app/infrastructure/clients/`): consistent with current code, but requires a "permitted exception" allowing `app/packages/<feature>/adapters/<provider>.py` to import from `app.infrastructure.clients` — a cross-layer import that is otherwise forbidden.
- Top-level sibling (`app/clients/`): clients are a cross-cutting primitive used by both layers; no exception is needed because no layer is being crossed.

**Constraints:**

- TODO: Migration cost from current placement; impact on existing import-linter configuration; impact on existing references in other ADRs and code.

**Non-goals:**

- This record does not define what clients are responsible for vs adapters — see [client-adapter-responsibilities.md](client-adapter-responsibilities.md).
- This record does not define allowed import directions in general — see [import-governance.md](import-governance.md). It only resolves the placement-dependent rule that import governance must encode.

## Considered Options

- TODO: Option 1 — Top-level `app/clients/` (sibling of `app/infrastructure/` and `app/packages/`).
- TODO: Option 2 — Status quo: nested `app/infrastructure/clients/` with a documented import exception for feature-owned adapters.
- TODO: Option 3 — Other placements (e.g., `app/infrastructure/<vendor>/clients/` per vendor).

## Decision Outcome

TODO: Which option was chosen and why. The decision must answer:

- Does a feature-owned adapter file (`app/packages/<feature>/adapters/<provider>.py`) importing a vendor client count as a layer-boundary crossing? (Top-level placement: no. Nested placement: yes, by exception.)
- What import-linter contracts encode the chosen placement?
- What migration steps (if any) are required to reach the chosen placement?

## Consequences

- TODO: Positive impacts of the chosen placement.
- TODO: Accepted tradeoffs (migration cost, churn in existing imports).
- TODO: Risks and mitigations.

## Confirmation

TODO: How compliance is verified — import-linter contracts that enforce the placement, code-review checklist for new clients.

## Source References

1. Architecture Patterns with Python (Cosmic Python) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_04_service_layer.html>
   - Accessed: 2026-05-08
   - Relevance: Cosmic Python places clients (`redis_client.py` and similar) in an `adapters/` directory at project boundary level alongside repository implementations — not nested under a "services" subdirectory. Grounds Option 1's structural argument.

2. The Clean Architecture — Robert C. Martin
   - URL: <https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html>
   - Accessed: 2026-05-08
   - Relevance: Clean Architecture places all concrete SDK dependencies in the outermost "Frameworks & Drivers" ring without a sub-ring distinction between "raw clients" and "composed-service implementations." Both placement options are compatible with Clean Architecture; the choice is structural, not principled.

3. TODO: Add additional sources as needed (e.g., import-linter documentation, prior art on client placement in Python modular monoliths).

## Change Log

- 2026-05-08: Created as placeholder. Scope extracted from layered-architecture.md, which now defers physical placement of vendor clients to this record.

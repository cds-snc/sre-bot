---
name: feature-architecture
description: Produce a feature-scoped architecture packet with complexity classification, ingress/egress contracts, error taxonomy, a TDD test matrix, and right-sized backlog tasks.
argument-hint: "[feature description]"
disable-model-invocation: true
---

# Feature Architecture Packet

Design the feature: `$ARGUMENTS`.

**Run as**: `feature-architecture` agent · Tier M (Claude Sonnet 5).
**Follow**: [implementation-planning](../implementation-planning/SKILL.md),
[type-model-boundaries](../type-model-boundaries/SKILL.md),
[fastapi-api-patterns](../fastapi-api-patterns/SKILL.md).

Translate approved app-level decisions into **one** feature-sized,
implementation-ready packet. No app-wide architecture rewrites here.

## Steps

1. Clarify the feature objective, actor journeys, and explicit out-of-scope behavior.
2. Check `decisions/` for governing ADRs and list exactly which ones apply.
3. Classify complexity — be honest, and scale the packet's depth to match:
   - **Level 1 (Simple)** — single purpose, one endpoint/command path, few schemas,
     minimal state or config.
   - **Level 2 (Standard)** — multiple paths or schemas, moderate state transitions,
     optional async/background behavior.
   - **Level 3 (Rich workflow)** — multi-step orchestration, multiple
     endpoints/channels, richer interaction surfaces (Slack/Teams/webhooks),
     policy- or config-driven behavior, cross-layer integration.
4. Define ingress and egress models, naming which boundary owns validation.
5. Define control flow and interaction layers (HTTP, background jobs, transports,
   external adapters).
6. Define the failure taxonomy and its HTTP error mapping.
7. **Level 3 only** — identify the overarching principles the feature needs and map
   each to an existing decision record or a proposed ADR update. Permanent policy
   belongs in `decisions/`, never inline in a feature packet.
8. Produce the test specification matrix: happy path, boundary, failure,
   authorization, idempotency.
9. Size the delivery against the single-PR size gate. Level 2/3 features usually
   decompose into several backlog tasks up front (expand → migrate → contract),
   each independently shippable.
10. Hand off to `/plan-task` so the packet is persisted into backlog tasks rather
    than left as chat output.

## Hard Constraints

- Full compliance with decision records, unless an explicit deviation proposal is
  included in the packet.
- Business logic in `app/packages`; shared platform capabilities in
  `app/infrastructure`; `app/modules` is never a reference.
- Plugin-registerable package design with lifespan startup assumptions.
- Type boundary rules apply to every declared contract.

## Output

Feature context and scope · applicable ADRs and derived constraints · complexity
level with rationale · ingress/egress models · interaction sequence and ownership ·
error taxonomy and API mapping · depth-appropriate design detail · acceptance
criteria · TDD test matrix · implementation handoff checklist.

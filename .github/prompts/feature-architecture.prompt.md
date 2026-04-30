---
name: feature-architecture
description: Produce a feature-scoped architecture packet with complexity classification, ingress/egress contracts, and a TDD test matrix.
agent: feature-architecture
model: GPT-5.3-Codex (copilot)
---

Produce a feature architecture packet. ADR index: [adr-index.md](../../docs/decisions/indexes/adr-index.md). Follow [copilot-instructions.md](../copilot-instructions.md).

## Output

1. Scope and assumptions.
2. Applicable ADRs cited by number.
3. Complexity classification (Level 1/2/3) with rationale.
4. Ingress/egress models typed per ADR-0065.
5. Interaction flow respecting ADR-0045 P3 unidirectional flow.
6. Error taxonomy and OperationResult mapping (ADR-0050, ADR-0060).
7. For Level 3: principles mapped to ADRs or proposed updates.
8. Acceptance criteria.
9. TDD test matrix per ADR-0062.
10. Implementation handoff checklist.

## Rules

- Feature-scoped and executable.
- Full ADR compliance; deviations must cite the ADR and propose amendment.
- Level 3: link durable policy to ADRs, not just the feature packet.
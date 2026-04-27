---
name: feature-architecture
description: Produce a feature-scoped architecture packet with complexity classification, ingress/egress contracts, and a TDD test matrix.
agent: feature-architecture
model: GPT-5.3-Codex (copilot)
---

Produce a feature architecture packet from the request.

Required output:
1. Feature scope and assumptions.
2. Applicable decision records and constraints.
3. Complexity classification (Level 1/2/3) with rationale.
4. Ingress and egress model definitions.
5. Interaction flow across layers/channels.
6. Error taxonomy and mapping.
7. For Level 3 features, overarching principles mapped to existing decision records or proposed record updates.
8. Acceptance criteria.
9. TDD test specification matrix for tests-creation.
10. Implementation handoff checklist.

Rules:
- Keep design feature-scoped and executable.
- Enforce type boundary rules and package/infrastructure boundaries.
- Full compliance with decision records unless explicit deviation proposal is required.
- For rich workflow (Level 3), do not define persistent architecture policy only in the feature packet; link policy to decision records.
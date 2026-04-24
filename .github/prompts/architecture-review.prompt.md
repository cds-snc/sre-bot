---
name: architecture-review
description: Produce architecture options, tradeoffs, and acceptance criteria before coding.
agent: architecture
model: Claude Sonnet 4.6 (copilot)
---

Review the request in architecture-first mode.

Required output:
1. Context and constraints.
2. Options considered (2-3) with tradeoffs.
3. Recommended approach and why.
4. Risks and mitigations.
5. Test strategy.
6. Implementation checklist suitable for handoff.

Rules:
- Ignore legacy app/modules patterns for architecture decisions.
- Align with app/infrastructure shared services and app/packages business domains.
- Validate settings, typing, and startup/plugin registration constraints.

---
name: feature-architecture
description: Produce a feature-scoped architecture packet with complexity classification, ingress/egress contracts, a TDD test matrix, and right-sized backlog tasks.
agent: feature-architecture
model: GPT-5.3-Codex (copilot)
---

Produce a feature architecture packet from the request, following the agent's full workflow and output contract.

Invocation notes:

- Classify complexity (Level 1/2/3) honestly; if the user says "rich", "rich workflow", or "Level 3", treat the feature as Level 3 and include orchestration boundaries, channel parity rules, and the policy/config model.
- Apply the single-PR size gate when sizing delivery; Level 2/3 features usually become multiple backlog tasks.
- Prefer the task-planner handoff so the packet is persisted into backlog tasks rather than remaining chat-only.

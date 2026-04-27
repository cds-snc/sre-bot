---
name: rich-feature-architecture
description: Produce a Level 3 rich-workflow feature architecture packet with orchestration boundaries, channel parity rules, policy/config modeling, and decision-record linkage.
agent: feature-architecture
model: GPT-5.3-Codex (copilot)
---

Produce a feature architecture packet from the request.

Treat this request as Level 3 (Rich Workflow) by default unless the user explicitly narrows scope.

Required output:
1. Feature scope, assumptions, and explicit non-goals.
2. Applicable decision records and constraints.
3. Complexity confirmation as Level 3 with rationale.
4. Ingress and egress model definitions by channel and boundary.
5. Interaction flow across HTTP endpoints, background processes, and collaboration channels.
6. Orchestration boundaries (application services, adapters, jobs, transport layers).
7. Channel parity rules (what behavior must remain consistent across HTTP, Slack, Teams, and webhooks).
8. Error taxonomy and mapping across channels.
9. Policy/config model (feature settings partitions, toggles, and ownership).
10. Overarching principles mapped to existing decision records or explicit decision-record updates.
11. Acceptance criteria.
12. TDD test specification matrix for tests-creation.
13. Implementation handoff checklist.

Rules:
- Keep design feature-scoped and executable.
- Enforce type boundary rules and package/infrastructure boundaries.
- Full compliance with decision records unless explicit deviation proposal is required.
- Do not define persistent architecture policy only in this packet; link all durable principles to decision records.
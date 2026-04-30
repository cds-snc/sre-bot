---
name: rich-feature-architecture
description: Produce a Level 3 rich-workflow feature architecture packet with orchestration boundaries, channel parity rules, policy/config modeling, and decision-record linkage.
agent: feature-architecture
model: GPT-5.3-Codex (copilot)
---

Produce a Level 3 (Rich Workflow) feature architecture packet. ADR index: [adr-index.md](../../docs/decisions/indexes/adr-index.md). Follow [copilot-instructions.md](../copilot-instructions.md).

Treat as Level 3 unless user explicitly narrows.

## Output

1. Scope, assumptions, non-goals.
2. Applicable ADRs cited by number.
3. Level 3 confirmation with rationale.
4. Ingress/egress by channel typed per ADR-0065.
5. Interaction flow: HTTP, background, collaboration channels (ADR-0045 P3).
6. Orchestration boundaries: services, adapters, jobs, transport (ADR-0059).
7. Channel parity: consistent behavior across HTTP/Slack/Teams/webhooks (ADR-0059, ADR-0078).
8. Error taxonomy across channels (ADR-0060, ADR-0050).
9. Settings partitions and ownership (ADR-0047, ADR-0055).
10. Principles mapped to ADRs or proposed updates (ADR-0051 taxonomy).
11. Acceptance criteria.
12. TDD test matrix per ADR-0062.
13. Implementation handoff checklist.

## Rules

- Feature-scoped and executable. Full ADR compliance.
- Link all durable principles to ADRs, not just this packet.
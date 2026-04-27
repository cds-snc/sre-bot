---
name: architecture-review
description: Produce app-level architecture options and source-cited decision-record updates, including mandatory web refresh for records older than 30 days.
agent: architecture
model: Claude Sonnet 4.6 (copilot)
---

Review the request in app-level architecture mode.

Required output:
1. App-level context, constraints, and non-goals.
2. Existing decision records reviewed and relevance status (include age in days).
3. Freshness audit for records older than 30 days with web validation outcomes.
4. Options considered (2-3) with tradeoffs.
5. Recommended approach and why.
6. Risks and mitigations.
7. Decision-record updates required (create/update list with sources).
8. Handoff packet for feature-level architecture.

Rules:
- Ignore legacy app/modules patterns for architecture decisions.
- Align with app/infrastructure shared services and app/packages business domains.
- Prioritize docs/decisions first; run web research for any relevant decision older than 30 days and for gaps/stale guidance.
- Include source references for every new or revised decision statement.
- Validate settings, typing, and startup/plugin registration constraints.

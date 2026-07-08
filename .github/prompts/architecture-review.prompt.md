---
name: architecture-review
description: Run app-level architecture mode on a request, producing options, source-cited decision-record updates, and backlog tasks for resulting work.
agent: architecture
model: Claude Sonnet 4.6 (copilot)
---

Review the request in app-level architecture mode and follow the agent's full workflow and output contract.

Invocation notes:

- Treat the user's input as the app-level question or change under review.
- Decision records live in `decisions/`; run the mandatory freshness audit (web-validate records older than 30 days).
- End with the decision-record update plan, backlog tasks created for resulting work, and the feature-architecture handoff packet.

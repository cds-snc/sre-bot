---
name: tdd-implementation
description: Implement approved design from existing failing tests with minimal code and quality gate verification.
agent: implementation
model: Auto (copilot)
---

Implement the approved architecture. Follow [copilot-instructions.md](../copilot-instructions.md).

## Workflow

1. Restate acceptance criteria.
2. Review existing failing tests as the contract.
3. Implement minimal code to pass tests.
4. Refactor safely.
5. Run [quality gates](./quality-gates.prompt.md).

## Rules

- Business logic in `app/packages/` only. No new logic in `app/infrastructure`.
- Do not rewrite tests unless architecture changed or tests are incorrect.
- Do not add features beyond what is needed to pass tests.
- Run gates every 3-5 edits and before completion.

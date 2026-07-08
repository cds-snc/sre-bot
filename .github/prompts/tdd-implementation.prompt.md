---
name: tdd-implementation
description: Implement approved design from existing failing tests with minimal code and quality-gate verification; supports backlog task ids as input.
agent: implementation
model: Auto (copilot)
---

Implement the approved work following the agent's full workflow and output contract.

Invocation notes:

- If the input is a backlog task id (for example `TASK-1`), read the task and its approved plan first (`backlog task view <id> --plain`); a task without an approved plan goes back to `/plan-task`.
- Existing failing tests are the contract; implement the minimal code to satisfy them, then refactor safely.
- Run the quality gates per the `python-quality-gates` skill before completion.

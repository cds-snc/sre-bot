---
name: tests-creation
description: Create or update failing behavior tests from an approved feature architecture packet or a planned backlog task.
agent: tests-creation
model: Auto (copilot)
---

Create the smallest deterministic failing test set for the approved work, following the agent's full workflow and output contract.

Invocation notes:

- If the input is a backlog task id, source acceptance criteria and the test matrix from the task's implementation plan (`backlog task view <id> --plain`).
- Cover success and failure mapping paths first; confirm each test fails for the intended reason.
- No production code, and no tests for planning-artifact wording.

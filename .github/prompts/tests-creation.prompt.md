---
name: tests-creation
description: Create or update failing tests only from approved feature architecture and acceptance criteria.
agent: tests-creation
model: Auto (copilot)
---

Create the fastest deterministic failing test set for the approved feature architecture.

Required output:
1. Test files created/updated in app/tests.
2. Acceptance criteria mapping to each test.
3. Targeted run results with intended failures.
4. Implementation backlog implied by failing assertions.

Rules:
- Do not implement production feature behavior.
- Keep tests behavior-focused and deterministic.
- Cover success and failure mapping paths first.
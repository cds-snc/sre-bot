---
name: tests-creation
description: Create or update failing behavior tests only from approved feature architecture and acceptance criteria.
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
- Do not create tests for architecture packet text, sprint naming, or transition-planning artifacts.
- Keep tests behavior-focused and deterministic.
- Cover success and failure mapping paths first.
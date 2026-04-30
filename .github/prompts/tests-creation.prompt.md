---
name: tests-creation
description: Create or update failing behavior tests only from approved feature architecture and acceptance criteria.
agent: tests-creation
model: Auto (copilot)
---

Create failing tests for the approved feature architecture. Follow the [testing-standards skill](../skills/testing-standards/SKILL.md) and [tests instructions](../instructions/tests-python.instructions.md).

## Output

1. Test files created/updated in `app/tests/`.
2. Acceptance criteria mapped to each test.
3. Targeted run results with intended failures.
4. Implementation backlog implied by failing assertions.

## Rules

- Do not implement production feature behavior.
- Do not test planning artifacts.
- Cover success, failure mapping, and dependency variation paths.
- Protocol-conformant doubles for Category A services (ADR-0077).
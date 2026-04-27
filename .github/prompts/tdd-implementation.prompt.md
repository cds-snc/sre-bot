---
name: tdd-implementation
description: Implement approved design from existing failing tests with minimal code and quality gate verification.
agent: implementation
model: Auto (copilot)
---

Implement the approved architecture using this workflow:

1. Restate acceptance criteria.
2. Review existing failing tests as the implementation contract.
3. Implement minimal code to pass tests.
4. Refactor safely.
5. Run quality gates and report outcomes.

Quality gates:
- mypy
- flake8
- black --check .
- pytest

Constraints:
- Keep business logic in app/packages.
- Avoid new business logic in app/infrastructure.
- Do not rewrite tests unless architecture changed or tests are incorrect.
- Respect type boundary rules and settings partitioning.

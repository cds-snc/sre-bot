---
name: tdd-implementation
description: Implement approved design with tests first, minimal code, and quality gate verification.
agent: implementation
model: Auto (copilot)
---

Implement the approved architecture using this workflow:

1. Restate acceptance criteria.
2. Write or update failing tests first.
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
- Respect type boundary rules and settings partitioning.

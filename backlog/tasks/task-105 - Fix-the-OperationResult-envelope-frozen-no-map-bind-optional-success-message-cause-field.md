---
id: TASK-105
title: >-
  Fix the OperationResult envelope: frozen, no map/bind, optional success
  message, cause field
status: To Do
assignee: []
created_date: '2026-09-24 19:57'
labels:
  - plugin-architecture
  - operation-result
milestone: m-7
dependencies: []
references:
  - decisions/operation-result.md
  - app/infrastructure/operations
priority: medium
type: task
ordinal: 245000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/operation-result.md lists envelope divergences to fix in one PR, independent of where the type lives. Fixing them in place before the move to app/contracts/ keeps the move purely mechanical (no refactor and behaviour change mixed in one PR).

Divergences (operation-result.md Consequences and Migration):
- the dataclass is mutable; the record requires frozen=True;
- map/bind monad helpers exist; the record removes them;
- message is required on SUCCESS; it becomes optional;
- there is no cause field (internal-only diagnostic, never rendered or serialized);
- undocumented provider/operation fields: keep and document, or drop, decided in this PR;
- a stale docstring points at the deleted ADR tree.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 OperationResult is frozen=True and a unit test asserts immutability
- [ ] #2 map and bind are removed and grep finds no .map( or .bind( call site on an OperationResult
- [ ] #3 message is optional on SUCCESS; cause exists, is excluded from repr and serialization, and is never rendered
- [ ] #4 The provider/operation fields are either documented or removed, with the choice recorded in the task notes
- [ ] #5 The shared renderers branch with match on status plus typing.assert_never, and mypy passes
- [ ] #6 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

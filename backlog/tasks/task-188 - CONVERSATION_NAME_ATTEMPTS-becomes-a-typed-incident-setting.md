---
id: TASK-188
title: CONVERSATION_NAME_ATTEMPTS becomes a typed incident setting
status: To Do
assignee: []
created_date: '2026-11-18T21:26:00Z'
labels:
  - incident
dependencies:
  - TASK-145.9.1
ordinal: 530000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
core/domain.py:549 holds CONVERSATION_NAME_ATTEMPTS = 5 as a plain constant. The rule recorded with TASK-145.9.1 (decisions/configuration.md, human 2026-11-18): plain constants are avoided unless the value must never change; a candidate-count bound is tunable, so it becomes a typed setting with default 5 on the incident settings slice, read at call time. Single small PR from main; no behaviour change at the default.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The conversation-name candidate bound is a typed setting with default 5 in config/base.toml, read at call time; the constant is deleted
- [ ] #2 ruff, mypy, lint-imports, make check-settings-key-ownership and the targeted tests pass
<!-- AC:END -->

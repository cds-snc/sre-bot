---
id: TASK-115
title: Move logging setup from app/infrastructure/logging/ to app/server/logging/
status: To Do
assignee: []
created_date: '2026-09-24 20:00'
labels:
  - plugin-architecture
  - observability
milestone: m-7
dependencies:
  - TASK-28.2
  - TASK-28.3
references:
  - decisions/plugin-architecture.md
  - decisions/observability.md
priority: medium
type: task
ordinal: 257000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md: framework services are host code, and logging setup is implemented in app/server/. infrastructure/ is hosting-only. Today the structlog pipeline configuration, redaction processor and request-context binding live in app/infrastructure/logging/, imported only by infrastructure/ and server/.

Mechanical move after the pipeline fixes that touch the same files (TASK-28.2 ProcessorFormatter, TASK-28.3 request_id middleware), so those land once in the old home instead of being rebased across a move. Features and capabilities keep logging through structlog directly and never import server/. No re-export is left in infrastructure/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Logging setup, redaction and context binding live in app/server/logging/; app/infrastructure/logging/ is deleted with no re-export
- [ ] #2 No feature, capability or integration imports server.logging; they log through structlog directly
- [ ] #3 The observability Checks still pass (redaction, UTC timestamps, single exception rendering)
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

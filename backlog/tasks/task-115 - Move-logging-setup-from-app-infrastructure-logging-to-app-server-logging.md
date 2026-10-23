---
id: TASK-115
title: Move logging setup from app/infrastructure/logging/ to app/server/logging/
status: To Do
assignee: []
created_date: 2026-09-24 20:00
updated_date: '2026-10-23T17:08:00Z'
labels:
  - plugin-architecture
  - observability
milestone: m-7
dependencies:
  - TASK-28.2
  - TASK-28.3
  - TASK-111.17
references:
  - decisions/plugin-architecture.md
  - decisions/observability.md
  - https://github.com/cds-snc/sre-bot/issues/1658
priority: medium
type: task
ordinal: 257000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md: framework services are host code, and logging setup is implemented in app/server/. infrastructure/ is hosting-only. Today the structlog pipeline configuration (setup.py), redaction and formatters (formatters.py), request-context binding (context.py) and the [logging] settings slice (settings.py) live in app/infrastructure/logging/, imported only by infrastructure/ and server/ (server/lifespan.py, server/configuration/host_configuration.py).

Mechanical move after the changes that touch the same files (TASK-111.17 configuration-phase logging, TASK-28.2 uvicorn and pre-configuration rendering, TASK-28.3 request_id middleware), so those land once in the old home instead of being rebased across a move. The move carries configure_logging(environment, logging_settings) as TASK-111.17 leaves it, with no host_info() fallback. Features and capabilities keep logging through structlog directly and never import server/. No re-export is left in infrastructure/.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Logging setup, redaction and context binding live in app/server/logging/; app/infrastructure/logging/ is deleted with no re-export
- [ ] #2 No feature, capability or integration imports server.logging; they log through structlog directly
- [ ] #3 The observability Checks still pass (redaction, UTC timestamps, single exception rendering)
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

---
id: TASK-113
title: >-
  Add the lifespan extension-point phase: collect each capability's strategies
  once at startup, in declared order, before it initializes
status: To Do
assignee: []
created_date: '2026-09-24 19:59'
labels:
  - plugin-architecture
  - plugins
  - lifecycle
milestone: m-7
dependencies:
  - TASK-107
  - TASK-110
references:
  - decisions/plugin-architecture.md
  - decisions/plugins.md
  - decisions/lifecycle.md
priority: medium
type: feature
ordinal: 255000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md, plugins.md and lifecycle.md phase 4: for each capability, in its declared order, the host calls that capability's own hookspecs once, collects the returned strategy objects (an ApprovalPolicy, an alert-action handler), and passes them to the capability before it initializes. At runtime the capability awaits the strategies' async methods. pluggy hooks are synchronous and are never called per request. A capability never initializes with an extension point still unfilled.

This replaces the in-process event bus as the way one plugin reacts to another (TASK-30 deletes the bus).

Build on demand: this lands in the same PR series as the first capability that owns hookspecs (the approvals engine, TASK-60, per the current backlog order). It carries no speculative extension point: tests use a test capability.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Lifespan runs an extension-point phase after plugin loading and before feature registration, logged with its phase name
- [ ] #2 Capabilities initialize in a declared order with no cycles; each receives the strategies collected from its own hookspecs module
- [ ] #3 Boot tests: an extension point with no registered strategy, or a strategy registration that raises, aborts boot before yield
- [ ] #4 No pluggy hook is called on the request path (review plus a test that fails if a capability hook is called after yield)
- [ ] #5 ruff, mypy (no new errors in touched files) and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

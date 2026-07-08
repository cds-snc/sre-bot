---
id: TASK-30
title: 'Rewrite the event dispatcher: owned, typed, synchronous; remove blinker'
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - infrastructure
  - phase-4
  - events
milestone: m-4
dependencies: []
references:
  - decisions/events.md
  - claude-research-outcome.md
priority: medium
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/events.md. Today app/infrastructure/events/service.py is string-keyed, blinker-backed with weak=False (disabling the very feature blinker was chosen for), and dispatches via ThreadPoolExecutor - breaking contextvars correlation inheritance. Per claude-research-outcome.md the fix is ~50 lines of owned code; no cloud service involved.

Steps:
1. New dispatcher in app/infrastructure/events/: a registry mapping event CLASSES to subscriber lists. Events are frozen dataclasses named as past-tense facts (AccessRequestApproved), carrying value types only.
2. Synchronous inline delivery on the publisher task in registration order; async subscribers awaited; per-subscriber error isolation (one exception logged with correlation, others still run).
3. Subscription via the existing startup hookspec; table frozen at yield.
4. Publish-after-commit for events describing persisted state changes (document at publish sites).
5. Migrate all publish/subscribe sites; remove blinker from dependencies; delete the ThreadPoolExecutor path.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dispatcher tests: registration order, error isolation, contextvar (request_id) inheritance into subscribers, async subscriber support
- [ ] #2 grep: no blinker imports anywhere; blinker removed from dependencies and uv.lock
- [ ] #3 No string event names at publish sites - publishing is keyed by event class
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 All existing event flows migrated; tests green
- [ ] #2 PR references decisions/events.md
<!-- DOD:END -->

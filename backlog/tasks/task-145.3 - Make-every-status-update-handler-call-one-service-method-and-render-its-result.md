---
id: TASK-145.3
title: Make every status-update handler call one service method and render its result
status: To Do
assignee: []
created_date: '2026-10-09 16:43'
updated_date: '2026-10-09 17:13'
labels:
  - incident
  - features
  - slack
dependencies:
  - TASK-145.2
parent_task_id: TASK-145
priority: high
type: task
ordinal: 353000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Layer A3 of TASK-145, in place in features/incident/scribe. Behavioural refactor of the entry point only; the modal's behaviour is unchanged.

TODAY: handle_generate_action is about 80 lines, handle_save_action and handle_status_update_command about 58, the approve submission and the published toggle chain two or three service calls, and the save failure path rebuilds a domain object with dataclasses.replace in the handler. decisions/feature-packages.md Handler discipline: receive, translate, one service call, render.

THIS SLICE
- Service results carry what the handler needs to render on failure: the save result includes the typed edit, approve_and_publish and toggle_published are single service functions returning the copy-ready text or the classified error, the overview result includes the AI-availability flag.
- Each handler: ack, parse the payload into typed values, one service call, one view builder from the outcome kind. No dataclasses.replace, no OperationResult chaining and no try/except around business outcomes in entrypoints/slack.py.
- asyncio.run stays (tolerated until TASK-33) but appears once per handler at most.
- Handler tests stub the service and assert the rendered view; service tests cover the merged paths.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No handler in scribe/entrypoints/slack.py exceeds about 30 lines or calls more than one service function
- [ ] #2 scribe/entrypoints/slack.py imports no domain constructor and does not import dataclasses.replace
- [ ] #3 approve_and_publish and toggle_published exist as single service functions with tests for success and each error outcome
- [ ] #4 The status-update modal flows (start, save, generate, approve, history, published) behave as before: existing integration tests pass with handler stubs updated only
- [ ] #5 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

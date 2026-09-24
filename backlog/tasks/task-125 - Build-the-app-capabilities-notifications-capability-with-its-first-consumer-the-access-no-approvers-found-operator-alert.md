---
id: TASK-125
title: >-
  Build the app/capabilities/notifications/ capability with its first consumer,
  the access 'no approvers found' operator alert
status: To Do
assignee: []
created_date: '2026-09-24 20:07'
labels:
  - plugin-architecture
  - capabilities
  - notifications
milestone: m-4
dependencies:
  - TASK-106
  - TASK-109
  - TASK-110
  - TASK-114
  - TASK-26.1
references:
  - decisions/plugin-architecture.md
  - decisions/platform-entrypoints.md
  - decisions/cloud-portability.md
priority: medium
type: feature
ordinal: 273000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/plugin-architecture.md lists notifications among the shared business capabilities, and decisions/platform-entrypoints.md makes "messaging people or channels outside a request" a capability with one adapter per platform. Nothing exists yet: app/infrastructure/notifications/ was a README placeholder (deleted by TASK-32). Capabilities are never built speculatively, so this one is built with its first real consumer: the access/request "no approvers found" operator alert, published today as an in-process event (TASK-30 deletes the bus).

Scope:
- create app/capabilities/notifications/ with api.py (a Protocol shaped by the operator-alert need: notify a channel or a person, with a transport-neutral message intent), a Slack adapter that sends through the Slack client factory (TASK-25.4) with a bot-scoped credential, an in-memory fake, and a README with its classification and feature consumer;
- register it through its entry point and enablement key.
Its vocabulary is the organization's (reach a person, post to a channel), not Slack's. Routing a person to their chat home arrives later with the people capability (TASK-83).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/notifications/ matches the capability layout; api.py exposes a Protocol shaped only by its first consumer's need, and its README names access as a consumer
- [ ] #2 Only adapters/ imports app.integrations; the Slack adapter classifies failures with classify_slack_error into OperationResult
- [ ] #3 An in-memory fake of the notifications Protocol lives in the package and is exercised by tests
- [ ] #4 ruff, mypy (no new errors in touched files), lint-imports and pytest tests --ignore=tests/smoke pass
<!-- AC:END -->

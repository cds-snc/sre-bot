---
id: TASK-37.3
title: 'Webhooks slice 3: transport-neutral intent + Slack renderer'
status: To Do
assignee: []
created_date: '2026-07-28 18:40'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.2
references:
  - decisions/webhooks.md
  - decisions/platform-transports.md
  - decisions/transport-slack.md
parent_task_id: TASK-37
priority: high
ordinal: 98000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of the webhooks rearchitecture (decisions/webhooks.md; coordinator TASK-37). Removes Slack coupling from the feature core and deletes the filesystem-walk pattern registries.

Goal: the interpret stage yields a transport-neutral domain intent; rendering to Slack happens ONLY in a transport renderer.

Scope:
1. domain.py: define the transport-neutral intent type(s) - e.g. NotificationRequested(title, summary, severity, links, target) plus a pass-through PostRequested for raw WebhookPayload cases. The TASK-37.2 intent-builders now emit these, never Slack blocks.
2. dispatch.py: a Slack render target mapping intent -> Slack message via the Slack transport's OperationResult->message renderer / SlackService Protocol (decisions/platform-transports.md, decisions/transport-slack.md). The feature core (schemas/service/router/domain) imports NO slack_sdk and builds NO Block Kit. If infrastructure/slack/ (the platform transport) is not yet available, use a thin local SlackPoster Protocol backed by the existing bot client via a provider, with a comment pointing at platform-transports.md - do NOT import WebClient into the feature core.
3. Move AWS-notification formatting (cloudwatch/budget/etc. -> message) behind the renderer as intent-to-message mapping; DELETE the walk registries: modules/webhooks/aws_sns_notification.py::init_notification_handlers / _load_pattern_module (os.listdir + importlib) and modules/webhooks/simple_text.py::init_pattern_handlers. Replace with the TASK-37.2 declarative source/intent table plus renderer mapping.
4. Preserve incident-button behaviour as an explicit intent/target attribute (hook_type == 'alert' -> an IncidentActionable target rendered by the Slack renderer), NOT a magic-string branch in the route.

Out of scope: cutover/delete of the legacy module directory (TASK-37.4), non-Slack sinks (TASK-37.5), HMAC (TASK-47).

Verify: the infrastructure/slack/ transport status - if the migration.md 'Slack home consolidation' has not landed, use the interim SlackPoster Protocol shim and note it in a comment.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The webhooks feature core imports no slack_sdk/WebClient and constructs no Block Kit; Slack shapes exist only behind the transport renderer (grep + review)
- [ ] #2 The interpret stage emits transport-neutral intents; the Slack renderer is the only place intents become Slack messages (test)
- [ ] #3 The os.listdir/importlib pattern-handler registries are deleted; no runtime import-string handler resolution remains under the webhooks package (grep)
- [ ] #4 Incident-button behaviour is expressed as an intent/target attribute, not a hook_type magic-string branch in the route (test)
- [ ] #5 Message output for existing SNS notification types is unchanged: TASK-36 smoke tests pass before and after
<!-- AC:END -->

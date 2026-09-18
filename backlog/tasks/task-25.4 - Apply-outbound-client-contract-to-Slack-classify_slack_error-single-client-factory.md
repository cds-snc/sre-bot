---
id: TASK-25.4
title: >-
  Apply outbound-client contract to Slack: classify_slack_error + single client
  factory
status: To Do
assignee: []
created_date: '2026-08-05 16:13'
updated_date: '2026-09-18 16:47'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-22.5
  - TASK-23
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/slack/client.py
  - app/integrations/slack/bootstrap.py
parent_task_id: TASK-25
priority: high
ordinal: 123000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply decisions/outbound-clients.md and decisions/sdk-typing.md to the Slack Web API client. Description added and scope corrected 2026-09-18 (human decision): the original AC#2 kept SlackClientManager and wrapped its callers, which would entrench a client facade that sdk-typing.md forbids.

TODAY (verified 2026-09-18). The Slack Web client is built in four places, and sdk-typing.md item 4 requires one construction path per vendor:
- app/integrations/slack/client.py: SlackClientManager, a class-level singleton that exposes get_client() -> WebClient (bot token). Its only production caller is app/integrations/slack/users.py:203.
- app/integrations/slack/bootstrap.py:48: AsyncWebClient for the Bolt AsyncApp (bot token, with slack_sdk RetryHandlers).
- app/integrations/slack/bootstrap.py:77: sync WebClient (bot token).
- app/packages/oncall_sync/providers.py:41: WebClient(token=settings.USER_TOKEN), the admin-scoped user token from TASK-71.
There is no classify_slack_error.

TARGET.
- app/integrations/slack/client.py exports factory functions for the Web client, covering bot and user tokens and sync and async as actually needed, with SDK-native RetryHandlers configured once in the factory, plus classify_slack_error.
- SlackClientManager is deleted.
- Every construction site above builds through the factory.
- Adapters that act on Slack as a target call the WebClient directly inside try/except + classify_slack_error.
- Whether a client is shared or built per use is decided and recorded (slack_sdk WebClient is safe to share across threads; say so explicitly or choose otherwise).

BOUNDARY WITH TASK-26. TASK-26 moves the transport (Bolt runtime, parser, formatter, help, commands) out of integrations/slack into infrastructure/slack and shrinks the vendor package to factory + classifier + settings. This task owns the factory and classifier that TASK-26 then relies on. The bootstrap may keep building its Bolt App where it lives today, but it gets its Web client from the factory. The planner checks the single-PR size gate and splits the work if needed (e.g. factory + classifier first, then call-site migration).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/slack/client.py exports Web client factory functions (bot/user token, sync/async as needed) with SDK-native RetryHandlers set once at construction, and classify_slack_error(exc) -> (OperationStatus, error_code, retry_after) for SlackApiError that honours Retry-After; no OperationResult in integrations/slack/client.py
- [ ] #2 SlackClientManager is deleted, and no production code outside integrations/slack/client.py calls WebClient(...) or AsyncWebClient(...) directly: bootstrap.py, users.py and packages/oncall_sync build through the factory
- [ ] #3 Every feature adapter that acts on Slack as a target (e.g. oncall_sync usergroup writes) calls the Web client directly inside try/except + classify_slack_error and returns OperationResult
- [ ] #4 classify_slack_error has unit tests: each mapped SlackApiError family -> expected status/error_code/retry_after (Retry-After honoured); one unmapped exception propagates. Factory tests assert token selection and RetryHandler wiring
- [ ] #5 No hand-rolled retry loop competes with slack_sdk's RetryHandlers (grep), and the client sharing/thread-safety choice is recorded
- [ ] #6 decisions/sdk-typing.md no longer lists SlackClientManager or multiple Slack construction paths as a tolerated divergence
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-18 16:47
---
2026-09-18 (human decision): scope corrected to match decisions/sdk-typing.md. The original AC#2 wrapped SlackClientManager.get_client() call sites, which would have kept a standing client facade. Now: delete SlackClientManager and bring all four Web-client construction sites (client.py, bootstrap.py x2, packages/oncall_sync/providers.py) onto one factory. sdk-typing.md lists this as a tolerated divergence owned by this task.
---
<!-- COMMENTS:END -->

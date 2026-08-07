---
id: TASK-25.4
title: >-
  Apply outbound-client contract to Slack: classify_slack_error + single client
  factory
status: To Do
assignee: []
created_date: '2026-08-05 16:13'
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

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 integrations/slack exports classify_slack_error(exc) -> (OperationStatus, error_code, retry_after) for SlackApiError, honoring the SDK's Retry-After header for TRANSIENT_ERROR retry_after; settings unchanged
- [ ] #2 every feature adapter that acts on Slack as a target (e.g. usergroup writes) wraps its SlackClientManager.get_client() call sites in try/except + classify_slack_error, returning OperationResult - no OperationResult inside integrations/slack/client.py itself
- [ ] #3 classify_slack_error has unit test coverage: each mapped SlackApiError family -> expected status/error_code/retry_after (incl. Retry-After honoring); one unmapped exception propagates
- [ ] #4 grep confirms no hand-rolled retry loop competes with slack_sdk's built-in RetryHandlers (bootstrap.py's existing SDK-native retry wiring is preserved, not duplicated)
<!-- AC:END -->

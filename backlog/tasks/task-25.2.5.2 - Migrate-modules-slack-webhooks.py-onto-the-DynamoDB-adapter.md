---
id: TASK-25.2.5.2
title: Migrate modules/slack/webhooks.py onto the DynamoDB adapter
status: To Do
assignee: []
created_date: '2026-09-15 20:09'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.5.1
references:
  - app/modules/slack/webhooks.py
  - app/api/v1/routes/webhooks.py
  - app/tests/modules/slack/test_slack_webhooks.py
  - app/tests/api/v1/test_webhooks.py
parent_task_id: TASK-25.2.5
priority: high
ordinal: 215000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 (migrate) of TASK-25.2.5. Moves modules/slack/webhooks.py (177 LOC) off integrations.aws.dynamodb onto build_dynamodb_adapter(). Downstream callers are unchanged: api/v1/routes/webhooks.py:98,105; modules/incident/incident_alert.py:41; modules/slack/webhooks_create.py:34; modules/slack/webhooks_list.py:183-256; modules/sre/webhook_helper.py:40,62.

Call sites (read 2026-09-15):
- create_webhook :26 put_item. Today it indexes response["ResponseMetadata"], so it crashes on False (TASK-25.2.1 item 24).
- get_webhook :53 get_item (item 26)
- lookup_webhooks :62 scan (item 27)
- increment_acknowledged_count :70 and increment_invocation_count :80 update_item "SET x = x + :inc" (item 28)
- list_all_webhooks :90 scan (item 29)
- toggle_webhook :113 get_webhook then update_item. Today it crashes on None (item 32).

Error policy (human decisions 2026-09-15):
- get_webhook, lookup_webhooks, list_all_webhooks and toggle_webhook (read and write): a non-success result logs status/error_code/error and raises RuntimeError. A missing item still returns None, and an empty scan still returns []. Visible effect: POST /hook/{id} answers a generic 5xx instead of 404 when DynamoDB fails, so SNS redelivers. Check that the 5xx body stays non-leaking (TASK-7).
- create_webhook keeps its existing failure branch: log and return None. webhooks_create already says "Something went wrong".
- The counter increments are not replay-safe, so they are sent with update_item(retries=False). A non-success result is logged and dropped (return None), so a counter never blocks webhook delivery.
- The update helpers' return values are unused by every caller, so they return None instead of the raw response.
- Raised (unclassified) errors propagate (TASK-25.2.4.x precedent).
- Dead code dropped after a re-grep confirms zero production callers: delete_webhook, revoke_webhook, is_active. validate_string_payload_type and deserialize_webhook are not DynamoDB code and stay for TASK-37.

Tests: tests/modules/slack/test_slack_webhooks.py keeps its legacy name (TASK-25.2.4 precedent). The adapter is mocked with MagicMock(spec=DynamoDBAdapter) returning OperationResult; Stubber is reserved for adapter tests. The pinned False-return tests (:268-:322) are replaced by tests of the new behaviour, and the dead helpers' tests are removed with them. Add a route test in tests/api/v1/test_webhooks.py for the lookup failure.

Overlap: TASK-37.1 later replaces this persistence with a StorageService-backed WebhookStore, so keep the diff minimal.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 modules/slack/webhooks.py no longer imports integrations.aws.dynamodb and reaches DynamoDB only through build_dynamodb_adapter() called at function entry
- [ ] #2 get_webhook, lookup_webhooks, list_all_webhooks and toggle_webhook log status, error_code and error and raise on a non-success result; a missing item returns None and an empty scan returns []
- [ ] #3 create_webhook logs and returns None on a non-success put; increment_acknowledged_count and increment_invocation_count call update_item(retries=False) and log without raising on a non-success result
- [ ] #4 POST /hook/{webhook_id} returns a non-leaking 5xx, not 404, when the webhook lookup fails, covered by a test in tests/api/v1/test_webhooks.py
- [ ] #5 delete_webhook, revoke_webhook and is_active are deleted after a re-grep confirms no production caller; the pinned False-return tests are replaced by tests of the new behaviour
- [ ] #6 Per-call-site before/after error-path behaviour is recorded in notes; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
<!-- AC:END -->

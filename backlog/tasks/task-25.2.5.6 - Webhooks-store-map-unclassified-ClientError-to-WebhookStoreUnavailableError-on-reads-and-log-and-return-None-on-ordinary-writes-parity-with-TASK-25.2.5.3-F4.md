---
id: TASK-25.2.5.6
title: >-
  Webhooks store: map unclassified ClientError to WebhookStoreUnavailableError
  on reads and log-and-return-None on ordinary writes (parity with TASK-25.2.5.3
  F4)
status: To Do
assignee: []
created_date: '2026-09-16 19:31'
updated_date: '2026-09-16 19:35'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.5.2
parent_task_id: TASK-25.2.5
priority: high
ordinal: 223000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Parity follow-up for TASK-25.2.5.2's modules/slack/webhooks.py, matching the F4 decision made on TASK-25.2.5.3 for the incident store: today an unclassified ClientError (a code the adapter's classify_aws_error does not map, e.g. ValidationException) propagates raw out of webhooks.py's read helpers (get_webhook via _get_item, lookup_webhooks, list_all_webhooks) instead of the typed WebhookStoreUnavailableError that webhooks_list.py/webhook_helper.py already catch, and out of the write helpers instead of their existing classified-failure branch (create_webhook logs and returns None; toggle_webhook's write logs and raises WebhookStoreUnavailableError). Rule: each helper's unclassified branch mirrors its own classified-failure branch. Fixing this in TASK-25.2.5.3 would pull the webhooks subsystem into that PR (size gate), so it is split out here. Call sites: modules/slack/webhooks.py's _get_item (used by get_webhook and toggle_webhook's read), lookup_webhooks, list_all_webhooks (reads); create_webhook and toggle_webhook's update_item call (writes). log_activity's counterpart, _increment_counter, already catches ClientError and is out of scope (no change). Must land before TASK-25.2.5.5 deletes integrations/aws/dynamodb.py.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _get_item, lookup_webhooks and list_all_webhooks wrap their adapter call in try/except ClientError, log the failure event with status="unclassified", error_code and error (from exc.response["Error"]), and raise WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=code) from exc instead of letting an unmapped ClientError propagate raw
- [ ] #2 Every existing webhooks_list.py/webhook_helper.py catch site (which only catches WebhookStoreUnavailableError) needs no code change, since it now also covers the unclassified case; confirmed by re-grep and by the updated test matrix
- [ ] #3 create_webhook's write catches ClientError, logs status="unclassified"/error_code/error and returns None; toggle_webhook's write catches ClientError, logs the same fields and raises WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=code) from exc — each mirrors its own classified-failure branch
- [ ] #4 Test matrix updated: an unclassified ClientError on a read raises WebhookStoreUnavailableError with PERMANENT_ERROR and error_code, logged status=unclassified (replacing any "ClientError propagates" test); on create_webhook's write it is logged and returns None; on toggle_webhook's write it is logged and raises WebhookStoreUnavailableError; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
<!-- AC:END -->

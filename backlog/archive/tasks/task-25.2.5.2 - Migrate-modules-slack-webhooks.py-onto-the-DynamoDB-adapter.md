---
id: TASK-25.2.5.2
title: Migrate modules/slack/webhooks.py onto the DynamoDB adapter
status: Done
assignee: []
created_date: '2026-09-15 20:09'
updated_date: '2026-09-16 18:00'
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
- [x] #1 modules/slack/webhooks.py no longer imports integrations.aws.dynamodb and reaches DynamoDB only through build_dynamodb_adapter() called at function entry
- [x] #2 get_webhook, lookup_webhooks, list_all_webhooks and toggle_webhook log status, error_code and error and raise on a non-success result; a missing item returns None and an empty scan returns []
- [x] #3 create_webhook logs and returns None on a non-success put; increment_acknowledged_count and increment_invocation_count call update_item(retries=False) and log without raising on a non-success result
- [x] #4 POST /hook/{webhook_id} returns a non-leaking 5xx, not 404, when the webhook lookup fails, covered by a test in tests/api/v1/test_webhooks.py
- [x] #5 delete_webhook, revoke_webhook and is_active are deleted after a re-grep confirms no production caller; the pinned False-return tests are replaced by tests of the new behaviour
- [x] #6 Per-call-site before/after error-path behaviour is recorded in notes; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUND TRUTH (read 2026-09-16): modules/slack/webhooks.py (177 LOC, full); packages/aws_platform/adapters/dynamodb.py (landed by TASK-25.2.5.1: scan/get_item/put_item/update_item(retries=) -> OperationResult, Unpack[...TypeDef] kwargs, build_dynamodb_adapter() builds 2 uncached clients per call); integrations/aws/dynamodb.py (legacy); api/v1/routes/webhooks.py (full); downstream callers modules/slack/webhooks_list.py:175-265, webhooks_create.py:25-50, modules/sre/webhook_helper.py:30-75, modules/incident/incident_alert.py:30-50; modules/aws/lambdas.py (_failure_fields idiom); tests/modules/slack/test_slack_webhooks.py (390 lines, full inventory); tests/api/v1/test_webhooks.py (fixtures, 20 tests); tests/integration/webhooks/{conftest,test_webhook_e2e}.py; TASK-25.2.5 plan + notes (incl. 2026-09-16 update adding AC#6 seam guard), TASK-25.2.5.3/.5, TASK-37.1, TASK-7; decisions/migration.md coexistence rules 1-3; pyproject [tool.mypy].

HUMAN DECISIONS 2026-09-16 (in addition to the 2026-09-15 error policy in the description, which is not re-opened)
- D1 toggle_webhook on a MISSING item (get succeeds, data None): log a warning (webhook_toggle_not_found) and return None without writing. Fixes today's TypeError.
- D2 lookup_webhooks: drop the unused field_type parameter and write {"S": value} as a literal. Reason: the adapter's typed kwargs make mypy reject the dynamic key ("Expected TypedDict key to be string literal", verified with a probe file); every production caller uses the default "S".
- D3 Type annotations only on the DynamoDB helpers this task rewrites. deserialize_webhook, decimal_default and validate_string_payload_type stay untouched (TASK-37).
- D4 Add a second route test: a failed invocation-counter write still delivers with 200.

RE-GREP (2026-09-16, rg over app/ excluding tests)
- Live: create_webhook <- webhooks_create.py:34; get_webhook <- routes/webhooks.py:98, webhooks_list.py:183,223; lookup_webhooks <- webhook_helper.py:40, webhooks_list.py:240,253 (all 2-arg, field_type never passed); list_all_webhooks <- webhook_helper.py:62, webhooks_list.py:240,256; toggle_webhook <- webhooks_list.py:232 (return unused); increment_invocation_count <- routes/webhooks.py:105 (return unused); increment_acknowledged_count <- incident_alert.py:41 (return unused).
- Dead: delete_webhook, revoke_webhook, is_active have zero production callers. Re-run the grep at implementation before deleting (AC#5).
- Test patches by name that must keep working (names unchanged): tests/integration/webhooks/conftest.py:184,202 and test_webhook_e2e.py:164,196 patch get_webhook/increment_invocation_count; test_webhooks_list.py and test_webhooks_create.py patch the helper functions, not dynamodb.

SIZE GATE: 1 production file (modules/slack/webhooks.py, about -50/+90 LOC), 2 test files, one subsystem (Slack webhooks persistence), behaviour change only (no mechanical refactor mixed in). Gate does not trip; single PR.

STEP 1 - app/modules/slack/webhooks.py
1a. Imports: remove `from integrations.aws import dynamodb`. Add `from typing import Any`, `from infrastructure.operations import OperationResult`, `from packages.aws_platform.adapters.dynamodb import DynamoDBAdapter, build_dynamodb_adapter`. Keep the other imports (TypeDeserializer, BaseModel, models, model_utils) for the untouched helpers.
1b. Add a private `_failure_fields(result: OperationResult[Any]) -> dict[str, Any]` returning status/error_code/error (copy of modules/aws/lambdas.py:19-21; siblings duplicate it privately).
1c. Add a private `_get_item(adapter: DynamoDBAdapter, id: str) -> dict[str, Any] | None`: adapter.get_item(TableName=table, Key={"id": {"S": id}}). On non-success: logger.error("webhook_get_failed", webhook_id=id, **_failure_fields(result)), then raise RuntimeError("webhooks get_item failed"). The message is generic and never result.message. Otherwise return result.data. This lets toggle_webhook share one adapter for its read and write.
1d. create_webhook(channel: str, user_id: str, name: str, hook_type: str = "alert") -> str | None: adapter = build_dynamodb_adapter() at entry, then put_item with the same Item. On non-success: logger.error("webhook_create_failed", **_failure_fields(result)) and return None. Otherwise return id. Removes the ResponseMetadata index (TASK-25.2.1 item 24).
1e. get_webhook(id: str) -> dict[str, Any] | None: return _get_item(build_dynamodb_adapter(), id). A missing item gives None; a failed read raises.
1f. lookup_webhooks(field: str, value: str) -> list[dict[str, Any]] (D2): adapter at entry; scan(TableName=table, FilterExpression=f"{field} = :{field}", ExpressionAttributeValues={f":{field}": {"S": value}}). On non-success: log "webhook_lookup_failed" with field and failure fields, then raise RuntimeError("webhooks scan failed"). Otherwise return result.data or [].
1g. increment_acknowledged_count(id: str) -> None and increment_invocation_count(id: str) -> None: adapter at entry; update_item(retries=False, same Key/UpdateExpression/ExpressionAttributeValues). On non-success: logger.error("webhook_acknowledged_count_increment_failed" / "webhook_invocation_count_increment_failed", webhook_id=id, **_failure_fields(result)) and return None. Never raise.
1h. list_all_webhooks() -> list[dict[str, Any]]: adapter at entry; scan(TableName=table, Select="ALL_ATTRIBUTES"). On non-success: log "webhook_list_failed", then raise RuntimeError. Otherwise return result.data or [].
1i. toggle_webhook(id: str) -> None: adapter at entry; webhook = _get_item(adapter, id), which raises on a failed read. If webhook is None: logger.warning("webhook_toggle_not_found", webhook_id=id) and return (D1). Otherwise update_item(TableName=table, Key=..., UpdateExpression="SET active = :active", ExpressionAttributeValues={":active": {"BOOL": not webhook["active"]["BOOL"]}}) with default retries: the precomputed SET replays safely (parent inventory). On non-success: log "webhook_toggle_failed", then raise RuntimeError.
1j. Delete delete_webhook, revoke_webhook, is_active (and the comment line above is_active) after the re-grep (AC#5).
1k. The table constant, decimal_default, deserialize_webhook and validate_string_payload_type stay unchanged.
mypy probe (2026-09-16): literal Item/Key/ExpressionAttributeValues dicts and Select="ALL_ATTRIBUTES" type-check against the adapter's Unpack kwargs; only the dynamic field_type key failed (D2).

STEP 2 - app/tests/modules/slack/test_slack_webhooks.py (legacy name kept)
Replace every @patch("modules.slack.webhooks.dynamodb") test. Patch "modules.slack.webhooks.build_dynamodb_adapter" to return MagicMock(spec=DynamoDBAdapter) whose methods return OperationResult.success(data=...) or OperationResult.error(OperationStatus.TRANSIENT_ERROR, message="boom", error_code="ThrottlingException"). Log assertions patch "modules.slack.webhooks.logger" (existing idiom in this file). Leave the 4 validate_string_payload_type tests untouched. Remove test_delete_webhook, test_revoke_webhook, test_is_active_returns_true/_false/_not_found and the 8 pinned tests at :267-:330. See TEST MATRIX.

STEP 3 - app/tests/api/v1/test_webhooks.py
- test_handle_webhook_lookup_failure_returns_generic_server_error (AC#4): patch api.v1.routes.webhooks.webhooks.get_webhook with side_effect=RuntimeError("secret-marker"), and patch increment_invocation_count. Use a dedicated TestClient(create_test_app(webhooks.router), raise_server_exceptions=False) with the bot mock on state. Assert status_code == 500 (not 404), and that the response text contains neither "secret-marker" nor "RuntimeError" (TASK-7 non-leaking). Assert increment_invocation_count is not called.
- test_handle_webhook_invocation_counter_failure_still_delivers (D4): patch get_webhook to return an active alert webhook, patch handle_webhook_payload/map_emails_to_slack_users/hydrate/log_to_sentinel/append_incident_buttons as test_handle_webhook does, and patch "modules.slack.webhooks.build_dynamodb_adapter" so update_item returns an error result. The real increment_invocation_count runs. Assert 200 {"ok": True}, that bot.client.api_call is called with chat.postMessage, and that update_item was called with retries=False.

TEST MATRIX (test_slack_webhooks.py unless noted)
AC#1/#3 create_webhook
 1 test_create_webhook_returns_id_on_success: put_item kwargs TableName="webhooks", Item shape with hook_type "alert"; returns a uuid string
 2 test_create_webhook_with_type: Item hook_type "info"
 3 test_create_webhook_returns_none_and_logs_on_failure: error result -> None; logger.error("webhook_create_failed", status=..., error_code=..., error=...)
AC#2 get_webhook
 4 test_get_webhook_returns_item: success data=item -> item; get_item Key={"id": {"S": id}}
 5 test_get_webhook_returns_none_when_absent: success data=None -> None
 6 test_get_webhook_raises_and_logs_on_failure: error -> RuntimeError; log has status/error_code/error
AC#2 lookup_webhooks
 7 test_lookup_webhooks_returns_items: scan kwargs FilterExpression "channel = :channel", ExpressionAttributeValues {":channel": {"S": value}}
 8 test_lookup_webhooks_returns_empty_list: success data=[] -> []
 9 test_lookup_webhooks_raises_and_logs_on_failure
AC#2 list_all_webhooks
 10 test_list_all_webhooks_returns_items: scan(TableName="webhooks", Select="ALL_ATTRIBUTES")
 11 test_list_all_webhooks_returns_empty_list
 12 test_list_all_webhooks_raises_and_logs_on_failure
AC#3 counters
 13 test_increment_acknowledged_count_sends_without_retries: update_item called with retries=False plus the exact expression; returns None
 14 test_increment_acknowledged_count_logs_and_returns_none_on_failure: no raise; logger.error called
 15 test_increment_invocation_count_sends_without_retries
 16 test_increment_invocation_count_logs_and_returns_none_on_failure
AC#2 toggle_webhook
 17 test_toggle_webhook_flips_active_flag: get_item data active True -> update_item ":active" {"BOOL": False}, retries not False; build_dynamodb_adapter called once
 18 test_toggle_webhook_logs_and_skips_write_when_absent (D1): data=None -> returns None, update_item not called, logger.warning("webhook_toggle_not_found")
 19 test_toggle_webhook_raises_when_read_fails: update_item not called
 20 test_toggle_webhook_raises_and_logs_when_update_fails
AC#4 (tests/api/v1/test_webhooks.py)
 21 test_handle_webhook_lookup_failure_returns_generic_server_error
 22 test_handle_webhook_invocation_counter_failure_still_delivers (D4)
Existing route tests (404 on None, disabled, success paths) stay unchanged and keep passing.

AC TRACEABILITY
- AC#1 <- Step 1a/1d-1i <- tests 1-20 (all patch build_dynamodb_adapter) + rg "integrations.aws" modules/slack/webhooks.py = 0 hits
- AC#2 <- 1c/1e/1f/1h/1i <- tests 4-12, 17-20
- AC#3 <- 1d/1g <- tests 1-3, 13-16, 22
- AC#4 <- 1c/1e + Step 3 <- test 21
- AC#5 <- 1j + Step 2 removals <- re-grep output recorded in notes
- AC#6 <- VERIFICATION + before/after table below, copied into notes

PER-CALL-SITE BEFORE/AFTER (to record in notes for AC#6; "legacy False" = handle_aws_api_errors error return)
- create_webhook: before, legacy False -> TypeError on ResponseMetadata index; non-200 dict -> None. After: non-success -> log + None (webhooks_create shows "Something went wrong").
- get_webhook: before, failure -> None -> /hook 404, webhooks_list crashes on None. After: failure -> log + RuntimeError -> /hook generic 500 (SNS redelivers), Bolt handler error; absent -> None as before.
- lookup_webhooks / list_all_webhooks: before, False passed through -> webhook_helper answers "No webhooks found" (a failure disguised as empty). After: log + RuntimeError -> Bolt error; empty -> [].
- increment_invocation_count / increment_acknowledged_count: before, retrying client (a replay could double count), False/response returned and ignored. After: retries=False, log and drop, returns None.
- toggle_webhook: before, failed or missing read -> TypeError; failed write -> None/False silently. After: failed read or write -> log + RuntimeError; missing -> warning + no-op (D1).
- delete_webhook / revoke_webhook / is_active: deleted (dead).

ASSUMPTIONS AND DOUBTS
- A1: No app exception handler converts RuntimeError (rg found only the RateLimitExceeded handler), so Starlette's ServerErrorMiddleware returns a plain "Internal Server Error" 500. Test 21 proves it; if create_test_app adds middleware that changes this, record it and assert the actual generic body.
- A2: Raising inside Bolt handlers (webhooks_list, webhook_helper) happens after ack(), so Slack shows no reply and Bolt logs the error. This is the accepted parent blast radius; the downstream handlers are not changed (description). webhooks_list.reveal_webhook/toggle_webhook still crash on a missing hook before reaching the helper; that is out of scope and noted for TASK-37.1.
- A3: The seam guard (parent AC#6) does not exist yet; .5 creates it and seeds modules/slack/webhooks.py as a consumer. Nothing to baseline in this PR.
- A4: Coexistence rule 1 (freeze): this is a persistence migration plus bug fixes with no new capability, the same shape as the TASK-25.2.4.x migrations.
- A5: The legacy test_dynamodb_local_endpoint.py and integrations/aws/dynamodb.py stay until .5.
- A6: Known order-dependent SNS/google-directory failures in the combined pytest run are pre-existing (memory: TASK-90 leaks); call them out, do not fix them.
- A7 (for TASK-25.2.5.3, not this task): db_operations.lookup_incident has the same dynamic field_type key and will hit the same mypy error.

BLAST RADIUS AND ROLLBACK
- /hook/{id}: a DynamoDB read failure now answers 500 instead of 404. SNS redelivers; other senders see a server error instead of "not found". A throttled invocation counter drops one increment but delivery continues.
- /sre webhooks list/toggle: a scan/read failure is a Bolt error instead of a misleading "No webhooks found" or a TypeError.
- Rollback: one git revert restores the legacy import (integrations/aws/dynamodb.py remains until .5). Ordering: merge before TASK-25.2.5.5.

VERIFICATION (from app/, record commands and actual output in notes)
uv run ruff check .
uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'   (no new errors vs the 85 pre-existing baseline recorded on .1)
uv run pytest tests/modules/slack tests/api/v1/test_webhooks.py tests/integration/webhooks
uv run pytest tests --ignore=tests/smoke
rg -n "integrations.aws|dynamodb\." modules/slack/webhooks.py ; rg -n "delete_webhook|revoke_webhook|is_active\(" --glob '!tests/**' .
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTATION (2026-09-16)
- app/modules/slack/webhooks.py: dropped the integrations.aws.dynamodb import. Every DynamoDB helper builds build_dynamodb_adapter() at function entry and branches on OperationResult. Adds private _failure_fields (lambdas.py idiom) and _get_item(adapter, id), so toggle_webhook uses one adapter for its read and write. The migrated helpers are annotated (D3), lookup_webhooks lost field_type (D2), and delete_webhook, revoke_webhook and is_active were deleted after a re-grep found zero production callers (AC#5). The only remaining "dynamodb" text is boto3.dynamodb.types.TypeDeserializer, which deserialize_webhook uses; it is not DynamoDB I/O.
- app/modules/slack/webhooks_list.py (human decision 2026-09-16, added during implementation): reveal_webhook and toggle_webhook now log a warning (reveal_webhook_not_found / toggle_webhook_not_found) and return when get_webhook returns None. Why: the honest dict | None annotation surfaced 7 mypy index errors at :184-186 and :224-233, which were an existing crash on a missing webhook. Rejected: loosening the annotation, or accepting the new errors.
- Tests: tests/modules/slack/test_slack_webhooks.py was rewritten (24 adapter-mock tests; the validate_string_payload_type tests are kept); tests/api/v1/test_webhooks.py gained 2 route tests, and the stale webhooks.is_active patch was removed from test_webhooks_rate_limiting; tests/modules/slack/test_webhooks_list.py gained 2 missing-webhook handler tests (written red first: TypeError 'NoneType' object is not subscriptable).

PER-CALL-SITE BEFORE/AFTER ("legacy False" = the error return of handle_aws_api_errors)
- create_webhook: before, legacy False -> TypeError on the ResponseMetadata index; a non-200 response -> None. After: non-success -> logger.error webhook_create_failed + None.
- get_webhook: before, a failure -> None -> /hook 404 (and a TypeError in webhooks_list). After: non-success -> webhook_get_failed + RuntimeError (generic message) -> /hook generic 500 so SNS redelivers, and a Bolt error in the Slack handlers; absent -> None as before.
- lookup_webhooks / list_all_webhooks: before, legacy False was passed through -> webhook_helper answered "No webhooks found" (a failure disguised as empty). After: non-success -> webhook_lookup_failed / webhook_list_failed + RuntimeError; an empty scan -> [].
- increment_invocation_count / increment_acknowledged_count: before, sent on the retrying client (a replay could double count), and the response or False was returned and ignored. After: update_item(retries=False); non-success -> webhook_*_count_increment_failed logged and dropped; return None.
- toggle_webhook: before, a failed or missing read -> TypeError; a failed write -> silently None/False. After: failed read -> webhook_get_failed + RuntimeError; missing -> webhook_toggle_not_found warning, no write; failed write -> webhook_toggle_failed + RuntimeError; returns None.
- webhooks_list.reveal_webhook / toggle_webhook: before, a missing webhook -> TypeError. After: warning + return.
- delete_webhook / revoke_webhook / is_active: deleted (dead code).

VERIFICATION (from app/)
- rg -n "integrations.aws|dynamodb\." modules/slack/webhooks.py -> only :7 from boto3.dynamodb.types import TypeDeserializer
- rg for delete_webhook|revoke_webhook|is_active over production dirs -> only unrelated directory-model is_active fields; rg "webhooks\.(delete_webhook|revoke_webhook|is_active)" tests -> no hits
- uv run ruff check . -> All checks passed!
- uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> Found 85 errors in 30 files (checked 353 source files). Same count as the baseline recorded on TASK-25.2.5.1; none are in modules/slack, api/v1/routes/webhooks.py, webhook_helper.py or incident_alert.py. (An intermediate run showed 92 before the webhooks_list guards.)
- uv run pytest tests/modules/slack tests/api/v1/test_webhooks.py tests/integration/webhooks -> 87 passed (before the 2 handler tests were added)
- uv run pytest tests --ignore=tests/smoke -> 6 failed, 3460 passed. The 6 are the known order-dependent leaks (test_webhooks_aws_sns.py x3, test_google.py x3), which are unrelated.

FOR THE HUMAN
- Review the added webhooks_list.py scope (+6 production lines), which the plan did not cover.
- The seam guard baseline (TASK-25.2.5.5) must include modules/slack/webhooks.py as a packages.aws_platform consumer.
- TASK-25.2.5.3: db_operations.lookup_incident has the same dynamic field_type key and will hit the same mypy error.

LOCAL MANUAL VERIFICATION AND COUNTER FIX (2026-09-16, human-run against dynamodb-local and dev Slack)
- Passed on the dev server: seeded hook -> 200, posted to C033L7RGCT0, invocation_count 0->1; unknown id -> 404; "Acknowledge and ignore" -> acknowledged_count +1; /dev-sre webhooks (channel and list), reveal, toggle off (404 "Webhook not active", counter unchanged) and on, create modal (both counters 0).
- FINDING (the manual step 6 test): an item without invocation_count returned HTTP 500 and nothing was posted. DynamoDB rejects "SET x = x + :inc" on a missing attribute with ValidationException. That code is unclassified, so the adapter re-raised it past the counter's OperationResult branch. Prod before this change swallowed it (legacy False), so this would have been a delivery regression for any prod item missing a counter.
- FIX (human decision 2026-09-16, "both"): a shared private _increment_counter now (1) uses "SET x = if_not_exists(x, :zero) + :inc", so a missing counter starts at 0 in the same atomic write, still with retries=False; and (2) catches a raised ClientError, logs the same failure event with status="unclassified"/error_code/error, and returns. Programmer errors still propagate. Reads keep raising (the intended 500).
- Tests (red first, 5 failing): the expression assertion was updated; added test_increment_count_logs_and_returns_none_on_unclassified_client_error x2 and test_increment_count_propagates_programmer_errors x2; the route test test_handle_webhook_invocation_counter_failure_still_delivers is now parametrized over a classified error result and an unclassified ClientError.
- Probe against real dynamodb-local: increment_invocation_count("no-counters") -> invocation_count None -> {'N': '1'}.
- Gates: ruff check . -> All checks passed!; mypy . -> Found 85 errors in 30 files (baseline, none new); pytest tests/modules/slack tests/api/v1/test_webhooks.py tests/integration/webhooks -> 94 passed; pytest tests --ignore=tests/smoke -> 6 failed, 3465 passed (the known SNS/google order-dependent leaks).
- STILL TO DO BY A HUMAN: re-run manual step 6 (expect HTTP 503 "Slack bot not initialized" on :8001) and step 5 (dead endpoint -> generic 500). Before prod, optionally run the read-only prod scan: aws dynamodb scan --table-name webhooks --select COUNT --filter-expression "attribute_not_exists(invocation_count) OR attribute_not_exists(acknowledged_count)".

- Manual step 6 re-run by a human after the fix (2026-09-16): with invocation_count removed from 'no-counters', POST :8001/hook/no-counters -> HTTP 503 {"detail":"Slack bot not initialized"} (the request got past the counter), and invocation_count null -> "1".

- Manual step 5 by a human (2026-09-16): :8001 with AWS_ENDPOINT_URL_DYNAMODB=http://dynamodb-local:1 -> POST /hook/no-counters -> HTTP 500 body 'Internal Server Error' (non-leaking). The log shows the structured webhook_get_failed (status=transient_error, error_code=EndpointConnectionError, webhook_id), then uvicorn's unstructured 'Exception in ASGI application' traceback ending in RuntimeError: webhooks get_item failed.

UNSTRUCTURED TRACEBACK FIX: HUMAN DECISIONS 2026-09-16 (after manual step 5 showed uvicorn's raw 'Exception in ASGI application' traceback)
Context: decisions/observability.md says exceptions render once, and decisions/errors-and-http.md requires explicit edge mapping, TRANSIENT_ERROR -> 503 + Retry-After and generic 5xx bodies. TASK-28 (app-wide uncaught handler, RFC 9457 helper) and TASK-28.2 (the uvicorn/stdlib pipeline) own the global fix; the human ruled the webhook instances in scope because these files are touched.
- E1: the read helpers raise a typed WebhookStoreUnavailableError (status, error_code, retry_after) instead of RuntimeError (DirectoryUsersUnavailableError precedent). This supersedes the 09-15 "raises RuntimeError" wording; the log-then-raise policy is unchanged.
- E2: POST /hook/{id} maps any lookup failure to 503 with a generic detail, plus Retry-After when retry_after is present. The failure is always server-side, so the sender should retry.
- E3: the Slack surfaces (webhooks_list.py handlers, modules/sre/webhook_helper.py) catch it and reply with a bilingual "try again later" message (modules/aws/lambdas.py precedent), so Bolt never logs a raw traceback.

- IMPLEMENTED E1-E3 (TDD: 15 tests red first with "module 'modules.slack.webhooks' has no attribute 'WebhookStoreUnavailableError'"):
  - modules/slack/webhooks.py: WebhookStoreUnavailableError(status, error_code, retry_after) with a generic message; get/lookup/list/toggle raise it after the structured log.
  - api/v1/routes/webhooks.py: catches it around get_webhook and raises HTTPException(503, "Service temporarily unavailable"), with Retry-After only when retry_after is set. The 5xx now comes from the route instead of an unhandled exception reaching uvicorn.
  - modules/slack/webhooks_list.py: STORE_UNAVAILABLE_MESSAGE (bilingual) and _store_unavailable_view(). reveal_webhook pushes it; toggle_webhook (read, toggle and refresh) and next_page replace the modal with it.
  - modules/sre/webhook_helper.py: /sre webhooks and "list" respond with the bilingual message.
  - Tests: RuntimeError assertions became the typed error, plus attribute checks; the route test is now test_handle_webhook_lookup_failure_returns_service_unavailable (with/without Retry-After, run on the default TestClient, which re-raises uncaught exceptions); 3 Slack handler tests (parametrized) in test_webhooks_list.py; 1 parametrized test in tests/unit/modules/sre/test_webhook_helper.py.
  - Not handled here (owned by TASK-28/TASK-28.2): the app-wide uncaught-exception handler, RFC 9457 bodies (a bare HTTPException is tolerated per errors-and-http.md Migration), and routing uvicorn/stdlib logs through structlog.
  - Gates: ruff check . -> All checks passed!; mypy . -> Found 85 errors in 30 files (baseline, none in touched files); pytest tests --ignore=tests/smoke -> 6 failed, 3474 passed (the known SNS/google leaks).
  - Agent live check: not possible from the agent shell (no real AWS credentials; the access-sync startup warmup fails AssumeRole with InvalidClientTokenId before serving). Manual step 5 still needs a human re-run: expect HTTP 503 and no "Exception in ASGI application" traceback.

- Manual step 5 re-run by a human after E1-E3 (2026-09-16): dead-endpoint server on :8001 -> POST /hook/no-counters -> HTTP/1.1 503 {"detail":"Service temporarily unavailable"}, no Retry-After (EndpointConnectionError has no retry_after). Server log: aws_dynamodb_operation_failed (warning) -> webhook_get_failed (error, status=transient_error, error_code=EndpointConnectionError) -> webhook_invocation -> uvicorn access line 503. No 'Exception in ASGI application' traceback. Remaining raw lines ('Found credentials in environment variables.' from botocore, the uvicorn INFO lines) are the stdlib/uvicorn pipeline gap owned by TASK-28.2.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-16 16:24
---
2026-09-16 tests authored ahead of implementation.
- tests/modules/slack/test_slack_webhooks.py: every dynamodb-patched test was replaced with 24 tests over MagicMock(spec=DynamoDBAdapter). This covers plan matrix 1-20, with the counter cases parametrized, plus test_dead_helpers_are_removed x3. The validate_string_payload_type tests are unchanged.
- tests/api/v1/test_webhooks.py: added test_handle_webhook_lookup_failure_returns_generic_server_error and test_handle_webhook_invocation_counter_failure_still_delivers.
- Plan gap found: test_webhooks_rate_limiting patched webhooks.is_active, which would raise AttributeError once is_active is deleted. That patch and its argument were removed in this pass.
Red state (uv run pytest tests/modules/slack/test_slack_webhooks.py tests/api/v1/test_webhooks.py): 4 failed, 24 passed, 20 errors.
- 21 fail with "AttributeError: modules.slack.webhooks does not have the attribute 'build_dynamodb_adapter'".
- The 3 dead-helper tests fail with "assert not True" (the helpers still exist).
- The lookup-failure route test already passes: it stubs get_webhook to raise, and the route already turns that into a generic 500. It guards the non-leaking body once get_webhook raises for real.
---
<!-- COMMENTS:END -->

---
id: TASK-25.2.5.6
title: >-
  Webhooks store: map unclassified ClientError to WebhookStoreUnavailableError
  on reads and log-and-return-None on ordinary writes (parity with TASK-25.2.5.3
  F4)
status: To Do
assignee: []
created_date: '2026-09-16 19:31'
updated_date: '2026-09-17 13:11'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.5.2
references:
  - app/modules/slack/webhooks.py
  - app/tests/modules/slack/test_slack_webhooks.py
  - app/modules/incident/db_operations.py
  - app/api/v1/routes/webhooks.py
  - app/modules/slack/webhooks_list.py
  - app/modules/sre/webhook_helper.py
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUND TRUTH (read 2026-09-17, post-TASK-25.2.5.2 `Done` and post-TASK-25.2.5.3 implementation commit d682676f). Every line below was re-read in the working tree, not recalled.

W1 -- Parity source. TASK-25.2.5.3's F4 is now implemented, so this task copies a shape that exists on disk rather than a paper decision. `db_operations.py:44-48` holds the canonical helper:
```
def _unclassified_fields(exc: ClientError) -> dict[str, Any]:
    """Return the structured log fields for a ClientError the adapter did not classify."""
    error = exc.response.get("Error", {})
    return {"status": "unclassified", "error_code": error.get("Code"), "error": error.get("Message")}
```
Its canonical read wrap is `db_operations.py:104-109` (`list_incidents`) and its canonical write wrap is `db_operations.py:80-83` (`create_incident`). This plan mirrors both verbatim in shape, substituting the webhooks event names and `WebhookStoreUnavailableError`.

W2 -- webhooks.py already has `WebhookStoreUnavailableError` (:27-39), `_unavailable` (:42-44) and `_failure_fields` (:47-49) from TASK-25.2.5.2, in the same order and shape as db_operations.py's. It is missing only `_unclassified_fields`. `from botocore.exceptions import ClientError` is ALREADY imported (:8, used by `_increment_counter`) and `from typing import Any` (:5) and `OperationStatus` (:12) are already imported -- this task adds NO new imports.

W3 -- The five in-scope call sites, re-read at HEAD:
- `_get_item` :52-58 -- `adapter.get_item`; classified branch logs `webhook_get_failed` with `webhook_id=id` then `raise _unavailable(result)`. Used by `get_webhook` (:87) and by `toggle_webhook`'s read (:158), so ONE wrap covers both read paths.
- `create_webhook` :61-82 -- `adapter.put_item` :65; classified branch logs `webhook_create_failed` (no webhook_id -- the id is not yet stored) then `return None`.
- `lookup_webhooks` :90-101 -- `adapter.scan`; classified branch logs `webhook_lookup_failed` with `field=field` then `raise _unavailable(result)`.
- `list_all_webhooks` :145-152 -- `adapter.scan`; classified branch logs `webhook_list_failed` (no extra fields) then `raise _unavailable(result)`.
- `toggle_webhook` :155-170 -- the write `adapter.update_item` :162; classified branch logs `webhook_toggle_failed` with `webhook_id=id` then `raise _unavailable(result)`.
The rule "each helper's unclassified branch mirrors its own classified-failure branch" therefore fixes every event name, every extra log field, and every outcome above without further judgement.

W4 -- `_increment_counter` :104-132 already catches `ClientError` and inlines the exact three fields `_unclassified_fields` returns (:122-128). HUMAN DECISION 2026-09-17, amending this task's description line "already catches ClientError and is out of scope (no change)": it IS changed, to call the new helper -- a pure refactor with zero behavior change, exactly as TASK-25.2.5.3's F4 did for `log_activity` ("implementation detail only, no behavior change"). Rationale: 6 call sites in webhooks.py (`_get_item`, `create_webhook`, `lookup_webhooks`, `list_all_webhooks`, `toggle_webhook`, `_increment_counter`) mirror the incident store's 6, and leaving two spellings of the same three fields in one file is the divergence this parity task exists to remove. Net effect is ~-6 LOC; its existing tests assert the resulting log call, not the extraction, so they stay green unchanged.

W5 -- AC#2 re-grep, run 2026-09-17 (`rg -n "WebhookStoreUnavailableError" --glob '!tests/**' app`). EIGHT catch sites, ALL already catching the bare `WebhookStoreUnavailableError` with no status/error_code discrimination, so all eight transparently cover the unclassified case with ZERO code change:
 1. `api/v1/routes/webhooks.py:100` (`get_webhook`) -- builds `headers = {"Retry-After": str(e.retry_after)} if e.retry_after else None`, then 503 "Service temporarily unavailable". An unclassified error carries `retry_after=None`, so the falsy branch is taken and no header is sent. That exact `retry_after=None` branch is ALREADY parametrized in `tests/api/v1/test_webhooks.py:160-188`, so the route's unclassified behavior is proven by tests that already exist and need no edit.
 2. `modules/sre/webhook_helper.py:42` (`lookup_webhooks`) -> `respond(STORE_UNAVAILABLE_MESSAGE)`.
 3. `modules/sre/webhook_helper.py:68` (`list_all_webhooks`) -> `respond(STORE_UNAVAILABLE_MESSAGE)`.
 4. `modules/slack/webhooks_list.py:201` (`get_webhook`, `reveal_webhook`) -> `views_push(_store_unavailable_view())`.
 5. `modules/slack/webhooks_list.py:248` (`get_webhook`, `toggle_webhook` handler) -> `views_update(_store_unavailable_view())`.
 6. `modules/slack/webhooks_list.py:264` (`webhooks.toggle_webhook`) -> `views_update(_store_unavailable_view())`.
 7. `modules/slack/webhooks_list.py:276` (`lookup_webhooks`/`list_all_webhooks`) -> `views_update(_store_unavailable_view())`.
 8. `modules/slack/webhooks_list.py:292` (`lookup_webhooks`/`list_all_webhooks`, `next_page`) -> `views_update(_store_unavailable_view())`.
The two write-side callers need no catch either, because the writes never raise for the unclassified case: `modules/slack/webhooks_create.py:34` already handles `create_webhook` returning None ("Something went wrong"), and `modules/incident/incident_alert.py:41` consumes `lookup_webhooks` (a read, site 2/3's shape).

W6 -- AC#4's parenthetical "(replacing any 'ClientError propagates' test)" is VACUOUS for webhooks: `rg -n "ClientError" tests/modules/slack/test_slack_webhooks.py` returns only :13 (the import) and :261/:265 (the two `_increment_counter` tests). Unlike test_db_operations.py, this file never pinned raw-propagation behavior for the read/write helpers, so the five new tests are pure additions with nothing to delete. Recorded here so the implementer does not hunt for a test that does not exist.

SIZE GATE. ONE production file (`app/modules/slack/webhooks.py`), ONE subsystem (webhooks persistence), no mechanical-refactor-plus-behavior mixing beyond W4's 6-line same-file helper extraction. Estimated production LOC: `_unclassified_fields` +5, five `try/except ClientError` wraps at ~5-6 lines each = ~28, `_increment_counter` refactor ~-6 = **~27 net / ~40 changed production LOC across 1 file**. One test file changed (`app/tests/modules/slack/test_slack_webhooks.py`, +5 tests, test churn excluded from the gate). GATE DOES NOT TRIP -- an order of magnitude under ~400 LOC / ~10 files / two subsystems. Single PR, no decomposition.

STEP 1 -- app/modules/slack/webhooks.py (the only production file)

1a. Imports: NO CHANGE. `ClientError` (:8), `Any` (:5), `OperationStatus` (:12) are all already imported and already used.

1b. After `_failure_fields` (:47-49), add the helper, byte-identical to `db_operations.py:44-48`:
```
def _unclassified_fields(exc: ClientError) -> dict[str, Any]:
    """Return the structured log fields for a ClientError the adapter did not classify."""
    error = exc.response.get("Error", {})
    return {"status": "unclassified", "error_code": error.get("Code"), "error": error.get("Message")}
```

1c. `_get_item` (read, covers `get_webhook` AND `toggle_webhook`'s read) -- wrap ONLY the adapter call:
```
def _get_item(adapter: DynamoDBAdapter, id: str) -> dict[str, Any] | None:
    """Read one webhook item; None when absent, raise when the read fails."""
    try:
        result = adapter.get_item(TableName=table, Key={"id": {"S": id}})
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        logger.error("webhook_get_failed", webhook_id=id, **fields)
        raise WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
    if not result.is_success:
        logger.error("webhook_get_failed", webhook_id=id, **_failure_fields(result))
        raise _unavailable(result)
    return result.data
```
`retry_after` is deliberately left unset (None): an unmapped code is by definition a non-retryable request/validation problem (F4's stated reasoning), and it is what makes W5 site 1 skip the `Retry-After` header.

1d. `lookup_webhooks` (read) -- same shape, event `webhook_lookup_failed`, extra field `field=field`:
```
    try:
        result = adapter.scan(
            TableName=table,
            FilterExpression=f"{field} = :{field}",
            ExpressionAttributeValues={f":{field}": {"S": value}},
        )
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        logger.error("webhook_lookup_failed", field=field, **fields)
        raise WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
```
Existing `if not result.is_success` branch and `return result.data or []` unchanged.

1e. `list_all_webhooks` (read) -- same shape, event `webhook_list_failed`, no extra field:
```
    try:
        result = adapter.scan(TableName=table, Select="ALL_ATTRIBUTES")
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        logger.error("webhook_list_failed", **fields)
        raise WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
```
Existing classified branch and `return result.data or []` unchanged.

1f. `create_webhook` (ordinary write, mirrors its own log-and-return-None branch) -- wrap ONLY `adapter.put_item`, leaving `id = str(uuid.uuid4())` and the `Item={...}` literal where they are:
```
    try:
        result = adapter.put_item(
            TableName=table,
            Item={ ... unchanged ... },
        )
    except ClientError as exc:
        logger.error("webhook_create_failed", **_unclassified_fields(exc))
        return None
```
No `fields` local here (nothing consumes `error_code` a second time) -- matches `create_incident`'s shape at `db_operations.py:80-83` exactly. Existing classified branch and `return id` unchanged.

1g. `toggle_webhook` (write, mirrors its own raise branch) -- the read half needs nothing, it goes through 1c's `_get_item`. Wrap the update:
```
    try:
        result = adapter.update_item(
            TableName=table,
            Key={"id": {"S": id}},
            UpdateExpression="SET active = :active",
            ExpressionAttributeValues={":active": {"BOOL": not webhook["active"]["BOOL"]}},
        )
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        logger.error("webhook_toggle_failed", webhook_id=id, **fields)
        raise WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
```
Existing classified branch unchanged. This helper is the one place a write raises, because its own classified branch raises -- the "mirror your own branch" rule, not an exception to it.

1h. `_increment_counter` (W4 refactor, NO behavior change) -- replace the inlined :122-128 extraction with the helper:
```
    except ClientError as exc:
        logger.error(failure_event, webhook_id=id, **_unclassified_fields(exc))
        return
```
The docstring at :105-110 stays as-is (it already explains why counters swallow unclassified errors). No other line of the function changes.

1i. Out of scope, confirmed unchanged: `decimal_default`, `deserialize_webhook`, `validate_string_payload_type`, `increment_acknowledged_count`, `increment_invocation_count`, `get_webhook`'s one-line body, and every module outside `webhooks.py` (W5).

STEP 2 -- app/tests/modules/slack/test_slack_webhooks.py (only test file changed)

Five additions, no deletions (W6). Reuse the existing `adapter` and `logger_mock` fixtures (:47-59) unchanged; `ClientError` is already imported at :13. Add module-level constants next to `FAILURE_FIELDS` (:39-43) so the five tests do not each re-spell the payload:
```
UNCLASSIFIED_ERROR = {"Error": {"Code": "ValidationException", "Message": "missing attribute"}}
UNCLASSIFIED_FIELDS = {"status": "unclassified", "error_code": "ValidationException", "error": "missing attribute"}
```
Place each new test immediately after its section's existing classified-failure test, under the existing `# -- <helper> ---` banner comments. Docstrings describe observable behavior, stub strategy and assertion rationale only (testing-standards) -- no task ids.

TEST MATRIX (file: app/tests/modules/slack/test_slack_webhooks.py)
 T1 `test_get_webhook_raises_and_logs_on_unclassified_client_error` (after :125-148). `adapter.get_item.side_effect = ClientError(UNCLASSIFIED_ERROR, "GetItem")`; `pytest.raises(webhooks.WebhookStoreUnavailableError)`; assert `.status is OperationStatus.PERMANENT_ERROR`, `.error_code == "ValidationException"`, `.retry_after is None`, `"missing attribute" not in str(exc_info.value)`; `logger_mock.error.assert_called_once_with("webhook_get_failed", webhook_id="test_id", **UNCLASSIFIED_FIELDS)`. Docstring: an unmapped SDK error must be indistinguishable to callers from a classified failure, so the eight existing catch sites cover it.
 T2 `test_lookup_webhooks_raises_and_logs_on_unclassified_client_error` (after :170). `adapter.scan.side_effect = ClientError(UNCLASSIFIED_ERROR, "Scan")`; same exception assertions; log `("webhook_lookup_failed", field="channel", **UNCLASSIFIED_FIELDS)`.
 T3 `test_list_all_webhooks_raises_and_logs_on_unclassified_client_error` (after :198). `adapter.scan.side_effect = ClientError(UNCLASSIFIED_ERROR, "Scan")`; same exception assertions; log `("webhook_list_failed", **UNCLASSIFIED_FIELDS)`.
 T4 `test_create_webhook_returns_none_and_logs_on_unclassified_client_error` (after :99-107). `adapter.put_item.side_effect = ClientError(UNCLASSIFIED_ERROR, "PutItem")`; assert the call returns None; log `("webhook_create_failed", **UNCLASSIFIED_FIELDS)`. Docstring: mirrors the classified branch -- a dropped create is reported to the user by webhooks_create, never raised.
 T5 `test_toggle_webhook_raises_and_logs_on_unclassified_client_error_on_write` (after :332-344). `adapter.get_item.return_value = OperationResult.success(data=WEBHOOK_ITEM)`; `adapter.update_item.side_effect = ClientError(UNCLASSIFIED_ERROR, "UpdateItem")`; same exception assertions; log `("webhook_toggle_failed", webhook_id="test_id", **UNCLASSIFIED_FIELDS)`.
 T6 (regression, no edit) the two `_increment_counter` tests at :251-278 and :280-292 must stay green BYTE-UNCHANGED -- that is the proof 1h's refactor is behavior-preserving. If either needs editing, 1h was done wrong.
 T7 (regression, no edit) `tests/api/v1/test_webhooks.py:160-188`'s `retry_after=None` parametrization must stay green unchanged -- it is the end-to-end proof that an unclassified read yields a 503 with no `Retry-After` header (AC#2, site 1).
 T8 (regression, no edit) every existing classified-failure test (`_failure()` / `FAILURE_FIELDS`) must stay green unchanged -- the `try/except` wraps must not disturb the `if not result.is_success` path.
NOT tested, deliberately: a "programmer error propagates" test per read/write helper. `test_increment_count_propagates_programmer_errors` (:284) already pins that `except ClientError` is narrow, and repeating it five times is churn; the incident store added such a test only where the surrounding function had no equivalent.

AC TRACEABILITY
- AC#1 (reads raise typed error, logged unclassified) <- steps 1b, 1c, 1d, 1e <- tests T1, T2, T3 (+ T8 regression).
- AC#2 (no catch site needs a code change) <- W5's eight-site re-grep table, which IS the enumeration, no step <- tests T1/T2/T3 (the raised type is the one they catch) + T7 (route end-to-end, retry_after=None branch already parametrized). Copy W5's table into the task's implementation notes at finalization.
- AC#3 (create_webhook logs + returns None; toggle_webhook's write logs + raises) <- steps 1f, 1g <- tests T4, T5.
- AC#4 (test matrix updated; gates pass with output recorded) <- step 2 and the matrix above, incl. W6's finding that there is no propagation test to replace <- VERIFICATION below, output pasted into notes.
- Step 1h (`_increment_counter` refactor) maps to no AC by design: it is W4's human-decided consistency refactor, justified as enabling work for the single-helper rule AC#1/AC#3 introduce, and pinned by T6.

VERIFICATION (run from app/, output pasted into the task's implementation notes -- evidence, not an assertion)
```
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run pytest tests --ignore=tests/smoke
```
Plus the two confirmation greps whose results belong in the notes:
```
rg -n "WebhookStoreUnavailableError" --glob '!tests/**' app          # must still be the same 8 catch sites + the 3 definition lines (AC#2)
rg -n "exc.response" app/modules/slack/webhooks.py                    # must return exactly 1 line, inside _unclassified_fields (1h done)
```
Known pre-existing condition: the single-process `pytest tests` run carries 6 SNS/google-directory ordering failures that are TASK-90 leaks, not regressions from this task -- call them out explicitly in the notes rather than fixing them here.

ASSUMPTIONS AND DOUBTS
- A1. Assumes `DynamoDBAdapter` really does re-raise an unclassified `ClientError` rather than wrapping it in an `OperationResult`. Verified indirectly: `_increment_counter` (:104-132) and `log_activity` in db_operations.py both already catch it, and TASK-25.2.5.1's Stubber tests pin it. If an implementer doubts it, re-read `packages/aws_platform/adapters/dynamodb.py`'s classification path before writing code -- do NOT rely on recall.
- A2. Assumes `OperationStatus.PERMANENT_ERROR` exists and is the right label for an unmapped code. Pinned by db_operations.py:109/:{lookup_incident} using exactly that constant, shipped in d682676f.
- A3. Assumes no catch site inspects `.status` or `.error_code` to branch. Verified: W5 read all eight; only the route touches `e.retry_after`, on a None-safe branch already under test.
- A4. Assumes `toggle_webhook`'s `SET active = :active` write is idempotent enough that it keeps SDK retries on (it sends no `retries=False`). Unchanged by this task -- flagged only so the implementer does not "fix" it here.
- A5. Ruff line length: the `raise WebhookStoreUnavailableError(...) from exc` line is long; db_operations.py:109 is the same construct and passes, so the repo's configured limit accommodates it. If ruff disagrees, wrap the arguments -- do not shorten the exception or drop `from exc`.

BLAST RADIUS AND ROLLBACK
- Behavior change is strictly narrowing: paths that previously raised a raw `ClientError` now raise `WebhookStoreUnavailableError` or return None. Nothing that previously succeeded changes, and no classified path is touched.
- User-visible effect: a `ValidationException`-class failure on `POST /hook/{id}` now answers a generic 503 (no `Retry-After`) instead of leaking a traceback to the ASGI server; `/sre webhooks` list/reveal/toggle surfaces answer the store-unavailable message instead of crashing Bolt. Confirm the 503 body stays non-leaking (TASK-7) -- T1's `"missing attribute" not in str(...)` and T7's `"ThrottlingException" not in response.text` both pin that.
- Rollback: a single `git revert` of the PR fully restores the previous behavior. One file, no schema, no config, no migration, no ordering constraint against deploys.
- Ordering constraint that DOES bind: this must merge before TASK-25.2.5.5 deletes `integrations/aws/dynamodb.py` (already wired -- TASK-25.2.5.5 lists TASK-25.2.5.6 in its `dependencies`, verified 2026-09-17). No dependency on TASK-25.2.5.3 merging first: this task touches none of its files, so the two PRs cannot conflict.
- Branch hygiene: one task, one branch, one PR. Cut this branch from main, NOT from the in-flight `feat/migrate_incident_persistence_dynamodb_adapter`.
<!-- SECTION:PLAN:END -->

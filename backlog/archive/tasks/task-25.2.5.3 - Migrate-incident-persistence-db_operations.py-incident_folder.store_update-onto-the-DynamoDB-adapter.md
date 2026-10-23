---
id: TASK-25.2.5.3
title: >-
  Migrate incident persistence (db_operations.py, incident_folder.store_update)
  onto the DynamoDB adapter
status: Done
assignee: []
created_date: '2026-09-15 20:09'
updated_date: '2026-09-17 14:00'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.2.5.1
references:
  - app/modules/incident/db_operations.py
  - app/modules/incident/incident_folder.py
  - app/modules/incident/information_display.py
  - app/modules/incident/incident_helper.py
  - app/modules/dev/incident.py
  - app/tests/modules/incident/test_db_operations.py
  - app/tests/modules/incident/test_incident_folder.py
  - app/tests/modules/incident/test_information_display.py
  - app/tests/modules/incident/test_incident_helper.py
  - app/tests/unit/modules/dev/test_dev_incident_handler.py
parent_task_id: TASK-25.2.5
priority: high
ordinal: 216000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 (migrate) of TASK-25.2.5. Moves modules/incident/db_operations.py (162 LOC) and incident_folder.py's store_update off integrations.aws.dynamodb onto build_dynamodb_adapter(). One feature domain: incident persistence (the "incidents" table) and the Slack/Bolt surfaces that read it -- the same shape TASK-25.2.5.2 used for webhooks.py + webhooks_list.py + webhook_helper.py in one task. This supersedes the 2026-09-15 "Downstream callers are unchanged" wording: information_display.py, incident_helper.py and modules/dev/incident.py are now in scope for a caller-side exception catch (see Error policy); core.py needs no change.

Call sites (read 2026-09-15):
- create_incident :40 put_item. Today it indexes response["ResponseMetadata"], so it crashes on False (TASK-25.2.1 item 33).
- list_incidents :67 scan (item 34)
- update_incident_field :90 update_item "SET #f = :f" (item 35)
- log_activity :108 update_item "SET logs = list_append(...)" (item 36)
- get_incident :138 get_item (item 37)
- lookup_incident :158 scan, reached from get_incident_by_channel_id :141, whose len() crashes on False (item 38)
- incident_folder.store_update :546 update_item "SET incident_updates = :updates". Today .get() on False crashes (item 39).

Error policy (human decisions 2026-09-16, superseding the 2026-09-15 "raises RuntimeError" wording to align this task's shape exactly with what TASK-25.2.5.2 shipped for webhooks.py):
- db_operations.py defines IncidentStoreUnavailableError(status, error_code=None, retry_after=None) with a generic message ("incidents store unavailable"), plus private _unavailable(result), _failure_fields(result) and _unclassified_fields(exc) helpers, mirroring webhooks.py:27-49. It also defines the bilingual INCIDENT_STORE_UNAVAILABLE_MESSAGE constant.
- list_incidents and lookup_incident log status/error_code/error and raise IncidentStoreUnavailableError on a non-success adapter result, INCLUDING when the adapter raises an unclassified ClientError: that path is caught, logged with status="unclassified", and re-raised as IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=...) from exc. An empty scan still returns [].
- create_incident, update_incident_field and store_update log and return None on a non-success write, INCLUDING an unclassified ClientError (caught, logged status="unclassified", return None) -- mirroring create_webhook's classified branch but closing the unclassified gap at the source, so no caller of update_incident_field (incident_status.py:59, information_update.py:322) needs a change.
- log_activity is not replay-safe, so it sends update_item(retries=False) and, mirroring webhooks._increment_counter, catches ClientError (classified or not), logging status="unclassified" for the unmapped case, and returns False with an error log on any non-success result.
- get_incident is dropped after a re-grep confirms zero production callers.
- store_update's read-modify-write race and fetch_updates's own code stay out of scope (TASK-38); fetch_updates's caller (incident_helper.display_current_updates) gets the same store-unavailable catch as the other surfaces.
- incident_folder.py drops its integrations.aws import; it duplicates the private _failure_fields and _unclassified_fields helpers for store_update's own write-failure log (it never raises IncidentStoreUnavailableError itself).
- Every Slack/Bolt surface that reaches a call that can raise IncidentStoreUnavailableError (list_incidents, lookup_incident, get_incident_by_channel_id -- directly, via create_incident's duplicate check, or via store_update's/fetch_updates' read) catches it and responds with INCIDENT_STORE_UNAVAILABLE_MESSAGE (or pushes a matching modal for open_updates_dialog, which has no `respond`). Re-grepped sites: information_display.py:17; incident_helper.py:474,619,658,696,704; modules/dev/incident.py:22,45,57,94. Two sites (core.py:303,364) already sit inside an existing broad try/except Exception and need no change. Because reads now raise the same typed error for both classified and unclassified failures, and writes never raise at all, no additional surface site is needed beyond these ten.
- ACCEPTED (modules/dev/incident.py:45, load_incidents -> create_missing_incidents): if the duplicate-check scan fails partway through a batch import, incidents already created before the failure are not rolled back. This is intentional, not a gap to close here: create_missing_incidents' own duplicate check makes a re-run of load_incidents safe (already-created incidents are found and skipped), and full rollback/transactional handling is TASK-38's.
- Webhooks parity: modules/slack/webhooks.py has the identical unclassified-ClientError gap on its reads and ordinary writes. Fixing it here would pull a second subsystem into this PR, so it is split into TASK-25.2.5.6 (parented under TASK-25.2.5, depends on TASK-25.2.5.2, and is itself a dependency of TASK-25.2.5.5 so the legacy module cannot be deleted before it lands).

Tests: tests/modules/incident/test_db_operations.py and test_incident_folder.py keep their legacy names. The adapter is mocked with MagicMock(spec=DynamoDBAdapter) returning OperationResult. The pinned tests (test_db_operations.py :209-:264, test_incident_folder.py :476) are replaced by tests of the new behaviour, and get_incident's tests are removed with it. test_information_display.py and test_incident_helper.py gain a store-unavailable test per surface site; a new tests/unit/modules/dev/test_dev_incident_handler.py (unit layer per decisions/testing.md; new files never go in legacy trees) covers modules/dev/incident.py's four sites (no prior coverage existed).

Overlap: TASK-38 later moves incident persistence into packages/incident/common, so keep the diff minimal.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 modules/incident/db_operations.py and incident_folder.py no longer import integrations.aws.dynamodb and reach DynamoDB only through build_dynamodb_adapter() called at function entry
- [x] #2 list_incidents and lookup_incident log status, error_code and error and raise IncidentStoreUnavailableError on a non-success adapter result, including when the adapter raises an unclassified ClientError (caught, logged status="unclassified", re-raised as IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=...) from exc); get_incident_by_channel_id and create_incident's duplicate check never treat a failed scan as no incident; empty scans still return []
- [x] #3 create_incident, update_incident_field and store_update log and return None on a non-success write, including an unclassified ClientError (caught, logged status="unclassified", return None), closing the gap at the source so no caller of update_incident_field needs a change; log_activity sends update_item(retries=False), catches ClientError (classified or not), and returns False with an error log on any non-success result
- [x] #4 get_incident is deleted after a re-grep confirms no production caller; the pinned False-return tests are replaced by tests of the new behaviour
- [x] #5 Every Slack/Bolt surface reaching list_incidents, lookup_incident or get_incident_by_channel_id (directly, via create_incident's duplicate check, or via store_update's/fetch_updates' read) catches IncidentStoreUnavailableError and gives the user a generic try-again-later response instead of a raw traceback, covering both classified and unclassified failures with no extra surface code; call sites already covered by an existing broad exception handler (core.py) are left unchanged and documented in notes
- [x] #6 Per-call-site before/after error-path behaviour, including the surface-handling table, is recorded in notes; ruff, mypy (no new errors) and pytest tests --ignore=tests/smoke pass with output recorded
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUND TRUTH (read 2026-09-16, v3 -- adds nothing new to v2's ground truth; F4 below is a human decision made directly on top of it, not new research).

DECISIONS 2026-09-16 (human decisions, supersede the 2026-09-15 "raises RuntimeError" and "downstream callers are unchanged" wording; align this task's shape exactly with what TASK-25.2.5.2 shipped in modules/slack/webhooks.py)

F1 -- Typed error, mirroring webhooks.py:27-49 exactly (docstring, signature, ordering):
- db_operations.py defines, right after its imports: `class IncidentStoreUnavailableError(Exception)` with `__init__(self, status: OperationStatus, error_code: str | None = None, retry_after: int | None = None) -> None`, generic message `"incidents store unavailable"`, storing `self.status`/`self.error_code`/`self.retry_after`; then `_unavailable(result: OperationResult[Any]) -> IncidentStoreUnavailableError`; then `_failure_fields(result: OperationResult[Any]) -> dict[str, Any]`.
- db_operations.py also defines `INCIDENT_STORE_UNAVAILABLE_MESSAGE`, a bilingual constant, living next to the exception since incident call sites are spread across three separate surface modules with no single natural owner (unlike webhooks_list.py for webhooks).
- incident_folder.py does NOT get its own copy of `IncidentStoreUnavailableError`/`_unavailable`: store_update's write failure logs and returns None (mirrors create_webhook, never raises), and its read failure (via `db_operations.lookup_incident`) simply propagates the exception without incident_folder.py needing to construct or reference the class. It DOES duplicate the small `_failure_fields` helper (sibling-duplication convention) because store_update logs its own write failure using the same shape; F4 below adds `_unclassified_fields` to that same duplication rule for consistency.

F2 -- Unclassified ClientError policy (ORIGINAL 2026-09-16 statement; F4 below supersedes the "reads/ordinary writes propagate it raw" part -- log_activity's rule is unchanged and still governed by F2 as written here):
- log_activity is not replay-safe, so it sends `update_item(retries=False)` and catches `ClientError` (fire-and-forget, matching webhooks' `_increment_counter`). On ClientError: log `status="unclassified"` + return False. On a non-success OperationResult: log + return False. On success: return True. (Implementation detail updated by F4: it now calls the shared `_unclassified_fields` helper instead of inlining the field extraction, since F4 gives that helper 6 call sites total.)

F3 -- Caller handling, mirroring TASK-25.2.5.2's E3 (webhooks_list.py / webhook_helper.py) exactly: every Slack/Bolt surface reaching a function that can raise `IncidentStoreUnavailableError` (list_incidents, lookup_incident, get_incident_by_channel_id -- directly, via create_incident's duplicate check, or via store_update's/fetch_updates' read) catches it at the call site (granular per-call try/except, matching webhooks_list.toggle_webhook's precedent of several try/excepts in one function) and responds instead of letting Bolt log a raw traceback. Full re-grepped enumeration and the decision for each:

 1. core.py:303 (`_create_database_record`, calls `create_incident`): already inside a local `try/except Exception` (:288-317). NO CHANGE.
 2. core.py:364 (`recreate_missing_resources`, calls `get_incident_by_channel_id`): its only caller, `incident_helper.recreate_missing_incident_resources` (:712-800), wraps the whole call in `try/except Exception`. NO CHANGE.
 3. information_display.py:17 (`open_incident_info_view`): ADD `try/except db_operations.IncidentStoreUnavailableError: respond(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE); return`.
 4. incident_helper.py:474 (`close_incident`): ADD the same catch.
 5. incident_helper.py:619 (`handle_update_status_command`): ADD the same catch.
 6. incident_helper.py:658 (`open_updates_dialog`): no `respond`; ADD a local `_store_unavailable_view() -> dict` helper (mirrors webhooks_list.py's) and, on catch, `client.views_open(trigger_id=body["trigger_id"], view=_store_unavailable_view())`.
 7. incident_helper.py:696 (`handle_updates_submission`, calls `incident_folder.store_update`): ADD a catch around the call.
 8. incident_helper.py:704 (`display_current_updates`, calls `incident_folder.fetch_updates`): ADD the same catch; `fetch_updates`'s own body stays untouched (TASK-38).
 9. modules/dev/incident.py:22 (`list_incidents`): ADD the same catch.
 10. modules/dev/incident.py:45 (`load_incidents`, calls `incident_folder.create_missing_incidents`): ADD the same catch. ACCEPTED DECISION (2026-09-16, not a caveat needing follow-up): if the duplicate-check scan fails partway through the loop, incidents already created before the failure are not rolled back. This is intentionally left as-is because `create_missing_incidents`' own duplicate check (`lookup_incident` before each `create_incident`) makes a re-run of `load_incidents` safe -- already-created incidents are found and skipped on retry, so no cleanup step is needed. Full rollback machinery belongs to TASK-38, which owns the read-modify-write/transactional concerns for this table.
 11. modules/dev/incident.py:57 (`add_incident`, calls `get_incident_by_channel_id`): ADD a catch.
 12. modules/dev/incident.py:94 (`add_incident`, calls `create_incident`): ADD a second, separate catch (granular per-call, two try/excepts in one function).

 F4 (below) closes the previously-open "unclassified ClientError from an ordinary write" gap structurally at the source (db_operations.py/incident_folder.py), so no 13th surface site is needed for that gap; re-grepped confirmation that `incident_status.py:59` and `information_update.py:322` (the two `update_incident_field` callers) need no code change is recorded under F4.

F4 -- Unclassified ClientError, closed at the source for the incident store (2026-09-16 human decision, amends F2's "propagates raw" rule for reads and ordinary writes; log_activity's own rule in F2 is unchanged since it already caught ClientError). The incident store never lets a raw ClientError the adapter doesn't classify escape to a Slack surface:
- Reads (list_incidents, lookup_incident): wrap the adapter call in `try/except ClientError`. Log the same failure event (`incident_list_failed` / `incident_lookup_failed`) with `status="unclassified"`, `error_code` and `error` (from `exc.response["Error"]`), via the shared `_unclassified_fields(exc)` helper. Then `raise IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc`. An unmapped code is by definition a non-retryable request/validation problem, so no `retry_after` is set. Every F3 surface that already catches `IncidentStoreUnavailableError` for the classified case now transparently also covers this case -- NO F3 SITE NEEDS A CODE CHANGE for this.
- Ordinary writes (create_incident, update_incident_field, store_update): catch `ClientError`, log the existing failure event with `status="unclassified"` + `error_code` + `error` via `_unclassified_fields(exc)`, and `return None` -- the same outcome as a classified non-success result. This closes the `information_update.py:322` gap (its `update_incident_field` call can no longer raise anything from an unclassified error) with NO SURFACE CHANGE there or at `incident_status.py:59`; re-grepped both call sites, neither needs a code change since they already ignore the return value.
- log_activity: unchanged from F2 (already catches ClientError; now reuses the shared helper -- implementation detail only, no behavior change).
- Only programmer errors (non-ClientError, e.g. KeyError from a malformed kwargs dict) still propagate from every function above.
- One small private helper, `_unclassified_fields(exc: ClientError) -> dict[str, Any]`, is justified now that 6 call sites need it (create_incident, list_incidents, update_incident_field, log_activity, lookup_incident in db_operations.py, plus store_update in incident_folder.py):
  ```
  def _unclassified_fields(exc: ClientError) -> dict[str, Any]:
      error = exc.response.get("Error", {})
      return {"status": "unclassified", "error_code": error.get("Code"), "error": error.get("Message")}
  ```
  Consistent with how `_failure_fields` is already handled (F1): db_operations.py owns it, incident_folder.py duplicates its own private copy for store_update rather than importing a private name across the module boundary -- same sibling-duplication convention applied to both helpers uniformly.
- Webhooks parity: `webhooks.py` has the identical gap (an unclassified ClientError propagates raw from `_get_item`/`lookup_webhooks`/`list_all_webhooks`/`create_webhook`/`toggle_webhook`). Fixing it here would pull the webhooks subsystem into this PR (size gate: two subsystems in one PR is not allowed). Split out as TASK-25.2.5.6, parented under TASK-25.2.5, depending on TASK-25.2.5.2, with the identical F4 rule applied to webhooks.py's read/write helpers. TASK-25.2.5.6 is now also a dependency of TASK-25.2.5.5 (must land before the legacy module is deleted).

SIZE GATE (v3, after F4): still 5 production files -- db_operations.py, incident_folder.py, information_display.py, incident_helper.py, modules/dev/incident.py (the latter three are UNCHANGED by F4: their F3 catches already target `IncidentStoreUnavailableError`, which F4's reads now also raise for the unclassified case, and F4's writes never raise at all, so zero additional surface-file LOC). Estimated production LOC: db_operations.py ~155 changed (v2's ~130, plus the `_unclassified_fields` helper ~4 lines and four new `try/except ClientError` wraps across create_incident/list_incidents/update_incident_field/lookup_incident, ~5-6 lines each); incident_folder.py ~40 (v2's ~30, plus store_update's `try/except ClientError` wrap and its own duplicated `_unclassified_fields` helper, ~10 lines); information_display.py ~6 (unchanged); incident_helper.py ~45 (unchanged); modules/dev/incident.py ~24 (unchanged). Total ~270 changed production LOC across the same 5 files, one feature domain. Test files: the same 5 files as v2 (test churn excluded from the gate), with a handful of test bodies changed shape (see TEST MATRIX) rather than new files added. GATE DOES NOT TRIP -- well under ~400 LOC / ~10 files / two subsystems. Single PR, no decomposition. (Webhooks parity is explicitly NOT in this PR -- TASK-25.2.5.6.)

STEP 1 -- app/modules/incident/db_operations.py
1a. Imports: remove `from integrations.aws import dynamodb`. Add `from typing import Any`, `from botocore.exceptions import ClientError`, `from infrastructure.operations import OperationResult, OperationStatus`, `from packages.aws_platform.adapters.dynamodb import build_dynamodb_adapter`. Keep `TypeSerializer`, `get_logger`, `Incident`, `datetime`.
1b. Add, mirroring webhooks.py:27-49 in order and shape, then the F4 helper:
   ```
   class IncidentStoreUnavailableError(Exception):
       """Raised when the incidents table cannot be read or updated.

       Carries the adapter's classification so callers can log or message
       accordingly; the message stays generic and never includes provider error text.
       """

       def __init__(self, status: OperationStatus, error_code: str | None = None, retry_after: int | None = None) -> None:
           super().__init__("incidents store unavailable")
           self.status = status
           self.error_code = error_code
           self.retry_after = retry_after


   def _unavailable(result: OperationResult[Any]) -> IncidentStoreUnavailableError:
       """Build the store-unavailable error from a non-success adapter result."""
       return IncidentStoreUnavailableError(result.status, error_code=result.error_code, retry_after=result.retry_after)


   def _failure_fields(result: OperationResult[Any]) -> dict[str, Any]:
       """Return the structured log fields describing a non-success adapter result."""
       return {"status": result.status.value, "error_code": result.error_code, "error": result.message}


   def _unclassified_fields(exc: ClientError) -> dict[str, Any]:
       """Return the structured log fields for a ClientError the adapter did not classify."""
       error = exc.response.get("Error", {})
       return {"status": "unclassified", "error_code": error.get("Code"), "error": error.get("Message")}


   INCIDENT_STORE_UNAVAILABLE_MESSAGE = (
       "The incidents database is temporarily unavailable. Please try again later.\n"
       "La base de donnees des incidents est temporairement indisponible. Veuillez reessayer plus tard."
   )
   ```
1c. create_incident (F4 write): unchanged duplicate-check call to `get_incident_by_channel_id`. Build `adapter = build_dynamodb_adapter()` before the put_item block:
   ```
   try:
       result = adapter.put_item(TableName="incidents", Item=serialized_data)
   except ClientError as exc:
       log.error("incident_creation_failed", **_unclassified_fields(exc))
       return None
   if not result.is_success:
       log.error("incident_creation_failed", **_failure_fields(result))
       return None
   ```
   then keep the existing success branch.
1d. list_incidents (F4 read): keep the existing `log.info("listing_incidents", ...)` line. Build the adapter:
   ```
   try:
       result = adapter.scan(TableName="incidents", Select=select, **kwargs)
   except ClientError as exc:
       fields = _unclassified_fields(exc)
       log.error("incident_list_failed", **fields)
       raise IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
   if not result.is_success:
       log.error("incident_list_failed", **_failure_fields(result))
       raise _unavailable(result)
   return result.data or []
   ```
1e. update_incident_field (F4 write; D5 from v1 unaffected -- the dynamic `type` param mypy fix stays): keep the `protected_fields` early-return. Build `attribute_value: dict[str, Any] = {type: value}` and `expression_attribute_values: dict[str, Any] = {f":{field}": attribute_value}`. Build the adapter:
   ```
   try:
       result = adapter.update_item(
           TableName="incidents", Key={"id": {"S": id}},
           UpdateExpression=f"SET #{field} = :{field}",
           ExpressionAttributeNames={f"#{field}": field},
           ExpressionAttributeValues=expression_attribute_values,
       )
   except ClientError as exc:
       log.error("incident_update_failed", **_unclassified_fields(exc))
       return None
   if not result.is_success:
       log.error("incident_update_failed", **_failure_fields(result))
       return None
   ```
   On success: keep the existing `log_activity(id, message)` fire-and-forget call, then `return None`.
1f. log_activity (F2, now reusing the F4 helper): build the adapter; send `adapter.update_item(retries=False, ...)` with the existing list_append expression, wrapped:
   ```
   try:
       result = adapter.update_item(retries=False, TableName="incidents", Key={"id": {"S": incident_id}},
           UpdateExpression="SET logs = list_append(if_not_exists(logs, :empty_list), :logs)",
           ExpressionAttributeValues={...same literal as today...}, ReturnValues="UPDATED_NEW")
   except ClientError as exc:
       log.error("activity_log_failed", **_unclassified_fields(exc))
       return False
   if not result.is_success:
       log.error("activity_log_failed", **_failure_fields(result))
       return False
   log.info("activity_logged", message=message)
   return True
   ```
1g. Delete `get_incident` (current lines 136-138) entirely (AC#4).
1h. `get_incident_by_channel_id`: no code change; now raises `IncidentStoreUnavailableError` whenever the underlying scan fails (classified or unclassified alike, per F4).
1i. lookup_incident (F4 read): drop the unused `field_type="S"` parameter. Build the adapter:
   ```
   try:
       result = adapter.scan(TableName="incidents", FilterExpression=f"{field} = :{field}", ExpressionAttributeValues={f":{field}": {"S": value}})
   except ClientError as exc:
       fields = _unclassified_fields(exc)
       log.error("incident_lookup_failed", **fields)
       raise IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
   if not result.is_success:
       log.error("incident_lookup_failed", **_failure_fields(result))
       raise _unavailable(result)
   return result.data or []
   ```
1j. Add return-type/parameter annotations only on the functions touched here: `create_incident(incident_data: dict[str, Any]) -> str | None`, `list_incidents(select: str = "ALL_ATTRIBUTES", **kwargs: Any) -> list[dict[str, Any]]`, `update_incident_field(id: str, field: str, value: Any, user_id: str, type: str = "S") -> None`, `log_activity(incident_id: str, message: str) -> bool`, `lookup_incident(field: str, value: str) -> list[dict[str, Any]]`.

STEP 2 -- app/modules/incident/incident_folder.py
2a. Imports: remove `from integrations.aws import dynamodb`. Add `from botocore.exceptions import ClientError`, `from infrastructure.operations import OperationResult` (extend the existing `OperationStatus` import line), `from packages.aws_platform.adapters.dynamodb import build_dynamodb_adapter`. No `IncidentStoreUnavailableError` import needed (F1).
2b. Add the local duplicate `_failure_fields(result: OperationResult[Any]) -> dict[str, Any]` AND `_unclassified_fields(exc: ClientError) -> dict[str, Any]` (same bodies as db_operations.py's; F1/F4's consistent least-duplication decision).
2c. store_update (F4 write): keep `existing_incident = db_operations.lookup_incident("id", incident_id)` and the `current_updates` computation unchanged (it now raises `IncidentStoreUnavailableError` on any failed scan, classified or unclassified). Build `adapter = build_dynamodb_adapter()`, then:
   ```
   try:
       result = adapter.update_item(
           TableName="incidents", Key={"id": {"S": incident_id}},
           UpdateExpression="SET incident_updates = :updates",
           ExpressionAttributeValues={":updates": {"L": current_updates}}, ReturnValues="UPDATED_NEW",
       )
   except ClientError as exc:
       logger.error("incident_update_store_failed", incident_id=incident_id, **_unclassified_fields(exc))
       return None
   if not result.is_success:
       logger.error("incident_update_store_failed", incident_id=incident_id, **_failure_fields(result))
       return None
   return None
   ```
   (replay-safe precomputed value, default `retries=True`; return None unconditionally.)
2d. Nothing else in this file changes: `create_missing_incidents` and `fetch_updates` keep calling `db_operations.lookup_incident` unmodified.

STEP 3 -- app/modules/incident/information_display.py (UNCHANGED BY F4, same as v2)
3a. Wrap `open_incident_info_view`'s `incident = db_operations.get_incident_by_channel_id(body["channel_id"])` (:17) in:
   ```
   try:
       incident = db_operations.get_incident_by_channel_id(body["channel_id"])
   except db_operations.IncidentStoreUnavailableError:
       log.error("incident_info_store_unavailable")
       respond(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)
       return
   ```

STEP 4 -- app/modules/incident/incident_helper.py (UNCHANGED BY F4, same as v2)
4a. close_incident (:474): wrap `get_incident_by_channel_id` -> `respond(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE); return`.
4b. handle_update_status_command (:619): same wrap.
4c. open_updates_dialog (:658): add local `_store_unavailable_view() -> dict` helper; on catch, `client.views_open(trigger_id=body["trigger_id"], view=_store_unavailable_view())`.
4d. handle_updates_submission (:696): wrap `incident_folder.store_update(...)` -> `respond(...)`; return.
4e. display_current_updates (:704): wrap `incident_folder.fetch_updates(...)` -> `respond(...)`; return.

STEP 5 -- app/modules/dev/incident.py (UNCHANGED BY F4, same as v2)
5a. list_incidents (:22): wrap `db_operations.list_incidents()` -> `respond(...)`; return.
5b. load_incidents (:45): wrap `incident_folder.create_missing_incidents(incidents)` -> `respond(...)`; return (accepted decision, F3 #10).
5c. add_incident (:57): wrap `db_operations.get_incident_by_channel_id(...)` -> `respond(...)`; return.
5d. add_incident (:94): wrap `db_operations.create_incident(incident_data)` in its own separate try/except -> `respond(...)`; return.

STEP 6 -- app/tests/modules/incident/test_db_operations.py (legacy name kept)
Add a pytest fixture patching `"modules.incident.db_operations.build_dynamodb_adapter"` with `MagicMock(spec=DynamoDBAdapter)`. Import `DynamoDBAdapter`, `OperationResult`/`OperationStatus`, `ClientError`, `IncidentStoreUnavailableError` from `modules.incident.db_operations`. Replace every `@patch(".dynamodb")` test with the fixture and `OperationResult.success/.error`. Keep `test_create_incident_with_invalid_data` untouched. Remove the 6 pinned/dead tests. Rewrite `test_log_activity_returns_false_and_logs_error_when_integration_returns_false`. See TEST MATRIX (updated for F4).

STEP 7 -- app/tests/modules/incident/test_incident_folder.py (legacy name kept)
Same fixture pattern, patching `"modules.incident.incident_folder.build_dynamodb_adapter"`. Replace the 3 `store_update` tests with adapter-fixture tests that also patch `"modules.incident.incident_folder.db_operations.lookup_incident"` for the read half. Fix `test_fetch_updates` to patch `db_operations.lookup_incident` instead of `dynamodb.scan`.

STEP 8 -- app/tests/modules/incident/test_information_display.py (UNCHANGED BY F4)
Extend `test_open_incident_info_view` with `test_open_incident_info_view_responds_when_store_unavailable`.

STEP 9 -- app/tests/modules/incident/test_incident_helper.py (UNCHANGED BY F4)
One store-unavailable test per F3 site #4-#8.

STEP 10 -- app/tests/unit/modules/dev/test_dev_incident_handler.py (NEW FILE, UNCHANGED BY F4)
One store-unavailable test per F3 site #9,#10,#11,#12.

TEST MATRIX (file: test_db_operations.py unless noted; F4 changes marked)
AC#1/#3 create_incident
 1 test_create_incident (rewrite): adapter.put_item.return_value = OperationResult.success(); assert kwargs; asserts incident.id returned; log_activity called.
 2 test_create_incident_with_optional_args (rewrite): same, full optional-field Item.
 3 test_create_incident_with_invalid_data: unchanged.
 4 test_create_incident_already_exists (rewrite): adapter.put_item.assert_not_called().
 5 test_create_incident_returns_none_and_logs_on_non_success_put (rewrite): OperationResult.error(...) -> None; log asserted.
 6 [F4, was "propagates"] test_create_incident_logs_and_returns_none_on_unclassified_client_error: adapter.put_item.side_effect = ClientError({"Error": {"Code": "ValidationException", "Message": "m"}}, "PutItem"); assert None returned; assert log has status="unclassified"/error_code="ValidationException"/error="m".
 7 test_create_incident_propagates_programmer_error: side_effect = KeyError; pytest.raises(KeyError).
 8 test_create_incident_propagates_when_duplicate_check_fails: patch get_incident_by_channel_id to raise IncidentStoreUnavailableError; pytest.raises(IncidentStoreUnavailableError).
AC#2 list_incidents
 9 test_list_incidents (rewrite): adapter.scan.return_value = OperationResult.success(data=[...]); assert list; assert scan kwargs.
 10 test_list_incidents_empty (rewrite): data=[] -> [].
 11 test_list_incidents_raises_and_logs_on_non_success: OperationResult.error(...) -> pytest.raises(IncidentStoreUnavailableError); assert exc carries status/error_code/retry_after; log asserted.
 12 [F4, was "propagates"] test_list_incidents_raises_incident_store_unavailable_on_unclassified_client_error: scan.side_effect=ClientError({"Error": {"Code": "ValidationException", "Message": "m"}}, "Scan"); pytest.raises(IncidentStoreUnavailableError) as exc_info; assert exc_info.value.status is OperationStatus.PERMANENT_ERROR and exc_info.value.error_code == "ValidationException" and exc_info.value.retry_after is None; assert log has status="unclassified".
 13 test_list_incidents_propagates_programmer_error: side_effect=KeyError -> pytest.raises(KeyError).
AC#3 update_incident_field
 14 test_update_incident_field (rewrite): adapter.update_item.return_value=OperationResult.success(); assert kwargs incl. ExpressionAttributeValues={":bar": {"S": "baz"}}; assert log_activity called; assert return is None.
 15 test_update_incident_field_with_type (rewrite): type="M" -> ExpressionAttributeValues={":bar": {"M": "baz"}}.
 16 test_update_incident_field_returns_none_and_logs_on_non_success (rewrite): OperationResult.error(...) -> None; log asserted; log_activity NOT called.
 17 [F4, was "propagates"] test_update_incident_field_logs_and_returns_none_on_unclassified_client_error: update_item.side_effect=ClientError(...) -> None; log status="unclassified".
 18 [new, F4] test_update_incident_field_propagates_programmer_error: update_item.side_effect=KeyError -> pytest.raises(KeyError).
 19 test_update_incident_field_protected_field_skips_write: field="id" -> adapter.update_item not called, warning logged, returns None.
AC#3 log_activity
 20 test_log_activity_sends_update_item_with_retries_false: adapter.update_item.return_value=OperationResult.success(); assert called with retries=False and the list_append expression; assert True returned.
 21 test_log_activity_returns_false_and_logs_on_non_success: OperationResult.error(...) -> False; log asserted.
 22 test_log_activity_logs_and_returns_false_on_unclassified_client_error (unchanged behavior, now via the shared helper): ClientError side_effect -> False, log status="unclassified".
 23 test_log_activity_propagates_programmer_error: side_effect=KeyError -> pytest.raises(KeyError).
AC#2 lookup_incident / get_incident_by_channel_id
 24 test_lookup_incident (rewrite): adapter.scan.return_value=OperationResult.success(data=[...]); assert scan kwargs use the literal `{"S": value}` (field_type dropped); assert returned list.
 25 test_lookup_incident_returns_empty_list_on_empty_scan: data=[] -> [].
 26 test_lookup_incident_raises_and_logs_on_non_success: error -> pytest.raises(IncidentStoreUnavailableError); logged.
 27 [F4, was "propagates"] test_lookup_incident_raises_incident_store_unavailable_on_unclassified_client_error: ClientError(...) -> pytest.raises(IncidentStoreUnavailableError) with PERMANENT_ERROR + error_code; log status="unclassified".
 28 test_lookup_incident_propagates_programmer_error: side_effect=KeyError -> pytest.raises(KeyError).
 29-31 test_get_incident_by_channel_id / _multiple_results / _no_results: unchanged.
 32 test_get_incident_by_channel_id_propagates_when_lookup_fails: patch lookup_incident with side_effect=IncidentStoreUnavailableError(...); pytest.raises(IncidentStoreUnavailableError).
AC#4: get_incident and its 2 tests deleted, no replacement.

TEST MATRIX (file: test_incident_folder.py; F4 changes marked)
AC#1/#3 store_update
 33 test_store_update_success: mock db_operations.lookup_incident -> `[{"incident_updates": {"L": [{"S": "Previous update"}]}}]`; adapter.update_item.return_value=OperationResult.success(); assert update_item kwargs; assert return is None.
 34 test_store_update_no_previous_updates: lookup_incident -> []; assert `current_updates == ""`.
 35 test_store_update_returns_none_and_logs_on_non_success: adapter.update_item.return_value=OperationResult.error(...); assert None; assert logger.error("incident_update_store_failed", ...).
 36 [F4, was "propagates"] test_store_update_logs_and_returns_none_on_unclassified_client_error: adapter.update_item.side_effect=ClientError(...); assert None; assert log status="unclassified".
 37 [new, F4] test_store_update_propagates_programmer_error: adapter.update_item.side_effect=KeyError; pytest.raises(KeyError).
 38 test_store_update_propagates_when_lookup_fails: db_operations.lookup_incident side_effect=IncidentStoreUnavailableError; pytest.raises(IncidentStoreUnavailableError); adapter.update_item.assert_not_called().
 39 test_fetch_updates (mechanical fix): patch db_operations.lookup_incident instead of dynamodb.scan; same two assertions.

TEST MATRIX (surface files, F3, UNCHANGED BY F4)
 40 test_information_display.py: test_open_incident_info_view_responds_when_store_unavailable.
 41-45 test_incident_helper.py: one test per site #4-#8.
 46-49 test_dev_incident_handler.py (new file): one test per site #9,#10,#11,#12.

AC TRACEABILITY
- AC#1 <- Steps 1a, 2a (imports) + 1c-1i, 2c (build_dynamodb_adapter() at function entry) <- `rg -n "integrations.aws" modules/incident/db_operations.py modules/incident/incident_folder.py` = 0 hits (recorded in notes).
- AC#2 <- 1d (list_incidents), 1i (lookup_incident), both now also raising on an unclassified ClientError (F4) <- tests 9-13, 24-28, 32.
- AC#3 <- 1c (create_incident), 1e (update_incident_field), 1f (log_activity), 2c (store_update), all now also catching-and-logging an unclassified ClientError (F4) <- tests 1-8, 14-23, 33-38.
- AC#4 <- 1g (delete get_incident) <- re-grep recorded in notes; its 2 tests removed, no replacement.
- AC#5 (surface handling) <- Steps 3, 4, 5 (12 call sites, 10 changed + 2 already-safe); F4 confirms no 13th site is needed for the write-side gap (re-grep of incident_status.py:59, information_update.py:322 recorded in notes) <- tests 40-49.
- AC#6 <- PER-CALL-SITE BEFORE/AFTER table below plus the F3/F4 enumeration, copied into notes at finalization, plus VERIFICATION output.

PER-CALL-SITE BEFORE/AFTER (record in notes for AC#6; "legacy False" = the integration's real failure-mode return)
- create_incident: before, a legacy False crashes on the unguarded `response["ResponseMetadata"]` index; a 400-status dict logs and returns None. After: non-success (classified OR an unclassified ClientError, F4) -> log `incident_creation_failed` + return None. Its duplicate-check read (get_incident_by_channel_id) now raises `IncidentStoreUnavailableError` on a failed scan instead of silently treating the failure as "no duplicate".
- list_incidents: before, a pure pass-through -- a legacy False reaches `modules/dev/incident.py:22`'s `len(incidents)` and crashes with a TypeError. After: non-success (classified OR unclassified, F4) -> log `incident_list_failed` + raise `IncidentStoreUnavailableError` (caught at :22 and answered with the generic message); an empty scan still returns [].
- update_incident_field: before, a legacy None/falsy response is swallowed silently (no log). After: non-success (classified OR unclassified, F4) -> log `incident_update_failed` + return None; no caller needs a catch (F4 closes the `information_update.py:322`/`incident_status.py:59` gap at the source). The dynamic `type` param keeps working via the `dict[str, Any]` typing fix.
- log_activity: before, a legacy falsy response logs `activity_log_failed` and returns False. After: same contract; also catches an unclassified ClientError (log status="unclassified", return False) instead of crashing `create_incident`/`create_missing_incidents`; the write goes out with `retries=False`.
- get_incident: deleted (dead code, zero production callers).
- lookup_incident / get_incident_by_channel_id: before, a legacy False crashes `incident_folder.py:493`'s unguarded `len(incident_exists)` and `db_operations.py:150`'s `len(incidents)`. After: non-success (classified OR unclassified, F4) -> log `incident_lookup_failed` + raise `IncidentStoreUnavailableError`, caught at every Slack/Bolt surface (F3 sites #3-#12) and answered with the generic message instead of a raw traceback; an empty scan still returns [] / None. field_type param dropped.
- incident_folder.store_update: before, a legacy False crashes on the unguarded `response.get("ResponseMetadata", {})` call; a 400-status dict returns None silently (no log). After: non-success (classified OR unclassified, F4) -> log `incident_update_store_failed` + return None; its read half (lookup_incident) now raises and is caught at incident_helper.py:696. Return value is now always None.
- Slack/Bolt surfaces (F3): 10 of 12 re-grepped call sites gain an explicit catch-and-respond (or catch-and-push-modal for open_updates_dialog); 2 (core.py:303,364) already had adequate broad exception handling and are unchanged. F4 needs zero additional surface sites: reads' unclassified case raises the same typed exception the F3 catches already target, and ordinary writes never raise at all.
- Webhooks (modules/slack/webhooks.py): same unclassified-ClientError gap exists today, split into TASK-25.2.5.6 rather than fixed here (size gate).

BLAST RADIUS AND ROLLBACK
- Slack `/sre` incident commands and view-submission handlers now answer with a clean, generic "try again later" message (bilingual) instead of a TypeError/AttributeError or a raw unhandled traceback reaching Bolt, whenever ANY DynamoDB read failure hits -- classified or an unmapped ClientError code alike (F4 removes the previous "unclassified still crashes" gap for reads).
- `create_missing_incidents`'s duplicate check no longer creates a second incident record when the duplicate-check scan itself fails.
- A throttled/unclassified `log_activity`, `create_incident`, `update_incident_field` or `store_update` write is logged and dropped instead of crashing its caller (F4 removes the previous "unclassified write still crashes" gap too).
- `modules/dev/incident.py`'s `load_incidents`: if the incidents-table scan fails partway through a batch import, incidents already created before the failure stay created. ACCEPTED (not a caveat to revisit here): a re-run of `load_incidents` is safe because `create_missing_incidents`' own duplicate check skips already-created incidents; full transactional rollback is TASK-38's.
- Webhooks retain the pre-existing unclassified-ClientError gap on both reads and writes until TASK-25.2.5.6 lands; that task is now a dependency of TASK-25.2.5.5, so the legacy module cannot be deleted before it closes.
- Rollback: one `git revert` restores the legacy `integrations.aws.dynamodb` import in db_operations.py/incident_folder.py and the pre-catch call sites in the three surface files (that legacy module stays until .5). Ordering: must land after .1 (adapter exists) and before .5 (contract/deletion); independent of .2 (webhooks) and .6 (webhooks parity), can land in any order relative to them.

VERIFICATION (from app/, record commands and actual output in --notes at finalization)
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'   (compare against the 85-error baseline recorded on .1/.2; no new errors)
cd app && uv run pytest tests/modules/incident tests/unit/modules/dev
cd app && uv run pytest tests --ignore=tests/smoke
rg -n "integrations.aws" modules/incident/db_operations.py modules/incident/incident_folder.py   (expect 0 hits)
rg -n "db_operations\.get_incident\(" --glob '!tests/**' app  (re-confirm 0 hits before finalizing the AC#4 deletion)
rg -n "update_incident_field\(" --glob '!tests/**' app  (re-confirm incident_status.py:59 and information_update.py:322 are the only callers and need no catch, per F4)
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTATION NOTES

Per-call-site before/after (AC#6):
- create_incident: before, a legacy False crashed on response["ResponseMetadata"]; a 400-status dict logged+returned None. After: non-success (classified OR unclassified ClientError) -> log incident_creation_failed + return None. Duplicate-check read (get_incident_by_channel_id) now raises IncidentStoreUnavailableError on a failed scan instead of silently treating failure as "no duplicate".
- list_incidents: before, pure pass-through; a legacy False reached modules/dev/incident.py:22's len(incidents) and crashed. After: non-success (classified or unclassified) -> log incident_list_failed + raise IncidentStoreUnavailableError; empty scan still returns [].
- update_incident_field: before, a legacy falsy response was swallowed silently (no log). After: non-success (classified or unclassified) -> log incident_update_failed + return None; no caller needs a catch (F4 closes the information_update.py:322 / incident_status.py:59 gap at the source, re-grepped, no code change needed at either).
- log_activity: before, a legacy falsy response logged activity_log_failed and returned False. After: same contract; also catches an unclassified ClientError (log status="unclassified", return False); write sent with retries=False.
- get_incident: deleted (dead code, zero production callers, re-grepped `db_operations\.get_incident\(` = 0 hits outside tests).
- lookup_incident / get_incident_by_channel_id: before, a legacy False crashed len(...) call sites. After: non-success (classified or unclassified) -> log incident_lookup_failed + raise IncidentStoreUnavailableError; empty scan still returns [] / None. field_type param dropped (literal {"S": value} used, matching test_lookup_incident).
- incident_folder.store_update: before, a legacy False crashed on response.get("ResponseMetadata", {}); a 400-status dict returned None silently. After: non-success (classified or unclassified) -> log incident_update_store_failed + return None; read half (lookup_incident) now raises, caught at incident_helper.py:696 (handle_updates_submission) and :704 (display_current_updates, via fetch_updates).

Surface-handling table (AC#5, F3 re-grep, 12 sites):
1. core.py:303 (_create_database_record, create_incident) - already inside try/except Exception (:288-317). NO CHANGE.
2. core.py:364 (recreate_missing_resources, get_incident_by_channel_id) - its only caller incident_helper.recreate_missing_incident_resources wraps the whole call in try/except Exception. NO CHANGE.
3. information_display.py:17 (open_incident_info_view) - ADDED try/except IncidentStoreUnavailableError -> respond(INCIDENT_STORE_UNAVAILABLE_MESSAGE); return.
4. incident_helper.py close_incident (get_incident_by_channel_id) - ADDED same catch.
5. incident_helper.py handle_update_status_command (get_incident_by_channel_id) - ADDED same catch.
6. incident_helper.py open_updates_dialog (get_incident_by_channel_id) - no respond param; ADDED local _store_unavailable_view() helper; on catch, client.views_open(trigger_id=..., view=_store_unavailable_view()).
7. incident_helper.py handle_updates_submission (incident_folder.store_update) - ADDED catch around the call.
8. incident_helper.py display_current_updates (incident_folder.fetch_updates) - ADDED same catch.
9. modules/dev/incident.py list_incidents (db_operations.list_incidents) - ADDED same catch.
10. modules/dev/incident.py load_incidents (incident_folder.create_missing_incidents) - ADDED same catch. Accepted: partial-batch incidents already created before a mid-loop scan failure are not rolled back (create_missing_incidents' own duplicate check makes a re-run safe).
11. modules/dev/incident.py add_incident (get_incident_by_channel_id) - ADDED catch.
12. modules/dev/incident.py add_incident (create_incident) - ADDED a second, separate catch.
F4 confirms no 13th surface site is needed: reads' unclassified case raises the same typed exception the above catches already target; ordinary writes never raise at all.

Re-greps recorded:
- `rg -n "integrations.aws" modules/incident/db_operations.py modules/incident/incident_folder.py` -> 0 hits.
- `rg -n "db_operations\.get_incident\(" --glob '!tests/**' app` -> 0 hits (AC#4 deletion confirmed safe).
- `rg -n "update_incident_field\(" --glob '!tests/**' app` -> only incident_status.py:59 and information_update.py:322 (plus the def itself); neither needs a change (both ignore the return value already).

Deviations from the plan's literal pseudocode (behavior unchanged, only implementation mechanics differ from the sketch, needed to satisfy the pre-authored tests' mocking strategy):
1. information_display.py imports IncidentStoreUnavailableError and INCIDENT_STORE_UNAVAILABLE_MESSAGE directly from modules.incident.db_operations (`from modules.incident.db_operations import INCIDENT_STORE_UNAVAILABLE_MESSAGE, IncidentStoreUnavailableError`) rather than referencing `db_operations.IncidentStoreUnavailableError` in the except clause. Reason: test_information_display.py's `@patch("modules.incident.information_display.db_operations")` replaces the whole db_operations name with an unspec'd MagicMock and never sets `.IncidentStoreUnavailableError` on it (unlike the incident_helper.py/dev-incident.py tests, which explicitly do `mock_db_ops.IncidentStoreUnavailableError = db_operations.IncidentStoreUnavailableError`). Catching `except <MagicMock attribute>:` raises `TypeError: catching classes that do not inherit from BaseException` (verified empirically). incident_helper.py and modules/dev/incident.py keep the plan's literal `db_operations.IncidentStoreUnavailableError` form since their tests do set that attribute.
2. modules/dev/incident.py: fixed a pre-existing bug in list_incidents and add_incident where `incident_conversation.is_incident_channel(client, logger, channel_id)` was called with 3 positional args against the real 2-arg signature `is_incident_channel(client, channel_id, notify=True)` (logger was being passed as channel_id). Simple bug fix in a touched file per standing preference; corrected to `is_incident_channel(client, channel_id)`.

Test changes (with reasons):
1. tests/modules/incident/test_db_operations.py: test_update_incident_field and test_update_incident_field_with_type now patch `db_operations.log_activity` and assert it was called (test_update_incident_field only), instead of asserting `adapter.update_item.assert_called_once()` against the unmocked real log_activity. Reason: update_incident_field's success path calls log_activity per the plan (STEP 1e, unchanged behavior), and log_activity issues its own adapter.update_item call against the same fixture-provided adapter mock, so the original assertion of exactly one call was unsatisfiable without mocking log_activity out. This is a test authoring gap, not a plan/architecture conflict.
2. tests/modules/incident/test_incident_helper.py:
   - test_close_incident_responds_when_store_unavailable: fixed the call to `incident_helper.close_incident(client, body, ack, respond)` (was `(client, body, respond, ack)`, swapped vs. the real signature `close_incident(client, body, ack, respond)`).
   - test_handle_update_status_command_responds_when_store_unavailable: fixed the call to `incident_helper.handle_update_status_command(client, body, respond, ack, ["Closed"])` (was `(client, body, "new_status", respond, ack)` -- wrong order/type against the real signature `(client, body, respond, ack, args)`; "new_status" is also not a valid status so the original call would never have reached get_incident_by_channel_id, and would in fact crash on `str.join(" ", ack)` since `args` was bound to the ack MagicMock).
   - test_open_updates_dialog_opens_unavailable_view_when_store_unavailable: replaced `assert db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE in str(view)` with `assert view["blocks"][0]["text"]["text"] == db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE`. Reason: `str()` of a dict reprs nested strings, escaping the message's real newline as the two-character sequence `\n`, so the raw (real-newline) message can never be a substring of `str(view)` for any multi-line message -- verified empirically. Structural assertion is equivalent in intent and actually verifies the right field.
3. tests/unit/modules/dev/test_dev_incident_handler.py: rewritten. The pre-authored file called `incident.list_incidents(respond)`, `incident.load_incidents(test_incidents, respond)`, `incident.add_incident("C001", respond)` -- none of which match the real signatures `list_incidents(ack, logger, respond, client, body)`, `load_incidents(ack, logger, respond, client, body)`, `add_incident(ack, logger, respond, client, body)` (the plan's own F3 site descriptions reference these same unchanged signatures/line numbers). Rewrote all 4 tests to call with the real 5-arg signature, added MagicMock ack/logger/client and a body dict, and stubbed `incident_conversation`/`incident_folder` collaborators only where needed to reach the store call cleanly without invoking real Slack/Drive logic against bare MagicMocks. `test_list_incidents_responds_when_store_unavailable` uses `respond.assert_called_with(...)` (last call) instead of `assert_called_once_with(...)` because list_incidents legitimately responds once with the "Is this an incident channel?" message before reaching db_operations.list_incidents(), unchanged pre-existing behavior. Same file also got a ruff-format pass (line wrapping only).

VERIFICATION (from app/):
- `uv run ruff check .` -> All checks passed!
- `uv run ruff format --check .` -> 734 files already formatted
- `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` -> Found 82 errors in 30 files (checked 353 source files); baseline from TASK-25.2.5.1/.2 was 85; net -3, zero new errors in db_operations.py, incident_folder.py, information_display.py, incident_helper.py, modules/dev/incident.py (the touched files' remaining errors -- db_operations.py:75, incident_folder.py:425/453/455/463/466/467, incident_helper.py:682 -- are pre-existing, in code/lines this task did not change).
- `uv run pytest tests/modules/incident tests/unit/modules/dev -q` -> 336 passed
- `uv run pytest tests --ignore=tests/smoke -q` -> 6 failed, 3498 passed. The 6 failures are the known pre-existing order-dependent leaks: tests/modules/webhooks/test_webhooks_aws_sns.py (3) and tests/unit/infrastructure/directory/test_google.py (3), unrelated to this change (TASK-90).
- `rg -n "integrations.aws" modules/incident/db_operations.py modules/incident/incident_folder.py` -> 0 hits.
- `rg -n "db_operations\.get_incident\(" --glob '!tests/**' app` -> 0 hits.
- `rg -n "update_incident_field\(" --glob '!tests/**' app` -> only incident_status.py:59 and information_update.py:322 as callers (plus the definition); neither needs a change.

core.py and information_update.py: confirmed unchanged (`git diff --stat` shows no modification to either file).

REVIEW FOLLOW-UP (2026-09-16), supersedes deviation 1 and the mypy line above:
- information_display.py now uses the same form as the other surfaces (`except db_operations.IncidentStoreUnavailableError: respond(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)`), with no direct import and no extra log line (the store already logs the failure). Its test sets the real error class and message constant on the patched db_operations mock, as the incident_helper and dev tests do.
- INCIDENT_STORE_UNAVAILABLE_MESSAGE moved to the top of db_operations.py, and its French text now has accents ("données", "réessayer"), matching webhooks_list.STORE_UNAVAILABLE_MESSAGE.
- store_update: removed the redundant trailing `return None` after the failure branch.
- mypy fixes in touched code: create_incident's duplicate-check return is annotated str (no-any-return from the new return type). open_updates_dialog no longer calls .get on a None incident; incident_id falls back to "Unknown" (pre-existing runtime crash on a channel with no record).
- Verification after follow-up:
  - `uv run ruff check .` -> All checks passed!
  - `uv run ruff format --check modules/incident modules/dev tests/modules/incident tests/unit/modules/dev` -> 41 files already formatted
  - `uv run pytest tests/modules/incident tests/unit/modules/dev -q` -> 336 passed
  - `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'` -> Found 80 errors in 28 files (baseline 85). The remaining errors in incident_folder.py (:425, :453-:467) are pre-existing in functions this task does not touch; none are in db_operations.py, information_display.py, incident_helper.py, modules/dev/incident.py or store_update.
  - `uv run pytest tests --ignore=tests/smoke -q` -> 6 failed, 3498 passed (before the two mypy fixes; the targeted suite was re-run after). The 6 are the known order-dependent SNS/google-directory leaks (TASK-90).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-16 17:06
---
2026-09-16, carried from TASK-25.2.5.2 (read before implementing):
1. The adapter re-raises unclassified ClientError codes (e.g. ValidationException). A helper whose policy is "log and return None/False" (create_incident, update_incident_field, store_update, log_activity) must decide explicitly whether to catch a raised ClientError as well, or a malformed expression or legacy item turns into an exception for its callers. In .2 the counters catch ClientError, log with status="unclassified", and return; programmer errors still propagate.
2. db_operations.lookup_incident builds ExpressionAttributeValues with a dynamic {field_type: value} key. mypy rejects that against the adapter's typed kwargs ("Expected TypedDict key to be string literal"). .2 dropped the unused field_type parameter.
3. log_activity already uses list_append(if_not_exists(logs, :empty_list), :logs), so a missing attribute is handled; point 1 still applies.
---
<!-- COMMENTS:END -->

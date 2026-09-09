---
id: TASK-25.1.6.10.4
title: >-
  Migrate modules/aws/spending.py onto SpreadsheetProvider and delete
  integrations/google_workspace/sheets.py
status: Done
assignee:
  - '@me'
created_date: '2026-09-09 15:04'
updated_date: '2026-09-09 20:48'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.6.10.1
  - TASK-25.1.6.10.2
  - TASK-25.1.6.10.3
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/migration.md
  - app/modules/aws/spending.py
  - app/integrations/google_workspace/sheets.py
parent_task_id: TASK-25.1.6.10
priority: medium
ordinal: 162000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move the last Sheets consumer onto the shared capability and delete the vendor mirror module. This is the slice that takes app/integrations/google_workspace/sheets.py's production reference count to zero.

CALL SITE (grep-verified 2026-09-09): exactly one - modules/aws/spending.py:190 sheets.batch_update_values(spreadsheetId=..., cell_range='Sheet1', values=values, valueInputOption='USER_ENTERED') inside update_spending_data. It becomes get_spreadsheet_provider().update_values(spreadsheet_id, 'Sheet1', values).

CONSUMER SHAPE (decided 2026-09-09, human-directed): direct provider consumption from the legacy module, no feature adapter and no new feature package. One write call with no vendor-specific concepts does not justify a package home, and the Directory migration (TASK-25.1.6.4/.5) set this precedent for legacy modules.

FAILURE SEMANTICS - AN INTENTIONAL CHANGE TO NAME IN THE PR. Today a Sheets HttpError propagates out of update_spending_data uncaught (there is no try/except) and out of modules/aws/aws.py:121 and execute_spending_data_update_job. After migration the provider returns a classified OperationResult instead. Decide and record explicitly whether a failed write logs and returns or raises; the scheduled-job caller is the one whose behavior changes, so state which it is and cover it with a test rather than letting the choice fall out of the diff.

FOLDED-IN DEFECT (registered on TASK-25.1.6.10 by TASK-25.1.6.1 planning, 2026-09-02, and owned by this call site): update_spending_data declares spreadsheet_id=SPENDING_SHEET_ID as a DEFAULT ARGUMENT, evaluated at import time. The sheet id is frozen at process start, unaffected by later config resolution, and unpatchable via the module attribute - which is why every existing test must pass spreadsheet_id explicitly. execute_spending_data_update_job calls update_spending_data(spending_data) with no id, so production always uses that frozen value. Fix it while migrating the call site: resolve the id inside the function (get_google_resources_config().spending_sheet_id) rather than carrying the import-time binding across the seam. The module-level SPENDING_SHEET_ID constant and its _get_spending_sheet_id() helper go with it if nothing else uses them.

DELETION (the point of this slice): app/integrations/google_workspace/sheets.py and app/tests/integrations/google_workspace/test_sheets.py are deleted. Verify zero production references first - by this point modules/reports is gone (.10.1) and incident_folder.py is migrated (.10.3), so spending.py is the last one. This also removes 5 of the remaining execute_google_api_request call sites, shrinking TASK-25.1.6.11's surface.

NOT IN SCOPE: any other AWS/cost-explorer behavior in spending.py, the currency rates table, integrations/google_workspace/google_drive.py (TASK-25.1.6.10.5), and the deletion of execute_google_api_request itself (TASK-25.1.6.11).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 modules/aws/spending.py's single Sheets call site uses infrastructure.spreadsheets.get_spreadsheet_provider().update_values and the module no longer imports integrations.google_workspace.sheets; no feature adapter or new package is created
- [x] #2 update_spending_data resolves the spreadsheet id inside the function instead of binding it as an import-time default argument; the existing skip-when-id-falsy branch still works and a test proves the id is no longer frozen at import
- [x] #3 The exact values matrix crossing the boundary (header row followed by DataFrame rows, and the header-only empty-DataFrame case) is unchanged, proven by the existing assertions in app/tests/unit/modules/aws/test_spending_handler.py repointed to the provider seam
- [x] #4 app/integrations/google_workspace/sheets.py and app/tests/integrations/google_workspace/test_sheets.py are deleted, with zero remaining production references to integrations.google_workspace.sheets repo-wide
- [x] #5 Full test suite, ruff, mypy, and app/bin/check_sdk_typing.py pass
- [x] #6 A classified write failure is logged with its status and error_code and does NOT propagate: update_spending_data returns without raising and execute_spending_data_update_job logs a failed run rather than crashing, with both covered by tests
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SIZE GATE: PASS as one slice. Production files touched: modules/aws/spending.py (edit, ~35 LOC changed) and integrations/google_workspace/sheets.py (deletion, ~150 LOC removed). Test files: tests/unit/modules/aws/test_spending_handler.py (edit) and tests/integrations/google_workspace/test_sheets.py (deletion). One subsystem (app backend), one call site, no terraform/CI. The import swap and the failure-semantics change touch the same six lines of the same function and were decided together by the human as one seam-crossing change (comment #11 on parent 25.1.6.10) - splitting them would produce a first PR that still raises past a Path A boundary (architecture drift) and a second PR with no independent value. Not decomposed.

STEP 1 - app/modules/aws/spending.py: swap the Sheets call site for SpreadsheetProvider, fix the import-time id binding, contain the write failure.

1a. Imports (top of file): remove `from integrations.google_workspace import sheets`. Add `from infrastructure.spreadsheets import get_spreadsheet_provider`. Keep the existing `from infrastructure.configuration.integrations.google import get_google_resources_config` import (already present at line 9-11).

1b. Delete lines 18-23 (`_get_spending_sheet_id()` helper and the module-level `SPENDING_SHEET_ID = _get_spending_sheet_id()` constant). Grep-verified zero other references repo-wide (production or test) to `spending.SPENDING_SHEET_ID` or `spending._get_spending_sheet_id`.

1c. Rewrite `update_spending_data` (currently lines 156-196):
```python
def update_spending_data(spending_data_df: DataFrame, spreadsheet_id: str | None = None) -> bool:
    """
    Updates the entire Sheet1 with new spending data.

    Args:
        spending_data_df: pandas DataFrame containing the data to upload
        spreadsheet_id: Google Sheets spreadsheet ID; resolved from config when omitted

    Returns:
        True if the write succeeded, False if it was skipped (no id) or failed.
    """
    if spreadsheet_id is None:
        spreadsheet_id = get_google_resources_config().spending_sheet_id
    log = logger.bind(spreadsheet_id=spreadsheet_id)
    if not spreadsheet_id:
        log.error("update_spending_data", error="spending sheet id is not set")
        return False

    header = spending_data_df.columns.tolist()
    data_values = spending_data_df.values.tolist()
    values = [header]
    if isinstance(data_values, list):
        values.extend(data_values)
    else:
        log.warning("data_values_is_not_list", actual_type=str(type(data_values)))
        for _, row in spending_data_df.iterrows():
            values.append(row.tolist())

    # Temporary shim: this legacy module owns the OperationResult check and its
    # logging directly until AWS spending reporting is rearchitected into a
    # feature package, at which point a service should own the outcome.
    result = get_spreadsheet_provider().update_values(spreadsheet_id, "Sheet1", values)
    if not result.is_success:
        log.error(
            "update_spending_data_failed",
            status=result.status.value,
            error_code=result.error_code,
            message=result.message,
        )
        return False

    log.info("update_spending_data")
    return True
```
Notes: the `spreadsheet_id=None` sentinel (not a call-time default expression) is what removes the import-time freeze - resolution happens on every call, inside the function body, so config changes and test patches of `get_google_resources_config` take effect per-call. Passing `spreadsheet_id=""` explicitly still skips (unchanged falsy branch, AC#2). The `.value` on `result.status` matches the enum-to-string pattern already used elsewhere (OperationStatus is an Enum). The one-line shim comment is the AC#6/parent-comment-#11-mandated marker so this is not read as a permanent pattern.

1d. Rewrite `execute_spending_data_update_job` (currently lines 199-216) so the job observes the write outcome instead of assuming success unconditionally - this is the "scheduled-job caller is the one whose behavior changes" piece named on the task:
```python
def execute_spending_data_update_job() -> None:
    """Executes the spending data update job"""
    log = logger.bind()
    log.info("execute_spending_data_update_job", status="started")
    spending_data = generate_spending_data()
    if spending_data.empty:
        log.warning(
            "execute_spending_data_update_job",
            status="no_data",
            message="No spending data to update",
        )
        return
    updated = update_spending_data(spending_data)
    if not updated:
        log.warning(
            "execute_spending_data_update_job",
            status="failed",
            message="Spending data update did not complete",
        )
        return
    log.info("execute_spending_data_update_job", status="success")
```
The old unconditional final `log.info(..., spreadsheet_id=SPENDING_SHEET_ID)` is replaced; the id is already logged once, inside `update_spending_data`'s bound logger, on every code path (success, skip, and failure), so it is not duplicated here.

1e. No other function in this file touches Sheets; `generate_spending_data`, `get_accounts_details`, `get_accounts_spending`, `get_rate_for_period`, `format_account_details`, `spending_to_df` and the `rates` table are untouched (NOT IN SCOPE per the task description).

STEP 2 - app/tests/unit/modules/aws/test_spending_handler.py: repoint the existing assertions to the provider seam (AC#3), add coverage for AC#2 and AC#6.

Provider mocking pattern: `@patch("modules.aws.spending.get_spreadsheet_provider")`, with `mock_get_provider.return_value.update_values.return_value = OperationResult.success(data=None)` for the happy path, and `OperationResult.error(status=OperationStatus.TRANSIENT_ERROR, message=..., error_code=...)` for the failure path. Import `OperationResult` and `OperationStatus` from `infrastructure.operations`. Because `spending.py` does `log = logger.bind(...)`, a `@patch("modules.aws.spending.logger")` mock's bound calls land on `logger_mock.bind.return_value.<level>` - assert there, matching the structlog-bind pattern (contrast with incident_folder's tests, which patch `logger` directly because that module calls `logger.error(...)` without `.bind()`).

- `test_should_update_spending_data_in_sheet` -> repoint: assert `mock_get_provider.return_value.update_values.assert_called_once_with("test_sheet_id", "Sheet1", values)` (values = `[["Account", "Cost"], ["123456789012", 100.00]]`); assert return value is `True`.
- `test_should_skip_update_when_spreadsheet_id_not_set` -> the meaning of "not set" changes from "caller passed None" to "config resolves to empty". Repoint: `@patch("modules.aws.spending.get_google_resources_config")` with `.return_value.spending_sheet_id = ""`, call `spending.update_spending_data(df)` (no id argument), assert `mock_get_provider.return_value.update_values.assert_not_called()` and return value is `False`.
- `test_should_skip_update_when_spreadsheet_id_is_empty_string` -> unchanged behavior, only the mock target changes to `get_spreadsheet_provider`; still passes `spreadsheet_id=""` explicitly.
- `test_should_send_header_row_followed_by_dataframe_rows_to_sheets` -> repoint: read `values` from `mock_get_provider.return_value.update_values.call_args[0][2]` (third positional arg) instead of `call_args[1]["values"]`.
- `test_should_send_header_row_only_when_dataframe_has_no_rows` -> same repoint as above.
- `test_should_propagate_error_when_sheets_update_fails` -> RENAME to `test_should_log_and_return_false_when_sheets_update_fails` (this is the AC#6 behavior-change test). Set `mock_get_provider.return_value.update_values.return_value = OperationResult.error(status=OperationStatus.TRANSIENT_ERROR, message="sheets down", error_code="RATE_LIMITED")`. Assert `spending.update_spending_data(df, spreadsheet_id="test_sheet_id")` returns `False` and raises nothing (no `pytest.raises`); assert the bound logger's `.error` was called with `"update_spending_data_failed"`, `status="transient_error"`, `error_code="RATE_LIMITED"`, `message="sheets down"`.
- NEW `test_should_resolve_spreadsheet_id_from_config_when_not_provided` (AC#2, proves the id is no longer frozen at import): patch `get_google_resources_config` to return two different `spending_sheet_id` values across two successive calls to `update_spending_data(df)` with no id argument (e.g. via `side_effect` returning two distinct mock config objects, or reassigning `mock_config.spending_sheet_id` between calls); assert `update_values` was called with each distinct id in turn. This is the direct replacement for the old "module attribute cannot be patched" defect - it must fail against the current import-time-bound code and pass after Step 1c.
- `test_should_execute_and_update_spending_job_successfully` -> add `mock_update.return_value = True` and assert `spending.execute_spending_data_update_job()` returns without warning (add a `@patch("modules.aws.spending.logger")` and assert no `.warning` call with `status="failed"`, or assert `logger_mock.bind.return_value.info.assert_called_with("execute_spending_data_update_job", status="success")`).
- NEW `test_should_log_failed_run_when_update_spending_data_fails` (AC#6, the job-level half): `mock_update.return_value = False`, assert `execute_spending_data_update_job()` returns without raising and the bound logger's `.warning` was called with `status="failed"`.
- `test_should_skip_update_when_spending_data_empty` -> unchanged.
- The three data-shaping tests (`test_should_generate_spending_data_successfully`, `test_should_return_empty_dataframe_when_no_spending_data_provided`, `test_should_flatten_spending_data_correctly`) are untouched - they never touch Sheets.

STEP 3 - delete app/integrations/google_workspace/sheets.py and app/tests/integrations/google_workspace/test_sheets.py.
Pre-condition already verified by grep (2026-09-09): `rg -n "integrations.google_workspace.sheets|from integrations.google_workspace import sheets" --type py .` returns exactly two hits before this change - modules/aws/spending.py:13 (removed in Step 1a) and the test file itself (deleted here). After Step 1 and this deletion, zero production references remain repo-wide (AC#4). `app/bin/baselines/sdk_typing_antipatterns.txt` has no entry for `sheets.py`, so no baseline edit is needed for `app/bin/check_sdk_typing.py` to keep passing (AC#5).

STEP 4 - verification (AC#5), run from app/:
- `uv run ruff check .`
- `uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`
- `uv run pytest tests --ignore=tests/smoke` (full suite per AC#5, not just the touched file)
- `uv run python bin/check_sdk_typing.py`

AC TRACEABILITY
- AC#1 (provider call site, no sheets import, no new package) -> Step 1a, 1c.
- AC#2 (id resolved inside function, skip branch intact, proven not frozen) -> Step 1b, 1c; tests: repointed `test_should_skip_update_when_spreadsheet_id_is_empty_string`, repointed `test_should_skip_update_when_spreadsheet_id_not_set`, new `test_should_resolve_spreadsheet_id_from_config_when_not_provided`.
- AC#3 (exact values matrix unchanged, existing assertions repointed) -> Step 1c; tests: repointed `test_should_send_header_row_followed_by_dataframe_rows_to_sheets`, `test_should_send_header_row_only_when_dataframe_has_no_rows`.
- AC#4 (sheets.py and its test deleted, zero production references) -> Step 3.
- AC#5 (full suite, ruff, mypy, check_sdk_typing.py pass) -> Step 4.
- AC#6 (classified failure logged with status/error_code, does not propagate, job logs a failed run) -> Step 1c, 1d; tests: renamed `test_should_log_and_return_false_when_sheets_update_fails`, new `test_should_log_failed_run_when_update_spending_data_fails`.

TEST MATRIX (app/tests/unit/modules/aws/test_spending_handler.py)
- Happy path: write succeeds -> provider.update_values called with (id, "Sheet1", values), returns True.
- Boundary: header-only empty DataFrame -> values is `[header]` only (existing test, repointed).
- Boundary: explicit `spreadsheet_id=""` -> skip, provider never called, returns False (existing test, repointed).
- Boundary: id omitted and config resolves to `""` -> skip, provider never called, returns False (existing test, repointed semantics).
- Boundary/regression: id omitted and config value changes between two calls -> each call uses the current value, not a cached one (new test, proves AC#2's defect fix).
- Failure: provider returns a classified error -> logged with status/error_code/message, no exception, returns False (renamed test).
- Job success: `update_spending_data` returns True -> job logs success, no warning.
- Job failure: `update_spending_data` returns False -> job logs a failed run, no exception (new test).
- Skip-empty-data: `generate_spending_data()` returns an empty DataFrame -> `update_spending_data` never called (existing test, untouched).

ASSUMPTIONS AND DOUBTS
- Assumes `OperationResult.status` is always an `OperationStatus` enum member so `.value` is safe to log; verified in infrastructure/operations/result.py and status.py (read directly, not from memory).
- Assumes no other code calls `modules.aws.spending.update_spending_data` expecting a `None` return; grep-verified the only production caller is `execute_spending_data_update_job` (this file) and the `/aws spending` Slack handler in modules/aws/aws.py:123, which already discards the return value (`spending.update_spending_data(spending_df)` with no assignment) - adding a `bool` return is additive and does not change that call site's behavior. Not touched in this slice per the task's NOT IN SCOPE note; verify no test on aws.py's spending branch pins a `None`/absence assertion in app/tests/unit/modules/aws/ or app/tests/modules/aws/ before merging - a repo-wide grep for `aws_command` + `"spending"` test names should confirm.
- Assumes structlog's `logger.bind(...)` pattern (rather than incident_folder.py's direct `logger.error(...)`) is what spending.py already uses today (verified by reading the file), so test mocking must assert on `logger_mock.bind.return_value.<level>`, not `logger_mock.<level>` directly - get this wrong and the new/renamed tests will pass for the wrong reason (asserting on an uncalled mock attribute) rather than fail.
- Assumes `app/bin/baselines/sdk_typing_antipatterns.txt` has no entry for `integrations/google_workspace/sheets.py` (grep-verified empty result) - if this assumption is wrong, `check_sdk_typing.py` would report a stale baseline entry, which does not fail the check, so no action is required either way.

BLAST RADIUS AND ROLLBACK
- Runtime surface: the AWS spending Slack command (`/aws spending`) and the scheduled `execute_spending_data_update_job`. Both already write to the same spreadsheet via the same values matrix; only the transport (SpreadsheetProvider vs. raw sheets.batch_update_values) and the failure path change.
- Worst case if this ships wrong: a spreadsheet write silently fails without raising where it previously would have crashed the job loudly. This is the intended, human-approved trade (comment #11 on the parent task: "nothing infers state from the absence of a write" for this call site, unlike the incident-status read path). The classified error is still logged with status/error_code, so failures remain observable via logs/alerts on `update_spending_data_failed` and `execute_spending_data_update_job status=failed`, just not via a crash.
- A single `git revert` of this PR fully restores prior behavior: it restores `sheets.py`, its test, the frozen `SPENDING_SHEET_ID` default argument, and the uncaught-exception propagation, with no data migration or config dependency in either direction.
- No ordering constraint against other in-flight children: TASK-25.1.6.10.5 (google_drive.py retirement) is independent of this file; TASK-25.1.6.13 (SDK retry-at-construction) is not a dependency of this task per parent comment #11 (only .10.2 and .10.5 depend on it).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented the AWS spending migration to SpreadsheetProvider: spreadsheet IDs resolve from Google resources config per call, values preserve the existing header/data matrix, classified write failures are logged and contained, and the scheduled job logs failed runs. Deleted integrations/google_workspace/sheets.py and its dedicated test. With human approval, also folded in the missing prerequisite cleanup: deleted the unreachable modules/reports package and tests and removed its orphaned Google resource setting. Evidence: focused spending tests 13 passed; human reports make test green; Ruff passed; bin/check_sdk_typing.py passed with no net-new anti-patterns; zero production references to integrations.google_workspace.sheets remain. AC #5 remains unchecked because repository-wide mypy still reports 65 pre-existing errors across unrelated legacy/dependency files; touched behavior is covered and the changed production files introduce no reported errors. Human follow-up: address the existing whole-tree mypy debt before checking AC #5 and closing the task.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-09 15:28
---
FAILURE SEMANTICS DECIDED 2026-09-09 (human-directed), replacing the 'decide during implementation' AC.

DO NOT PRESERVE TODAY'S BEHAVIOR. Right now a Sheets HttpError propagates uncaught out of update_spending_data, out of modules/aws/aws.py:121 and out of execute_spending_data_update_job. That is drift from decisions/outbound-clients.md, not a contract worth carrying across the seam - the current code predates the architecture and is to be treated as outdated.

TARGET: the provider returns a classified OperationResult; update_spending_data logs the failure with status and error_code and returns; execute_spending_data_update_job logs a failed run. No exception crosses the boundary. This is safe here in a way it would not be for a read: nothing infers state from the absence of a write, unlike TASK-25.1.6.10.3's get_incidents_from_sheet, where an empty result would cause a duplicate row and therefore still raises.

THE RESULT HANDLING IN THE LEGACY MODULE IS AN EXPLICIT TEMPORARY SHIM. modules/aws/spending.py stays a frozen legacy module; the OperationResult check and its logging live there only until the AWS spending concern is rearchitected into a feature package, at which point a service owns the result and decides the user-facing outcome. Say so in a one-line comment at the call site so the shim is not mistaken for a permanent pattern, and do not build a result-translation helper for one call site.
---
<!-- COMMENTS:END -->

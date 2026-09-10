---
id: TASK-25.1.6.10.5
title: >-
  Retire integrations/google_workspace/google_drive.py: re-home incident
  appProperties metadata and relocate DRIVE_SCOPES
status: Done
assignee:
  - '@me'
created_date: '2026-09-09 15:04'
updated_date: '2026-09-10 17:10'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.6.10.1
  - TASK-25.1.6.13
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - app/integrations/google_workspace/google_drive.py
  - app/packages/incident/drive/adapters/google_drive.py
  - app/infrastructure/drive/google.py
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1.6.10
priority: medium
ordinal: 163000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Take app/integrations/google_workspace/google_drive.py to zero production references and delete it. This inherits TASK-25.1.6.10's original AC#7, whose premise ('its last two call sites live in modules/reports/google_groups.py') is stale - see the 2026-09-08 impact note on the parent.

ACTUAL REMAINING REFERENCES after TASK-25.1.6.10.1 deletes modules/reports (grep-verified 2026-09-09):
1. app/packages/incident/drive/adapters/google_drive.py - deliberate temporary pass-throughs shipped by TASK-25.1.6.8.2: add_metadata, delete_metadata, get_metadata (via legacy list_metadata), and find_document_by_channel_name's metadata lookup. These are Google appProperties operations, intentionally excluded from the vendor-neutral DriveProvider by the 2026-09-08 architecture clarification recorded on TASK-25.1.6.8.1 and in decisions/layers.md.
2. app/infrastructure/drive/google.py:13 imports DRIVE_SCOPES from it.
3. app/packages/incident_draft/adapters/google_docs.py:321 and :1308 use google_drive.DRIVE_SCOPES.

WHY THIS IS A SEPARATE SLICE, NOT PART OF THE SHEETS MIGRATION: it is Drive-shaped work with its own architectural decision (where Google appProperties lives), and it was only parked on TASK-25.1.6.10 because the deleted report module used to hold the last call sites. Kept under this coordinator because .10 already owned the deletion; nothing in it depends on the spreadsheets capability.

TARGET SHAPE:
- The three metadata operations become REAL Path B code inside packages/incident/drive/adapters/google_drive.py, per decisions/layers.md ('the feature adapter owns vendor-specific behavior during migration') and decisions/outbound-clients.md ('the adapter is the boundary'): build the Resource from integrations.google_workspace.client.get_drive_service, call files().get / files().update(body={'appProperties': ...}) with supportsAllDrives=True directly on the stub-typed handle, wrap in try/except HttpError, and classify with classify_google_error. No execute_google_api_request, no pass-through to a vendor mirror module. The adapter keeps returning the dict shapes its incident callers consume today, so no consumer outside the adapter changes.
- DRIVE_SCOPES relocates into app/infrastructure/drive/google.py (scopes are Google-specific and belong in the Google implementation, the same rule TASK-25.1.6.10.2 applies to the Sheets scope from the start). infrastructure/drive/google.py drops the cross-tier import into a doomed vendor module - the wart flagged as step 5B / doubt (b) on TASK-25.1.6.8.1. packages/incident_draft/adapters/google_docs.py and the incident Drive adapter take the constant from its new home, or define their own if the incident_draft adapter's scope needs differ.
- app/integrations/google_workspace/google_drive.py and app/tests/integrations/google_workspace/test_google_drive.py are deleted.

WATCH: app/tests/unit/packages/incident/drive/adapters/test_incident_drive_boundaries.py asserts on the string 'integrations.google_workspace import google_drive' in the adapter source. That guard must be updated to match the new boundary (the adapter will legitimately import integrations.google_workspace.client instead, which decisions/layers.md permits only inside adapters/), not deleted.

NOT IN SCOPE: widening DriveProvider with metadata methods (explicitly rejected 2026-09-08 - appProperties is not a portable capability), LEGACY_FOLDER_DISPLAY_LIMIT (TASK-81), any Sheets work, and the deletion of execute_google_api_request (TASK-25.1.6.11).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 packages/incident/drive/adapters/google_drive.py implements add_metadata, delete_metadata and get_metadata itself against a stub-typed DriveResource from integrations.google_workspace.client.get_drive_service, with its own try/except HttpError plus classify_google_error; no pass-through to a vendor mirror module and no execute_google_api_request remains
- [x] #2 infrastructure.drive.DriveProvider is NOT widened with metadata or appProperties operations; the vendor-neutral contract is unchanged
- [x] #3 DRIVE_SCOPES lives in app/infrastructure/drive/google.py (or each adapter owns its own scope list); no module imports it from integrations.google_workspace.google_drive, including packages/incident_draft/adapters/google_docs.py's two call sites
- [x] #4 app/integrations/google_workspace/google_drive.py and app/tests/integrations/google_workspace/test_google_drive.py are deleted, with zero remaining production references repo-wide
- [x] #5 app/tests/unit/packages/incident/drive/adapters/test_incident_drive_boundaries.py is updated to guard the new boundary rather than deleted, and the incident callers of the metadata functions are unchanged
- [x] #6 Unit tests cover the three metadata operations' success and classified-failure paths at the adapter's SDK seam
- [x] #7 Full test suite, ruff, mypy, and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SCOPE FRAMING (user direction 2026-09-10)
This slice is part of isolating business features, legacy modules included, from direct vendor SDK calls. The end state is that every Google Drive call sits in an adapter that holds the stub-typed SDK handle and classifies errors with classify_google_error, which is the baseline for conforming to decisions/outbound-clients.md and decisions/sdk-typing.md. That isolation is meant to make the full transition to decisions/layers.md and decisions/feature-packages.md easier and less risky. Moving legacy callers onto OperationResult and frozen dataclasses, and further work on the infrastructure services (infrastructure/drive), come later and are out of scope here.

KNOWN, INTENTIONAL DEVIATIONS (recorded for the later conformance pass)
- The metadata functions re-raise the classified HttpError instead of returning OperationResult (outbound-clients.md: the adapter "returns OperationResult"). Reason: modules/incident callers rely on today's raise semantics (AC#5).
- They return the SDK `File` payload as `dict[str, Any]` rather than a frozen dataclass (sdk-typing.md item 3). Reason: the task's target shape keeps the callers' dict shapes unchanged.
- Pre-existing and left unchanged: modules/incident/incident_folder.py `delete_folder_metadata` checks `if not response`, a branch that cannot run because failures raise.

CONTEXT / CURRENT STATE (grep-verified 2026-09-10, dependencies TASK-25.1.6.10.1 and TASK-25.1.6.13 both Done)

Only real production references to app/integrations/google_workspace/google_drive.py left:
1. app/infrastructure/drive/google.py:13 `from integrations.google_workspace.google_drive import DRIVE_SCOPES`, used at line 59 `self._get_service(DRIVE_SCOPES, delegated_user_email)`.
2. app/packages/incident/drive/adapters/google_drive.py:17 `from integrations.google_workspace import google_drive as legacy_google_drive`, wrapped by `get_legacy_google_drive()` and called at:
   - line 87 `find_document_by_channel_name`: `get_legacy_google_drive().list_metadata(document.id, fields="id, name, appProperties")`
   - line 92 `add_metadata`: `get_legacy_google_drive().add_metadata(file_id, key, value)`
   - line 96 `delete_metadata`: `get_legacy_google_drive().delete_metadata(file_id, key)`
   - line 100 `get_metadata`: `get_legacy_google_drive().list_metadata(file_id, fields=fields)`
3. app/packages/incident_draft/adapters/google_docs.py:27 `from integrations.google_workspace import google_drive`, used at :321 and :1308 as `google_drive.DRIVE_SCOPES` when building a Drive service for `_copy_source_document` and `_source_name_and_folder`.

app/integrations/google_workspace/google_drive.py itself (308 LOC) still defines DRIVE_SCOPES plus 10 Drive functions (add_metadata, delete_metadata, list_metadata, create_folder, create_file_from_template, create_file, find_files_by_name, list_folders_in_folder, list_files_in_folder, copy_file_to_folder, healthcheck) built on `execute_google_api_request`/`_execute_file_request`. All non-metadata functions are already dead (their only callers were app/modules/reports/google_groups.py, deleted by TASK-25.1.6.10.1). Its test file app/tests/integrations/google_workspace/test_google_drive.py (550 LOC) covers all of them.

infrastructure.drive.GoogleDriveProvider (app/infrastructure/drive/google.py) already establishes the target pattern for this task: `_call`/`_map_sdk_exception` wrapping `HttpError`, `classify_google_error` from `integrations.google_workspace.client`, and a Resource obtained via an injected `get_service` callable ultimately backed by `integrations.google_workspace.client.get_drive_service`. DriveProvider intentionally has no appProperties/metadata methods (AC#2 says keep it that way; decisions/layers.md excludes vendor-specific appProperties from the vendor-neutral contract).

infrastructure.spreadsheets sets the exact precedent for both parts of this task, shipped by the already-Done TASK-25.1.6.10.2:
 - `SHEETS_SCOPES = [...]` is a plain module constant defined directly in infrastructure/spreadsheets/google.py:14 (not imported from anywhere). It is NOT re-exported; the re-export precedent is `RANGE_NOT_FOUND`, which infrastructure/spreadsheets/__init__.py re-exports from google.py.
 - Consumers import `RANGE_NOT_FOUND` from the infrastructure package's __init__.py, never from the concrete `google.py` module directly - this is what keeps CLAUDE.md's "never import concrete implementations from app/infrastructure/<service>/... in package/domain/route code" satisfied while still letting the constant live in the Google implementation file per this task's own instructions.
 app/infrastructure/drive/__init__.py already re-exports DriveFile, DriveProvider, DriveSettings, get_drive_provider, get_drive_provider - DRIVE_SCOPES will join that list the same way.

test_incident_drive_boundaries.py today only greps app/modules/incident/**/*.py and app/jobs/**/*.py for the literal substring "integrations.google_workspace import google_drive" - it does not scan app/packages/incident/drive/adapters/google_drive.py at all, so it currently passes vacuously with respect to the adapter. Per the task's WATCH note this must be widened to actually guard the adapter itself once its import changes from the legacy module to `integrations.google_workspace.client` (permitted per decisions/layers.md, "the only feature files that may import from app/integrations/" are Path B adapters).

DECISION (confirmed by the user 2026-09-10):
DRIVE_SCOPES lives in infrastructure/drive/google.py as a plain module constant (shape mirrors SHEETS_SCOPES; re-export mirrors RANGE_NOT_FOUND) and is re-exported via infrastructure/drive/__init__.py. Both packages/incident/drive/adapters/google_drive.py and packages/incident_draft/adapters/google_docs.py import `from infrastructure.drive import DRIVE_SCOPES` (the package __init__, not the concrete google.py). For now there is one shared constant, and an inline comment flags it for review when another Drive provider is added. Per-adapter scope lists were considered and deferred, because both adapters need the identical scope today.

TARGET DESIGN

1. app/infrastructure/drive/google.py: delete the `from integrations.google_workspace.google_drive import DRIVE_SCOPES` import. Add `DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]` as a module constant near the top (same shape as `SHEETS_SCOPES` in infrastructure/spreadsheets/google.py:14), with a short inline comment saying it is shared with Google Path B adapters and should be revisited when another Drive provider is added. The comment must NOT reference a task id. Suggested: `# Shared with Google Path B adapters via infrastructure.drive; revisit when another Drive provider is added.` No other line in this file changes (line 59's usage is untouched).

2. app/infrastructure/drive/__init__.py: add `from infrastructure.drive.google import DRIVE_SCOPES` and add `"DRIVE_SCOPES"` to `__all__`, alongside the existing DriveFile/DriveProvider/DriveSettings/get_drive_provider re-exports.

3. app/packages/incident/drive/adapters/google_drive.py becomes the real Path B implementation of the three metadata operations, and so of the metadata lookup inside `find_document_by_channel_name`. It holds the stub-typed SDK handle directly, per outbound-clients.md ("the adapter is the boundary") and sdk-typing.md item 3:
   - Imports: drop `from types import ModuleType` and `from integrations.google_workspace import google_drive as legacy_google_drive`; add `from typing import TYPE_CHECKING`, `from googleapiclient.errors import HttpError`, `from infrastructure.drive import DRIVE_SCOPES`, and `from integrations.google_workspace import client as google_workspace_client` (same alias as packages/incident_draft/adapters/google_docs.py). Under `if TYPE_CHECKING:`, import `DriveResource` and `File` from `googleapiclient._apis.drive.v3`.
   - Remove `get_legacy_google_drive()`. Update the module docstring: metadata is now Google-specific Path B code implemented here (appProperties is deliberately not part of DriveProvider), so drop the "temporary pass-throughs" wording.
   - Add `_drive_service() -> "DriveResource"` returning `google_workspace_client.get_drive_service(scopes=DRIVE_SCOPES)`. client.py:100-103 already annotates the return as `DriveResource`, and no call site passes a delegated user.
   - Add `_log_http_failure(event: str, file_id: str, exc: HttpError) -> None`, the sibling of the existing `_log_failure` (which handles OperationResult). It calls `google_workspace_client.classify_google_error(exc)` and emits `logger.warning(event, file_id=file_id, status=status.value, error_code=error_code, retry_after=retry_after)`. It only logs and never builds or executes a request.
   - NO generic `request: Any` execute helper: it would erase the stub's `FileHttpRequest.execute() -> File` return type, and it is the dispatcher shape sdk-typing.md retires. Each function writes its own try/except around the typed call (outbound-clients.md: "adapter authors write the try/except themselves"):
     ```
     def add_metadata(file_id: str, key: str, value: str) -> dict[str, Any]:
         body = cast("File", {"appProperties": {key: value}})
         try:
             file = _drive_service().files().update(fileId=file_id, body=body, supportsAllDrives=True).execute()
         except HttpError as exc:
             _log_http_failure("incident_drive_add_metadata_failed", file_id, exc)
             raise
         return cast("dict[str, Any]", file)
     ```
     `delete_metadata` is identical except for the body `{"appProperties": {key: None}}` and the event `incident_drive_delete_metadata_failed`. `get_metadata` calls `files().get(fileId=file_id, fields=fields, supportsAllDrives=True)` with the event `incident_drive_get_metadata_failed`.
   - Re-raising preserves today's behavior exactly: the legacy path runs through `execute_google_api_request`, which logs and re-raises (integrations/google_workspace/client.py:176-192). Only `HttpError` is caught; anything else propagates unclassified, per outbound-clients.md.
   - `find_document_by_channel_name`: replace the legacy `list_metadata` call with `metadata = get_metadata(document.id, fields="id, name, appProperties")`. The returned `{"id", "appProperties"}` shape does not change.
   - Legacy `add_metadata`/`delete_metadata` passed `fields=None` to `files().update`, so omitting it is equivalent.
   - NO `num_retries` anywhere (retry is configured at construction in client.py by TASK-25.1.6.13). No `execute_google_api_request` (AC#1).
   - `incident_drive_healthcheck` is unchanged: it already calls `get_metadata` and catches its exceptions.

4. app/packages/incident_draft/adapters/google_docs.py: remove `from integrations.google_workspace import google_drive` (line 27); add `from infrastructure.drive import DRIVE_SCOPES`; replace `google_drive.DRIVE_SCOPES` with `DRIVE_SCOPES` at lines 321 and 1308. No other line changes - `google_workspace_client.get_drive_service`, the existing `try/except HttpError`/`classify_google_error` blocks in `_copy_source_document` and `_source_name_and_folder` are already correct and untouched. The module docstring's "the only place in the package allowed to import integrations" remains true (it still imports `integrations.google_workspace.client`; only the `google_drive` submodule import is removed).

5. Delete app/integrations/google_workspace/google_drive.py (308 LOC) and app/tests/integrations/google_workspace/test_google_drive.py (550 LOC) as plain file deletions during implementation (no git commands - the user controls git per CLAUDE.md).

6. app/tests/unit/packages/incident/drive/adapters/test_incident_drive_boundaries.py: widen the guard so it is not vacuous post-migration. Replace the current two-directory scan with a scan that also covers app/packages/incident/drive/adapters, and split the assertion:
   - `modules/incident` and `jobs` (existing behavior, unchanged): no file may contain "integrations.google_workspace import google_drive" - keep as-is, this guards against modules/incident bypassing the adapter.
   - NEW: app/packages/incident/drive/adapters/google_drive.py itself must NOT contain "integrations.google_workspace import google_drive" (guards against a future contributor re-adding the deleted pass-through) and MUST contain "integrations.google_workspace import client" (or "from integrations.google_workspace import client", matching the actual new import) so the test also pins that the adapter still legitimately reaches the vendor package the way Path B adapters are allowed to per decisions/layers.md, rather than silently losing all SDK access.
   Rename is not required (AC#5 says "updated ... rather than deleted"); the existing two test function names stay, and one new test function is added for the adapter-source assertions.

7. app/tests/unit/packages/incident/drive/adapters/test_incident_drive_adapter.py:
   - Update `test_find_document_by_channel_name_enriches_match_with_app_properties`: replace `patch.object(google_drive, "get_legacy_google_drive", ...)` with `patch.object(google_drive, "_drive_service", ...)`, the same seam as the new add/delete/get tests below, returning a MagicMock whose `.files().get(...).execute()` returns the same fixture dict, and re-assert the same output shape (`{"id": "doc-1", "appProperties": {...}}`).
   - Update `test_incident_drive_healthcheck_returns_false_when_legacy_lookup_raises`: no functional change needed (it patches `get_metadata` directly, which still exists), but confirm import symmetry; rename only if the "legacy" wording in the test name is now misleading (recommend renaming to `test_incident_drive_healthcheck_returns_false_when_metadata_lookup_raises` for AC#6/#5 clarity - a mechanical rename, not a behavior change).
   - ADD (AC#6): six new tests at the adapter's SDK seam (patching `_drive_service` to return a MagicMock Resource, asserting request-building kwargs and classified-failure logging):
     - `test_add_metadata_returns_updated_file_on_success`
     - `test_add_metadata_reraises_classified_http_error`
     - `test_delete_metadata_returns_updated_file_on_success`
     - `test_delete_metadata_reraises_classified_http_error`
     - `test_get_metadata_returns_file_on_success`
     - `test_get_metadata_reraises_classified_http_error`
   Each failure-path test constructs an `HttpError` (reuse the `_http_error(status)` helper pattern from the deleted test_google_drive.py, recreated locally in this file since it has no shared fixture module) and asserts the exception propagates unchanged after a `classify_google_error`-driven warning log (assert via `caplog`/structlog capture or by asserting `logger.warning` was called, matching this repo's existing structlog test conventions - confirm exact convention via testing-standards skill / an existing adapter test with logging assertions before writing).

8. Verify DRIVE_SCOPES relocation does not break existing green tests: grep app/tests for any test importing `integrations.google_workspace.google_drive` or patching `google_drive.DRIVE_SCOPES` (none found in app/tests/unit/infrastructure/drive/, app/tests/unit/infrastructure/drive/test_factory.py, or app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py - confirmed via grep during planning) - no other test file needs updating for the DRIVE_SCOPES move.

TEST STRATEGY / MATRIX

Existing tests that move/are deleted:
- app/tests/integrations/google_workspace/test_google_drive.py: DELETED in full (its subject module is deleted).
- app/tests/unit/packages/incident/drive/adapters/test_incident_drive_adapter.py: one existing test modified (find_document_by_channel_name's mock seam), one renamed (healthcheck test), six new tests added.
- app/tests/unit/packages/incident/drive/adapters/test_incident_drive_boundaries.py: extended with a third guard (adapter-source assertions), no test removed.

New coverage (AC#6): happy path and classified-failure path for each of add_metadata/delete_metadata/get_metadata at the SDK seam (request-building assertions - fileId/body/supportsAllDrives kwargs - plus a classified HttpError re-raise, using at least a 404 and a 429 case to prove classify_google_error is actually invoked, not just any exception swallowed).

No test needed for infrastructure/drive/google.py or infrastructure/drive/__init__.py beyond what already exists (DRIVE_SCOPES's *value* is unchanged, only its defining module moves) - a plain grep-based check in AC#3's own text ("no module imports it from integrations.google_workspace.google_drive") is enforced by AC#4's zero-remaining-reference grep and by the deleted-module import error that would surface immediately in mypy/pytest collection if anything were missed.

VERIFICATION COMMANDS (run from app/, per CLAUDE.md and TASK-25.1.6.13's evidence style)
cd app && uv run ruff check .
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run pytest tests/unit/packages/incident/drive/adapters tests/unit/infrastructure/drive tests/unit/packages/incident_draft tests/unit/integrations/google_workspace -q
cd app && uv run pytest tests --ignore=tests/smoke
cd app && uv run python bin/check_sdk_typing.py
rg -n 'integrations\.google_workspace(\.| import )google_drive' app -g '*.py'   # must return nothing

STEP -> AC TRACEABILITY
Step 3 (adapter rewrite) -> AC#1, AC#5 (unchanged caller dict shapes), partially AC#6 (implementation under test)
Step 3 (no DriveProvider change) -> AC#2 (negative assertion: infrastructure/drive/provider.py and google.py's public Protocol methods are not touched by this task)
Steps 1, 2, 4 (DRIVE_SCOPES relocation + re-export + consumer updates) -> AC#3
Step 5 (deletions) -> AC#4
Step 6 (boundary test widened) -> AC#5
Step 7 (new adapter tests) -> AC#6
Verification commands -> AC#7

RISKS
- Re-raising HttpError after classify_google_error keeps today's behavior, so callers still see raw googleapiclient exceptions rather than OperationResult. This is recorded under KNOWN, INTENTIONAL DEVIATIONS; converting now would ripple into modules/incident/*.py and break the single-PR gate.
- Widening the boundary test to scan the adapter file for both the removed and the newly-legitimate import string is a fragile substring check (as the existing test already is) - accepted since it matches the existing test's own established style, not introduced fresh by this task.
- Rollback: a single git revert restores google_drive.py, its test file, and all four call sites atomically since nothing else depends on the intermediate state; no data migration, no deploy ordering.

SIZE GATE
Production files touched: infrastructure/drive/google.py (edit, ~2 lines), infrastructure/drive/__init__.py (edit, ~2 lines), packages/incident/drive/adapters/google_drive.py (edit, ~40-50 changed lines), packages/incident_draft/adapters/google_docs.py (edit, ~4 lines), integrations/google_workspace/google_drive.py (delete, -308 LOC). 5 production files, roughly 60-70 net changed/added production LOC plus a 308-LOC deletion (deletions do not count against the "production LOC changed" spirit of the gate the way added complexity does, but even counted literally the whole diff is ~370 lines touched across 5 files). One subsystem (Google Workspace Drive integration boundary). No mixed mechanical-refactor-plus-behavior-change: the metadata operations' behavior (success dict shape, failure propagation) is explicitly preserved, this is a seam relocation, not new behavior. Well inside the ~400 LOC / ~10 file / two-subsystem gate - no decomposition required.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented per approved plan, zero deviations.

Changes:
- infrastructure/drive/google.py: DRIVE_SCOPES now a local module constant (mirrors SHEETS_SCOPES), no longer imported from the legacy vendor module.
- infrastructure/drive/__init__.py: re-exports DRIVE_SCOPES (mirrors RANGE_NOT_FOUND precedent).
- packages/incident/drive/adapters/google_drive.py: add_metadata/delete_metadata/get_metadata rewritten as real Path B code against a stub-typed DriveResource from integrations.google_workspace.client.get_drive_service; each wraps its own try/except HttpError + classify_google_error via new _log_http_failure, then re-raises (preserves existing raise semantics). find_document_by_channel_name now calls get_metadata instead of the legacy pass-through. get_legacy_google_drive()/ModuleType import removed.
- packages/incident_draft/adapters/google_docs.py: both DRIVE_SCOPES call sites now import from infrastructure.drive instead of the legacy vendor module.
- Deleted app/integrations/google_workspace/google_drive.py and app/tests/integrations/google_workspace/test_google_drive.py.
- test_incident_drive_boundaries.py already contained the widened adapter-source guard (not import client / not legacy) from the pre-authored failing-test contract; left unchanged as it already matches the new boundary.
- test_incident_drive_adapter.py already contained the 6 new SDK-seam tests (success + classified-failure for all 3 metadata ops) plus the updated find_document_by_channel_name/healthcheck tests from the pre-authored contract; no test edits needed.

Evidence:
- cd app && uv run pytest tests/unit/packages/incident/drive/adapters tests/unit/infrastructure/drive tests/unit/packages/incident_draft tests/unit/packages/talent -q -> 252 passed
- cd app && uv run ruff check . -> All checks passed!
- cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' -> 88 pre-existing errors in 32 files, none in touched files (infrastructure/drive/*, packages/incident/drive/adapters/google_drive.py, packages/incident_draft/adapters/google_docs.py all clean)
- cd app && uv run python bin/check_sdk_typing.py -> OK: no net-new SDK anti-patterns
- grep -rn for integrations.google_workspace(.|import )google_drive -> zero production hits (only the boundary test's own literal guard strings)

AC#7 left unchecked: full `uv run pytest tests --ignore=tests/smoke` was not run by the agent per task instructions (user runs the full suite); targeted subset above is green.

UPDATE: user ran the full suite (make test) - all green. AC#7 checked off. Task ready for human review/PR (status remains In Progress per workflow; only a human moves it to Done).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-09 15:29
---
RETRY CONSTRAINT ADDED 2026-09-09 (human-directed, from TASK-25.1.6.10.2's review). Your new Path B metadata code in packages/incident/drive/adapters/google_drive.py calls the SDK directly, so it would otherwise be the next place a per-call retry argument gets sprinkled.

DO NOT PASS num_retries AT ANY .execute() CALL AND DO NOT DEFINE A RETRY CONSTANT. Retry is configured once at construction in integrations/google_workspace/client.py by TASK-25.1.6.13, now a dependency of this task. Verified against google-api-python-client 2.198.0: build(num_retries=N) only retries the discovery-document fetch, while build(requestBuilder=...) is the real construction-time seam - so the configuration genuinely belongs in client.py, not at your call sites.

NOTE FOR YOUR PLANNING: TASK-25.1.6.13 also deletes _NUM_RETRIES and the 12 per-call num_retries arguments from infrastructure/directory/google.py and infrastructure/drive/google.py. If you read infrastructure/drive/google.py as a template while writing the metadata adapter, read it AFTER .13 lands, or you will copy a shape that is being removed.
---
<!-- COMMENTS:END -->

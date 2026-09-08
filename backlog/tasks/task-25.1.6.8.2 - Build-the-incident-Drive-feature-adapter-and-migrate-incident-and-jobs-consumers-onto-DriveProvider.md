---
id: TASK-25.1.6.8.2
title: >-
  Build the incident Drive feature adapter and migrate incident and jobs
  consumers onto DriveProvider
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-08 18:57'
updated_date: '2026-09-08 22:46'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.8.1
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/feature-packages.md
  - app/packages/incident/documents/adapters/google_docs.py
  - app/modules/incident/core.py
  - app/modules/incident/incident_document.py
  - app/modules/incident/incident_folder.py
  - app/modules/incident/incident_helper.py
  - app/modules/incident/incident_roles.py
  - app/jobs/scheduled_tasks.py
parent_task_id: TASK-25.1.6.8
priority: medium
ordinal: 156000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build a thin incident-owned Drive adapter over TASK-25.1.6.8.1's DriveProvider and repoint the six in-scope incident/jobs consumers onto it: app/modules/incident/core.py (list_files_in_folder), incident_document.py (create_file_from_template), incident_folder.py (list_folders_in_folder x2, delete_metadata, add_metadata, list_metadata x2), incident_helper.py (create_folder, the `/sre incident products create` command — found via fresh grep at planning time, not in the coordinator's original scope), incident_roles.py (add_metadata x2, find_files_by_name), and app/jobs/scheduled_tasks.py (the google_drive.healthcheck entry in integration_healthchecks()).

PACKAGE HOME: app/packages/incident/drive/ (empty __init__.py, no hookimpl — mirrors packages/incident/documents/ and packages/incident/scheduling/). adapters/google_drive.py is the only file in this subdomain allowed to import integrations.google_workspace.google_drive.

PROTOCOL FIX (prerequisite, landed in this task's PR): infrastructure/drive/provider.py's list_folders is missing the query parameter that GoogleDriveProvider already implements and that incident_folder.py's Templates-exclusion filter requires. Widen the Protocol method to accept a keyword-only query: str | None = None, matching the shipped implementation exactly (purely additive, no behavior change to GoogleDriveProvider). Note the correction via --comment on the now-Done TASK-25.1.6.8.1 rather than reopening it.

ADAPTER SHAPE: domain-oriented function names (not SDK passthroughs). Generic file/folder operations (list files, list folders, create folder, create-from-template, name lookup) call infrastructure/drive/factory.py::get_drive_provider(), translate the returned OperationResult into the dict / list[dict] / None shape each call site already handles, and log a warning event (status/error_code/retry_after) on failure — mirrors packages/incident/documents/adapters/google_docs.py's shape. Metadata operations (add/delete/get appProperties) and the incident-template health check remain thin pass-throughs to the legacy integrations.google_workspace.google_drive module — Google-specific feature behavior explicitly kept out of the vendor-neutral DriveProvider per TASK-25.1.6.8.1's shipped scope — preserving their exact current call signatures and let-exceptions-propagate behavior (no new try/except added there: no existing test covers a failure path for these calls today).

FIND_FILES_BY_NAME + APPPROPERTIES: incident_roles.py's manage_roles needs both the document id (name lookup) and its appProperties (ic_id/ol_id) from one legacy call today. Per human direction (2026-09-08 planning session), the adapter routes the name lookup through DriveProvider.find_files_by_name (id/name only) then enriches the first match with a second call to the legacy google_drive.list_metadata(document_id, fields="id, name, appProperties") — an intentional, flagged behavior change: one extra Drive API round trip for this call site only.

INCIDENT-SPECIFIC HEALTH CHECK: the adapter exposes its own health-check function reimplementing today's google_drive.healthcheck() body against the legacy integration's incident-template metadata lookup (DriveProvider has no metadata methods at all in its shipped, narrower contract) — jobs/scheduled_tasks.py calls that instead of google_drive.healthcheck.

LEGACY_FOLDER_DISPLAY_LIMIT: retire the shim only if TASK-81 has landed; otherwise leave it in place unchanged, still pointing at TASK-81.

NOT IN SCOPE: modules/role/role.py (TASK-25.1.6.8.3), modules/reports/google_groups.py (deleted outright by TASK-25.1.6.10), deleting app/integrations/google_workspace/google_drive.py itself (also TASK-25.1.6.10), and packages/incident_draft/adapters/google_docs.py (imports google_drive only for the DRIVE_SCOPES constant; calls none of the operations migrated here).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A new packages/incident/drive/adapters/google_drive.py (no hookimpl, empty subdomain __init__.py) exposes domain-oriented functions for folder/file listing, folder creation, template-based file creation, and name lookup, built on infrastructure.drive.factory.get_drive_provider(), never constructing GoogleDriveProvider directly
- [x] #2 core.py, incident_document.py, incident_folder.py, incident_helper.py, incident_roles.py, and jobs/scheduled_tasks.py call the adapter; none imports integrations.google_workspace.google_drive
- [x] #3 Metadata operations (add/delete/get appProperties) and the incident-template health check are exposed by the adapter as thin pass-throughs to the legacy integrations.google_workspace.google_drive module, not a generic DriveProvider method (DriveProvider has no metadata operations)
- [x] #4 The Templates-folder exclusion is applied by the adapter filtering DriveFile.name client-side, not by passing a vendor-specific query string through DriveProvider; infrastructure/drive/provider.py is not modified by this task
- [x] #5 LEGACY_FOLDER_DISPLAY_LIMIT is left unchanged with its TASK-81 reference intact; this task does not implement the real Slack pagination/search fix
- [x] #6 Existing incident/jobs Drive test coverage (test_incident_document.py, test_incident_folder.py, test_incident_helper.py, test_incident_roles.py, test_recreate_missing_resources.py, test_scheduled_tasks_integration.py) is preserved at the new boundary, plus new unit tests for the adapter itself
- [x] #7 Focused tests, ruff, mypy, and app/bin/check_sdk_typing.py pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STEP 1 — package scaffold
Create app/packages/incident/drive/__init__.py (empty), app/packages/incident/drive/adapters/__init__.py (empty), app/packages/incident/drive/adapters/google_drive.py.

STEP 2 — adapter functions (packages/incident/drive/adapters/google_drive.py)
- _to_dict(file: DriveFile) -> dict[str, Any]: {"id": file.id, "name": file.name} — private helper; no current caller needs mime_type/parents.
- list_folder_files(parent_folder_id: str) -> list[dict[str, Any]]: get_drive_provider().list_files(parent_folder_id); success -> [_to_dict(f) for f in result.data]; failure -> log "incident_drive_list_files_failed" (status/error_code/retry_after) + return [].
- list_child_folders(parent_folder_id: str) -> list[dict[str, Any]]: get_drive_provider().list_folders(parent_folder_id) (NO query parameter — DriveProvider stays vendor-neutral, per the Path A litmus test in decisions/layers.md); success -> filter out any DriveFile whose name contains "Templates" (`f.name and "Templates" not in f.name`), then [_to_dict(f) for f in filtered]; failure -> log "incident_drive_list_folders_failed" + return []. The Templates exclusion is incident-specific business logic, so it lives here, not as a vendor query string threaded through the Protocol.
- create_folder(name: str, parent_folder_id: str) -> dict[str, Any] | None: get_drive_provider().create_folder(name, parent_folder_id); success -> _to_dict(result.data); failure -> log "incident_drive_create_folder_failed" + return None.
- create_document_from_template(name: str, parent_folder_id: str, template_id: str) -> dict[str, Any] | None: get_drive_provider().create_file_from_template(name, parent_folder_id, template_id); same success/failure shape, log "incident_drive_create_document_failed".
- find_document_by_channel_name(channel_name: str) -> dict[str, Any] | None: get_drive_provider().find_files_by_name(channel_name); empty or failed -> log "incident_drive_find_document_failed" (failure case only) + return None; else take first match and call the legacy google_drive.list_metadata(match.id, fields="id, name, appProperties") to enrich, returning {"id": match.id, "appProperties": metadata.get("appProperties", {})}. The list_metadata call keeps its own let-exceptions-propagate behavior (same as the other metadata pass-throughs below).
- add_metadata(file_id: str, key: str, value: str) -> dict[str, Any]: thin pass-through to google_drive.add_metadata.
- delete_metadata(file_id: str, key: str) -> dict[str, Any]: thin pass-through to google_drive.delete_metadata.
- get_metadata(file_id: str, fields: str | None = None) -> dict[str, Any]: thin pass-through to google_drive.list_metadata.
- incident_drive_healthcheck() -> bool: reimplements today's google_drive.healthcheck() body (calls get_metadata(INCIDENT_TEMPLATE), checks "id" in metadata, logs google_drive_healthcheck_success, wraps broad except Exception + logger.exception("google_drive_healthcheck_failed", ...), returns bool) — byte-for-byte parity with the function it replaces.
All failure-path logging mirrors packages/incident/documents/adapters/google_docs.py's shape (structlog warning with status.value/error_code/retry_after).

STEP 3 — core.py
Drop `google_drive` from `from integrations.google_workspace import google_drive, meet` (keep `meet`); add `from packages.incident.drive.adapters import google_drive as incident_drive`. Replace `google_drive.list_files_in_folder(folder_id)` with `incident_drive.list_folder_files(folder_id)`. No other line changes (existing `.get("name", "")` / `["id"]` dict access stays valid).

STEP 4 — incident_document.py
Swap the import the same way. Replace `response = google_drive.create_file_from_template(title, folder, INCIDENT_TEMPLATE)` + `if isinstance(response, dict): document_id = response.get("id")` with `response = incident_drive.create_document_from_template(title, folder, INCIDENT_TEMPLATE)` + `if response: document_id = response.get("id")`.

STEP 5 — incident_folder.py
Swap `from integrations.google_workspace import google_drive, sheets` to keep `sheets`, add the adapter import. Update:
- list_incident_folders() / list_folders_view(): google_drive.list_folders_in_folder(SRE_INCIDENT_FOLDER, "not name contains 'Templates'") -> incident_drive.list_child_folders(SRE_INCIDENT_FOLDER) (the Templates exclusion moves inside the adapter, so the call site drops the query-string argument entirely).
- delete_folder_metadata(): google_drive.delete_metadata(folder_id, key) -> incident_drive.delete_metadata(folder_id, key).
- save_metadata(): google_drive.add_metadata(folder_id, key, value) -> incident_drive.add_metadata(folder_id, key, value).
- get_folder_metadata() / view_folder_metadata(): google_drive.list_metadata(folder_id, fields="id, name, appProperties") -> incident_drive.get_metadata(folder_id, fields="id, name, appProperties").
LEGACY_FOLDER_DISPLAY_LIMIT and its comment stay untouched (AC#5).

STEP 6 — incident_helper.py
Swap the import. Replace `folder = google_drive.create_folder(name, SRE_INCIDENT_FOLDER)` with `folder = incident_drive.create_folder(name, SRE_INCIDENT_FOLDER)`; change the `if isinstance(folder, dict): folder_name = folder.get("name", None)` guard to `if folder: folder_name = folder.get("name")` (adapter already returns dict | None).

STEP 7 — incident_roles.py
Swap the import. save_incident_roles(): both google_drive.add_metadata(file_id, "ic_id"/"ol_id", ...) calls -> incident_drive.add_metadata(...). manage_roles(): replace `documents = google_drive.find_files_by_name(channel_name, fields=...)` + `len(documents) == 0` / `documents[0]` with `document = incident_drive.find_document_by_channel_name(channel_name)` + `if document is None: ...` — the "no incident document found" respond() message and downstream appProperties/id access stay the same, only the emptiness check and access change from list-indexing to a single value.

STEP 8 — jobs/scheduled_tasks.py
Swap the import. Replace `"google_drive": google_drive.healthcheck` with `"google_drive": incident_drive.incident_drive_healthcheck` inside integration_healthchecks()'s dict.

STEP 9 — update existing tests in place (same files, same tree — app/tests/modules/incident/ and app/tests/integration/jobs/, per the TASK-25.1.6.7 precedent of not relocating legacy-module test files during a vendor-import-path swap)
- test_incident_document.py: repoint the `modules.incident.incident_document.google_drive` patch to the adapter import; the `create_file_from_template` mocked return value/assertion is unchanged (already a dict, no fields kwarg passed).
- test_incident_folder.py: repoint every `modules.incident.incident_folder.google_drive[.method]` patch to the adapter alias; update the 5 `list_folders_in_folder(...)` call assertions to `list_child_folders(SRE_INCIDENT_FOLDER)` (single positional arg, no query string) across test_list_incident_folders, test_list_incident_folders_sorted, test_list_incident_folders_truncates_to_the_display_limit, test_list_folders_view, test_list_folders_view_truncates_to_the_display_limit; add a new test proving a folder whose name contains "Templates" is excluded from the adapter's result (this behavior moved from a Google query string into adapter-owned Python logic, so it now needs its own direct test rather than relying on the mocked Drive call to have already filtered it).
- test_incident_helper.py: repoint the two `modules.incident.incident_helper.google_drive.create_folder` patches to the adapter alias; assertions/return values unchanged (dict | None already matches).
- test_incident_roles.py: repoint the three `modules.incident.incident_roles.google_drive.find_files_by_name` patches to the adapter's `find_document_by_channel_name`; change the mocked return value from `[{"id": ..., "appProperties": {...}}]` to `{"id": ..., "appProperties": {...}}` (and to `None` for the no-result case, was `[]`); update `assert_called_once_with` to a single `channel_name` positional arg (no `fields=` kwarg, since that now lives inside the adapter's internal enrichment call).
- test_recreate_missing_resources.py: repoint whatever mock currently targets `google_drive.list_files_in_folder` (core.py's consumer) to the adapter alias — confirm the exact existing patch string during implementation (not read in this planning pass; flagged in Doubts).
- test_scheduled_tasks_integration.py: repoint `@patch("jobs.scheduled_tasks.google_drive")` to patch the adapter import instead; `mock_incident_drive.incident_drive_healthcheck.return_value` replaces `mock_google_drive.healthcheck.return_value` in both TestIntegrationHealthchecksWorkflow tests (test_healthcheck_all_healthy, test_healthcheck_partial_failures).

STEP 10 — new adapter tests
- app/tests/unit/packages/incident/drive/adapters/test_incident_drive_adapter.py: success + classified-OperationResult-failure coverage for list_folder_files, list_child_folders (including the Templates-name-exclusion filter, both a mixed-results case and an all-excluded case), create_folder, create_document_from_template, find_document_by_channel_name (both the two-call enrichment path and the no-match path); success-only pass-through coverage for add_metadata/delete_metadata/get_metadata (mirrors today's untested-failure-path convention); incident_drive_healthcheck success/unhealthy/exception paths (mirror tests/integrations/google_workspace/test_google_drive.py's existing healthcheck test if one exists — confirm during implementation, flagged in Doubts).
- app/tests/unit/packages/incident/drive/adapters/test_incident_drive_boundaries.py: mirrors test_incident_documents_boundaries.py's shape — asserts packages/incident/drive ships no hookimpls, and that no file under app/modules/incident or app/jobs imports integrations.google_workspace.google_drive directly (google_drive.py itself is not deleted this task, so no "moved out of google_workspace" assertion applies here, unlike the Docs precedent).

STEP 11 — guardrails
Run `uv run python bin/check_sdk_typing.py`, `uv run ruff check .`, `uv run mypy` scoped to packages/incident/drive, and the focused pytest files listed in Steps 9-10. infrastructure/drive/ is NOT touched by this task (confirmed: the Templates exclusion moved into the adapter instead of widening DriveProvider — see the vendor-neutrality correction below), so its existing test suite needs no changes.

VENDOR-NEUTRALITY CORRECTION (2026-09-08, human-flagged during plan review): the original version of this plan widened infrastructure/drive/provider.py's list_folders with a `query: str | None = None` parameter to carry Google's own `q=` query-language fragment ("not name contains 'Templates'") through the Protocol. That embeds a vendor-specific DSL into a Path A capability, failing decisions/layers.md's portability litmus test (an operation/param must remain meaningful for at least one other plausible provider — a raw Google Drive query string is not). Corrected: DriveProvider's Protocol and infrastructure/drive/ are untouched by this task; the Templates-folder exclusion is instead applied by the incident adapter itself, filtering the already-typed DriveFile.name client-side after a plain list_folders(parent_folder_id) call. The earlier --comment left on TASK-25.1.6.8.1 proposing the Protocol widening is superseded by a follow-up --comment retracting it.

AC TRACEABILITY
AC#1 (adapter exists, no direct GoogleDriveProvider construction) -> Steps 1, 2, 10.
AC#2 (six consumers call the adapter, none imports google_drive directly) -> Steps 3-8; proven by Step 9's updated patch targets.
AC#3 (metadata + health check are legacy pass-throughs, not a generic DriveProvider method) -> Step 2's add/delete/get_metadata + incident_drive_healthcheck; proven by Step 9's test_scheduled_tasks_integration.py update and Step 10's adapter tests.
AC#4 (Templates exclusion is client-side adapter filtering, not a vendor query string; provider.py untouched) -> Step 2's list_child_folders; proven by Step 9's new Templates-exclusion test and by provider.py having zero diff.
AC#5 (LEGACY_FOLDER_DISPLAY_LIMIT untouched) -> Step 5 (no-op on that constant); proven by grep showing zero diff to that line/comment.
AC#6 (existing test coverage preserved + new adapter tests) -> Steps 9, 10.
AC#7 (guardrails pass) -> Step 11.

TEST MATRIX
Happy path: each adapter function's success branch (Step 10); each of the six consumers' existing happy-path tests continue passing against the new patch target (Step 9).
Boundary: empty list from list_folder_files/list_child_folders; a folder set where every name contains "Templates" (list_child_folders returns []); find_document_by_channel_name with zero matches (-> None, "no incident document found" message preserved); LEGACY_FOLDER_DISPLAY_LIMIT truncation tests unaffected.
Failure: classified HttpError (via DriveProvider) for list/create/find operations, each asserting the logged warning event and the None/[]/False return; incident_drive_healthcheck's exception path.
Not covered by new failure tests (intentionally, matching today's coverage): add_metadata/delete_metadata/get_metadata raising — no existing test exercises this, so none is added here; behavior is unchanged (still propagates), only the import path moved.

DOUBTS AND ASSUMPTIONS FOR HUMAN REVIEW
(a) test_recreate_missing_resources.py's exact mock target for `google_drive.list_files_in_folder` was not read during this planning pass — verify the precise patch string during implementation; low risk, same mechanical pattern as the other five test files.
(b) Assumed no dedicated existing unit test for google_drive.py's own healthcheck() in tests/integrations/google_workspace/test_google_drive.py; if one exists, mirror its cases for incident_drive_healthcheck, else write fresh success/unhealthy/exception cases from the function's own logic — confirm during implementation.
(c) DriveFile.id is always a string (possibly empty on a malformed response, per _build_drive_file's `str(payload.get("id") or "")`); treated as truthy/falsy the same way today's unguarded dict access effectively is — not specially guarded.
(d) packages/incident_draft/adapters/google_docs.py imports google_drive only for the DRIVE_SCOPES constant and calls none of the migrated operations — confirmed out of scope, left untouched.
(e) Fetching all folders under SRE_INCIDENT_FOLDER (including Templates-named ones) instead of excluding them server-side via Google's query language means one extra folder (or however many match "Templates") is paginated through and then discarded client-side — a negligible, accepted performance trade-off for keeping DriveProvider vendor-neutral.

BLAST RADIUS AND ROLLBACK
All production changes are import-path swaps at six call sites; infrastructure/drive/ (including its Protocol) is not modified at all by this task, and integrations/google_workspace/google_drive.py is not modified or deleted (TASK-25.1.6.10 owns that) — so a single `git revert` of this PR fully restores today's behavior with no partial-migration state. No terraform, CI, or settings changes. Two intentional, narrowly-scoped behavior changes are called out above (find_document_by_channel_name's extra Drive API round trip; the Templates-exclusion moving from a server-side query to a client-side filter).

SIZE GATE
Production: packages/incident/drive/{__init__.py, adapters/__init__.py, adapters/google_drive.py} (3 new files, ~150-180 LOC), core.py/incident_document.py/incident_folder.py/incident_helper.py/incident_roles.py/scheduled_tasks.py (6 edits, ~60-90 LOC total) = 9 production files, roughly 220-270 LOC — comfortably under both the 400-LOC and 10-file thresholds. One subsystem (packages/incident/drive plus its six already-coordinator-scoped consumers); the only behavior changes are the two narrowly flagged ones above, not a mixed refactor-plus-unrelated-feature change. Fits one PR; no decomposition needed.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented incident Drive adapter and migrated incident/jobs consumers. Added required empty package initializers after verification. Evidence: make test reported green; focused adapter and migrated-consumer suite passes (144 passed); uv run python bin/check_sdk_typing.py passes; uv run ruff check . passes; uv run mypy packages/incident/drive passes. Templates filtering is client-side, legacy metadata/healthcheck remain adapter pass-throughs, and LEGACY_FOLDER_DISPLAY_LIMIT is unchanged. Task remains In Progress for human DoD verification; not set to Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-08 18:57
---
TASK-81 created (2026-09-08) as the linked Slack pagination/search follow-up for LEGACY_FOLDER_DISPLAY_LIMIT. AC#4 updated to reference it by ID instead of describing it generically.
---

created: 2026-09-08 20:12
---
2026-09-08 portability adjustment: this task remains implementable, but its adapter boundary must distinguish common Drive operations from incident-specific Google metadata. Migrate core.py, incident_document.py, incident_folder.py, incident_roles.py, and scheduled_tasks.py so consumers call the incident-owned adapter only. The adapter uses DriveProvider for folder/file listing, template creation, and name lookup. It owns appProperties reads/writes and the incident-template health check as Google-specific feature behavior, temporarily delegating to the legacy google_workspace.google_drive metadata helpers (or an equivalent adapter-local classified client call) until TASK-25.1.6.10 removes that integration. Do not restore get_metadata/set_metadata_property/delete_metadata_property to the vendor-neutral DriveProvider; revise AC#3's wording from DriveProvider.get_metadata to the incident adapter's Google metadata helper. This is a full consumer migration: legacy modules/jobs no longer import the Google integration directly; only the feature adapter may retain the temporary vendor dependency.
---

created: 2026-09-08 20:48
---
PLAN WRITTEN 2026-09-08 (task-planner). Grounded against the actually-shipped TASK-25.1.6.8.1 code (its narrower, vendor-neutral final DriveProvider contract — no metadata methods, no app_properties field on DriveFile — differs from its own stale Description/Implementation-Plan prose, per its own comment #1 and notes). Human confirmed via vscode_askQuestions: (1) subdomain name is packages/incident/drive (not the task's originally proposed 'folders', since scope spans more than folders); (2) modules/incident/incident_helper.py added as a 6th consumer — fresh grep found its create_folder call, absent from the coordinator's and this task's original file list; (3) infrastructure/drive/provider.py's list_folders Protocol gets a small additive 'query' parameter fix in this task's PR (GoogleDriveProvider already implements it; the shipped Protocol just omitted it) rather than blocking on a separate task; (4) incident_roles.py's find_files_by_name migrates to DriveProvider for the name lookup, then enriches the first match with a second legacy google_drive.list_metadata call for appProperties (ic_id/ol_id) — an accepted extra API round trip, matching TASK-25.1.6.8.1's own comment that name lookup should route through DriveProvider. Also confirmed out of scope: packages/incident_draft/adapters/google_docs.py imports google_drive only for the DRIVE_SCOPES constant, calls none of the migrated operations. Fits one PR (10 production files at the file-count boundary, ~250-300 LOC, one subsystem); no decomposition needed.
---

created: 2026-09-08 21:06
---
VENDOR-NEUTRALITY CORRECTION (2026-09-08): human review flagged that the plan's original 'query' parameter on DriveProvider.list_folders would leak Google's own q=-language string through a Path A Protocol, failing layers.md's portability litmus test. Plan revised: infrastructure/drive/provider.py is untouched by this task; the Templates-folder exclusion is applied as a client-side filter on DriveFile.name inside the incident adapter's list_child_folders. AC#4 and the size gate updated accordingly (9 production files, not 10); the earlier --comment on TASK-25.1.6.8.1 proposing the Protocol change was retracted.
---
<!-- COMMENTS:END -->

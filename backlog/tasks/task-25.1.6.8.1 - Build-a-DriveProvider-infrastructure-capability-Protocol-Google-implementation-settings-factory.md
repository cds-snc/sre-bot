---
id: TASK-25.1.6.8.1
title: >-
  Build a DriveProvider infrastructure capability (Protocol, Google
  implementation, settings, factory)
status: To Do
assignee: []
created_date: '2026-09-08 18:55'
updated_date: '2026-09-08 18:56'
labels:
  - clients
  - phase-3
  - infrastructure
milestone: m-3
dependencies:
  - TASK-25.1.6.3
references:
  - decisions/layers.md
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/infrastructure/directory/provider.py
  - app/infrastructure/directory/google.py
  - app/infrastructure/directory/factory.py
  - app/infrastructure/directory/settings.py
  - app/infrastructure/directory/models.py
  - app/integrations/google_workspace/google_drive.py
  - app/integrations/google_workspace/client.py
parent_task_id: TASK-25.1.6.8
priority: high
ordinal: 155000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Introduce app/infrastructure/drive/ as a new Path A infrastructure capability, mirroring app/infrastructure/directory/{provider,google,factory,models,settings}.py's exact shape (Protocol + Google implementation + settings + singleton factory). This is the foundation both TASK-25.1.6.8.2 (incident feature adapter) and TASK-25.1.6.8.3 (role feature adapter) build on.

WHY PATH A, NOT PATH B: two independent feature consumers of Google Drive already exist today (the incident feature and the talent/hiring `role` workflow, in modules/role/role.py). decisions/layers.md promotes a Path B adapter to shared infrastructure "when a second feature needs the same adapter" — here that second consumer is already known, so building one Path B adapter and promoting it later would be pure churn. See TASK-25.1.6's 2026-09-08 pivot comment for the full rationale.

SCOPE (this task only): the new infrastructure/drive/ package and its own tests. This task does NOT touch any consumer file (core.py, incident_document.py, incident_folder.py, incident_roles.py, jobs/scheduled_tasks.py, modules/role/role.py, modules/reports/google_groups.py) and does NOT delete app/integrations/google_workspace/google_drive.py — google_drive.py keeps serving its current callers until TASK-25.1.6.8.2/.8.3 migrate them and TASK-25.1.6.10 removes the last reference (modules/reports/google_groups.py).

PROTOCOL SHAPE, derived from the 7 in-scope consumers' actual call sites (grep-verified against app/modules/incident/{core,incident_document,incident_folder,incident_roles}.py, app/modules/role/role.py, app/jobs/scheduled_tasks.py):
- warmup() -> OperationResult[None] and health_check() -> OperationResult[None], mirroring DirectoryProvider (health_check is a fast liveness check, no expensive API call — it must NOT reproduce today's incident-specific "fetch the incident template's metadata" check; that stays a feature-level concern built on get_metadata(), see TASK-25.1.6.8.2).
- create_folder(name, parent_folder_id, *, fields=None, delegated_user_email=None) -> OperationResult[DriveFile]
- list_folders(parent_folder_id, query=None, *, delegated_user_email=None) -> OperationResult[list[DriveFile]] — preserves the q-DSL query composition (`parents in '<id>' and mimeType = 'application/vnd.google-apps.folder' and trashed=false`, appending an optional caller-supplied query fragment) and the full list_next pagination loop.
- list_files(parent_folder_id, *, delegated_user_email=None) -> OperationResult[list[DriveFile]]
- find_files_by_name(name, parent_folder_id=None, *, fields=None, delegated_user_email=None) -> OperationResult[list[DriveFile]] — preserves its q-DSL composition and pagination.
- create_file_from_template(name, parent_folder_id, template_id, *, delegated_user_email=None) -> OperationResult[DriveFile]
- copy_file_to_folder(file_id, name, source_parent_id, destination_folder_id, *, delegated_user_email=None) -> OperationResult[DriveFile] — preserves the copy-then-move composition (files().copy then files().update with addParents/removeParents).
- get_metadata(file_id, *, fields=None, delegated_user_email=None) -> OperationResult[DriveFile]
- set_metadata_property(file_id, key, value, *, delegated_user_email=None) -> OperationResult[DriveFile]
- delete_metadata_property(file_id, key, *, delegated_user_email=None) -> OperationResult[DriveFile]

NOT PORTED: google_drive.py::create_file (the file_type-to-mimeType map + its ValueError) and google_drive.py::create_file's only caller, modules/reports/google_groups.py, is deleted outright by TASK-25.1.6.10, not migrated — per TASK-25.1.6's 2026-09-08 scope update. Do not add a create_file-equivalent Protocol method.

MODEL: a single canonical `DriveFile` frozen dataclass (id, name, mime_type, parents: tuple[str, ...], app_properties: dict[str, str] | None, provider) used for both files and folders — Google Drive's own data model has no separate folder type (a folder is a File with a special mimeType), so canonicalizing to one type is correct, not a simplification that loses information.

SETTINGS: `DriveSettings(InfrastructureSettings)` mirrors DirectorySettings (a `provider: Literal["google"] = "google"` field via `DRIVE_PROVIDER`, default "google" — no other backend is implemented today, but the field keeps the shape consistent and swappable).

FACTORY: `get_drive_provider()` singleton via `@cache`, mirrors `get_directory_provider()` — builds `GoogleDriveProvider` from `integrations.google_workspace.client.get_drive_service` + `get_google_workspace_settings()` (for the default delegated_user_email, `SRE_BOT_EMAIL`). Unlike DirectoryProvider's get_service partial (delegation fixed at construction), Drive's Protocol methods accept `delegated_user_email` per call, since one existing caller (role.py) passes `BOT_EMAIL` explicitly per call while every other caller passes nothing (defaults to None/no delegation) — do not fix delegation at factory-construction time, preserve today's per-call flexibility.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 infrastructure/drive/provider.py defines a runtime_checkable DriveProvider Protocol with warmup, health_check, create_folder, list_folders, list_files, find_files_by_name, create_file_from_template, copy_file_to_folder, get_metadata, set_metadata_property, delete_metadata_property, all OperationResult-wrapped
- [ ] #2 infrastructure/drive/models.py defines a single frozen DriveFile dataclass used for both files and folders; no separate Folder type
- [ ] #3 infrastructure/drive/google.py::GoogleDriveProvider implements the Protocol via integrations.google_workspace.client.get_drive_service, classifies HttpError with classify_google_error, and preserves today's q-DSL query composition, list_next pagination, and copy-then-move composition byte-for-byte
- [ ] #4 infrastructure/drive/settings.py::DriveSettings (InfrastructureSettings) and infrastructure/drive/factory.py::get_drive_provider() (cached singleton) exist, mirroring infrastructure/directory's settings+factory shape
- [ ] #5 app/integrations/google_workspace/google_drive.py is untouched and still exists; no consumer file is modified by this task
- [ ] #6 Unit tests cover GoogleDriveProvider (success, HttpError classification, pagination across multiple pages, copy-then-move) plus settings and factory construction
- [ ] #7 mypy, ruff, and app/bin/check_sdk_typing.py pass for the new package
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
STEP 1 - models.py
Add app/infrastructure/drive/models.py::DriveFile (frozen dataclass): id: str, name: str | None, mime_type: str | None, parents: tuple[str, ...] = (), app_properties: dict[str, str] | None = None, provider: str | None = None. One canonical type for both files and folders (Drive's own model has no separate Folder type).

STEP 2 - provider.py
Add app/infrastructure/drive/provider.py::DriveProvider (@runtime_checkable Protocol), mirroring infrastructure/directory/provider.py's docstring conventions (OperationResult-wrapped, no exceptions cross the boundary). Methods (all return OperationResult[...]):
  warmup() -> OperationResult[None]
  health_check() -> OperationResult[None]  # fast liveness only, no Drive API round-trip
  create_folder(name: str, parent_folder_id: str, *, fields: str | None = None, delegated_user_email: str | None = None) -> OperationResult[DriveFile]
  list_folders(parent_folder_id: str, query: str | None = None, *, fields: str | None = None, delegated_user_email: str | None = None) -> OperationResult[list[DriveFile]]
  list_files(parent_folder_id: str, *, fields: str | None = None, delegated_user_email: str | None = None) -> OperationResult[list[DriveFile]]
  find_files_by_name(name: str, parent_folder_id: str | None = None, *, fields: str | None = None, delegated_user_email: str | None = None) -> OperationResult[list[DriveFile]]
  create_file_from_template(name: str, parent_folder_id: str, template_id: str, *, fields: str | None = None, delegated_user_email: str | None = None) -> OperationResult[DriveFile]
  copy_file_to_folder(file_id: str, name: str, source_parent_id: str, destination_folder_id: str, *, delegated_user_email: str | None = None) -> OperationResult[DriveFile]
  get_metadata(file_id: str, *, fields: str | None = None, delegated_user_email: str | None = None) -> OperationResult[DriveFile]
  set_metadata_property(file_id: str, key: str, value: str, *, delegated_user_email: str | None = None) -> OperationResult[DriveFile]
  delete_metadata_property(file_id: str, key: str, *, delegated_user_email: str | None = None) -> OperationResult[DriveFile]

STEP 3 - google.py::GoogleDriveProvider
Constructor takes an injected get_service: Callable[[list[str], str | None], DriveResource] (mirrors GoogleDirectoryProvider's injected get_service, but Drive needs delegated_user_email threaded per-call, so the injected callable takes it as a parameter rather than being pre-bound via partial). Internal helpers mirror GoogleDirectoryProvider's _call/_map_sdk_exception shape (try/except HttpError -> classify_google_error -> OperationResult.error). Port byte-for-byte from google_drive.py:
  - q-DSL composition: list_folders builds "parents in '<id>' and mimeType = 'application/vnd.google-apps.folder' and trashed=false" + optional " and {query}"; list_files builds "parents in '<id>' and mimeType != 'application/vnd.google-apps.folder' and trashed=false"; find_files_by_name builds "trashed=false and name='<name>'" + optional " and '<folder_id>' in parents".
  - Pagination: a private _collect_files(files_resource, request) -> list[dict] loop identical to google_drive.py's, calling request.execute(num_retries=...) then files_resource.list_next(request, response) until None. Reuse across list_folders/list_files/find_files_by_name.
  - Metadata: get_metadata/set_metadata_property/delete_metadata_property call files().get / files().update(body={"appProperties": {key: value}}) / files().update(body={"appProperties": {key: None}}), all with supportsAllDrives=True.
  - copy_file_to_folder: files().copy(...) for the id, then files().update(addParents=destination, removeParents=source, body={}) — preserve the two-call copy-then-move composition and its two debug log events (google_drive_file_copied, google_drive_file_moved).
  - create_folder / create_file_from_template: files().create(body={"name":..., "parents":[...], "mimeType": "application/vnd.google-apps.folder"}) and files().copy(fileId=template, body={"name":..., "parents":[...]}) respectively.
  - Map every raw dict response through a private _build_drive_file(item: dict) -> DriveFile.
  - warmup(): a cheap Drive call proving credentials/connectivity (e.g. files().list(pageSize=1) or an about().get() equivalent if the stub exposes it — check DriveResource stub surface first; fall back to files().list(pageSize=1, fields="files(id)") if not).
  - health_check(): must NOT reproduce today's google_drive.py::healthcheck() (which checks a specific incident template file's metadata — that is incident-domain knowledge that does not belong in this generic provider). Implement as a fast local check (e.g. verify get_service can be constructed) with no required Drive API round-trip, matching DirectoryProvider.health_check()'s "must not make expensive remote API calls" contract. TASK-25.1.6.8.2's incident adapter separately exposes its own incident-specific health function built on get_metadata(), for jobs/scheduled_tasks.py to keep calling.

STEP 4 - settings.py
DriveSettings(InfrastructureSettings): provider: Literal["google"] = Field(default="google", alias="DRIVE_PROVIDER"). Mirrors DirectorySettings's shape/docstring conventions; no other fields needed today (no cache/warmup-timeout requirement was named by any consumer).

STEP 5 - factory.py
build_google_drive_provider(get_service, drive_settings) -> DriveProvider (pure constructor, testable). get_drive_provider() -> DriveProvider, @cache singleton, provider_key dispatch (only "google" today, raise ValueError otherwise per get_directory_provider()'s precedent). get_service is a partial around integrations.google_workspace.client.get_drive_service binding scopes=google_drive.DRIVE_SCOPES (import the constant, do not redefine it — google_drive.py keeps owning DRIVE_SCOPES until TASK-25.1.6.10 deletes it, at which point the constant relocates here; note this as a forward dependency in the notes, not resolved in this task).

STEP 5B — verify DRIVE_SCOPES ownership doesn't create a premature deletion. Since google_drive.py isn't deleted until TASK-25.1.6.10, importing DRIVE_SCOPES from it here is a temporary cross-reference; TASK-25.1.6.10's plan must include moving DRIVE_SCOPES into infrastructure/drive/ (or duplicating the constant) as part of its own final cleanup — flag this explicitly as a note on TASK-25.1.6.10 once this task ships.

STEP 6 - tests
New app/tests/unit/infrastructure/drive/ tree: test_google_drive_provider.py (success + HttpError-classification path per method; a dedicated multi-page test for at least one list method proving the list_next loop aggregates across pages — the AC#6 pagination proof originally scoped to TASK-25.1.6.8), test_settings.py, test_factory.py (mirroring the directory equivalents' structure/fixtures). Reuse the FakeResp/HttpError-construction helper convention already duplicated per-vendor-test-file in this repo (do not centralize it).

STEP 7 - guardrails
Run app/bin/check_sdk_typing.py and confirm the new package is clean (no execute_google_api_request, no getattr-based dispatch). Run mypy/ruff scoped to app/infrastructure/drive/.

DOUBTS FOR HUMAN REVIEW (not resolved unilaterally):
(a) warmup()/health_check() semantics above are a best-effort mirror of DirectoryProvider's contract; DriveResource's stub surface must be checked for a cheap connectivity probe (e.g. about().get()) before committing to files().list(pageSize=1) as the warmup call — confirm during implementation, not blocking this plan.
(b) DRIVE_SCOPES stays imported from the not-yet-deleted google_drive.py until TASK-25.1.6.10 — flagged above, not a design flaw, just a sequencing note for whoever picks up .10.
<!-- SECTION:PLAN:END -->

---
id: TASK-25.1.5
title: Migrate Google Drive integration off execute_google_api_call
status: Done
assignee:
  - '@me'
created_date: '2026-07-31 18:33'
updated_date: '2026-09-02 14:32'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.4
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/google_drive.py
  - app/integrations/google_workspace/client.py
parent_task_id: TASK-25.1
priority: high
ordinal: 116000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 (largest, done last) of TASK-25.1. Migrate integrations/google_workspace/google_drive.py off google_service.py's execute_google_api_call dispatcher onto a factory-built, stub-typed DriveResource (google-api-python-client-stubs, per decisions/sdk-typing.md item 3) plus classify_google_error. Done last so the factory/classify extraction pattern is already proven on 4 smaller surfaces.

CONSUMERS (re-grepped 2026-09-02): NINE production files, not the eight originally listed. modules/incident/incident_document.py, modules/incident/incident_helper.py, modules/incident/incident_folder.py, modules/incident/core.py, modules/incident/incident_roles.py, modules/role/role.py, jobs/scheduled_tasks.py, modules/reports/google_groups.py, and packages/incident_draft/adapters/google_docs.py (added after this task was first scoped - the same concurrent-work drift TASK-25.1.2 found for Docs). Only Drive-related calls in each file are in scope; their Docs/Sheets/Directory calls belong to sibling slices.

INTENT (human-directed 2026-09-02): the point of adopting stubs is to stop hand-mirroring and guessing SDK parameters. So this slice does not merely swap the dispatcher for a factory - it removes the vendor module's guessed parameter choices and realigns each call with the real SDK contract, keeping google_drive.py only for what it genuinely adds over the SDK (the Drive q-DSL query builders, the mimeType map, the copy-then-move composition, the healthcheck, and the appProperties metadata convention).

SCOPE SPLIT: the adapter-side work was split out to TASK-25.1.5.1 (repoint packages/incident_draft/adapters/google_docs.py onto get_drive_service with its own inline try/except, then delete the zero-caller get_file_by_id) because bundling it tripped the single-PR size gate - its test file is 1704 lines with 135 mock_drive references. Deleting the orphaned google_service.py module itself was likewise split out to TASK-25.1.7; no task previously owned it.

KEY CORRECTION found during planning: the hardcoded fields= projections in this module are NOT uniformly "guessed params". Two groups behave oppositely. On files.get/files.update (list_metadata, add_metadata, delete_metadata) the projection is LOAD-BEARING - appProperties is not in the Drive v3 default response field set, so removing it would silently drop the metadata the incident-folder Slack UI reads. On the three files.list calls the projection is HARMFUL - fields="files(...)" omits nextPageToken, so files().list_next() returns None after page one and pagination has been effectively dead. Combined with pageSize=1 on find_files_by_name and pageSize=25 on the folder/file listings, this is a live truncation bug: modules/incident/core.py only scans the first 25 files of an incident folder before deciding to create a duplicate incident document.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/google_workspace/google_drive.py no longer calls execute_google_api_call: every Drive call is built from a new integrations/google_workspace/client.py::get_drive_service factory returning a stub-typed DriveResource (googleapiclient._apis.drive.v3), and failures are classified by classify_google_error per the outbound-clients.md contract
- [x] #2 No Drive SDK parameter is guessed or hidden from callers: fields and pageSize are exposed as SDK-named, stub-typed parameters with today's values as defaults where they are load-bearing; supportsAllDrives=True is retained as a deliberate product decision with a one-line rationale; the files().update move call passes the body the stub requires
- [x] #3 Pagination is correct against the real SDK: find_files_by_name, list_folders_in_folder and list_files_in_folder include nextPageToken in their projection and loop files().list_next() to exhaustion, and the previously-latent truncation is documented in the task notes
- [x] #4 The Slack folder views keep a named, commented display cap in modules/incident/incident_folder.py so views_open stays inside Slack's 100-block and 100-option limits now that folder listings are unbounded; the cap is registered as a temporary shim with TASK-25.1.6
- [x] #5 All nine production consumers keep working (existing tests pass). The only intended behavior changes are the pagination fix and the removed truncation, each named explicitly in the task notes; no consumer loses a response field it reads today
- [x] #6 classify_google_error is verified against the Drive surface: it either gains a Drive-specific mapped family with unit coverage under tests/unit/integrations/google_workspace/, or the task records that Drive raises only HttpError statuses already covered by the existing table, backed by an error-propagation test per migrated function
- [x] #7 execute_google_api_call has zero remaining callers repo-wide (grep-verified, feeding TASK-25.1 AC#1), and integrations/google_workspace/google_drive.py is pruned from app/bin/baselines/sdk_typing_antipatterns.txt with python3 bin/check_sdk_typing.py passing
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLANNED 2026-09-02 (task-planner). Grounded in a fresh repo grep and in the installed stub package, not in the task's original prose.

DECISION (human-directed this session, three choices recorded)
1. This is not a like-for-like dispatcher swap. Stubs were adopted so the codebase stops hand-mirroring and guessing SDK parameters; google_drive.py survives only for what it genuinely adds over the SDK, and every SDK parameter it still sets is either a documented product decision or a caller-overridable, SDK-named argument.
2. Pagination is fixed rather than preserved, with a temporary display cap at the two Slack call sites, tracked by TASK-25.1.6.
3. The adapter repoint and the google_service.py deletion were split out (TASK-25.1.5.1, TASK-25.1.7) because bundling them trips the single-PR size gate.

GROUND TRUTH ESTABLISHED
- Stubs: googleapiclient-stubs 1.39.0 ships _apis/drive/v3 with DriveResource and a File schema (TypedDict, total=False, appProperties: dict[str, Any]) - so dict literals type-check without cast, unlike the Docs/Sheets slices.
- googleapiclient bundles discovery_cache/documents/drive.v3.json, so client.py's static_discovery=True is safe for Drive.
- files().update() in the stub declares body: File as REQUIRED. copy_file_to_folder's second call (the move) passes no body today. File is total=False, so body={} type-checks and is the minimal compliant form.
- handle_google_api_errors' non_critical_errors table has no google_drive entries, so removing the decorator changes no swallow/raise semantics - only the log event name (google_api_http_error -> google_api_request_failed), matching the shipped sibling slices.
- After this slice, execute_google_api_call has zero callers: the only remaining matches repo-wide are bin/check_sdk_typing.py's own detection regex and a hasattr assertion at tests/integrations/google_workspace/test_sheets.py:250.

THE fields= FINDING (drives most of this plan)
The module's hardcoded fields= projections split into two groups that must be treated oppositely.
LOAD-BEARING (keep the default, expose an override): list_metadata's "id, name, appProperties" and add_metadata/delete_metadata's "name, appProperties". appProperties is not in the Drive v3 default response field set for files.get/files.update, so dropping the projection would silently strip the metadata that modules/incident/incident_folder.py's metadata_items() reads ('appProperties' not in folder).
HARMFUL (fix): the three files.list calls use fields="files(...)" which omits nextPageToken, so files().list_next() returns None after page one. Pagination has been dead. Together with pageSize=1 (find_files_by_name) and pageSize=25 (both folder/file listings) this is a live truncation bug - modules/incident/core.py:170 scans only the first 25 files of an incident folder before concluding no incident document exists and creating a duplicate.

STEPS

1. integrations/google_workspace/client.py: add get_drive_service(scopes, delegated_user_email=None) -> DriveResource, mirroring get_docs_service exactly (cast over _build_service("drive", "v3", ...)), plus the TYPE_CHECKING import of DriveResource from googleapiclient._apis.drive.v3 with the same pyright ignore comment the siblings use. About 8 LOC. No other change to client.py; execute_google_api_request is reused as-is (temporary deviation, TASK-25.1.6).

2. integrations/google_workspace/google_drive.py header: drop "from integrations.google_workspace import google_service" and its three re-exports. Import client as google_service_client (sibling naming). Define DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"] and source INCIDENT_TEMPLATE from get_google_resources_config().incident_template_id directly (google_service.py is deleted by TASK-25.1.7). Delete DELETED_USER_EMAIL... specifically: delete DELEGATED_USER_EMAIL, which is dead (grep-confirmed: no reader anywhere, including inside this module). Add a module-private _collect_files(files_resource, request) -> list[dict] mirroring google_directory.py::_collect_pages: it takes the ALREADY-BUILT request so the .list(...) call stays at the call site and is stub-checked, loops execute_google_api_request + files_resource.list_next(request, response), and accumulates response.get("files", []).

3. Migrate the four single-call, non-list functions. Each drops @handle_google_api_errors, builds the service via get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=...), and calls execute_google_api_request(service.files().<method>(...)). Signatures become explicit and typed - no **kwargs - using the SDK's own parameter names for pass-throughs (house style, see sheets.py's spreadsheetId; ruff does not enable pep8-naming so camelCase args are fine):
   - add_metadata(file_id: str, key: str, value: str, *, fields: str | None = "name, appProperties", delegated_user_email: str | None = None) -> dict, body: File = {"appProperties": {key: value}}, supportsAllDrives=True.
   - delete_metadata(file_id, key, *, fields="name, appProperties", delegated_user_email=None), body {"appProperties": {key: None}}.
   - list_metadata(file_id, *, fields="id, name, appProperties", delegated_user_email=None) -> files().get(...).
   - get_file_by_id(file_id, *, fields=None, delegated_user_email=None) -> files().get(...). Kept here; TASK-25.1.5.1 deletes it once the adapter no longer calls it.
   The defaults reproduce today's wire behavior exactly; the difference is that a caller can now override them, and mypy checks the value.

4. Migrate the three create/copy functions the same way:
   - create_folder(name, parent_folder, *, fields=None, delegated_user_email=None): body File {"name", "parents": [parent_folder], "mimeType": "application/vnd.google-apps.folder"}. modules/role/role.py passes fields="id" positionally today - keep the third positional slot compatible or update that one call site; prefer keeping fields as the third positional parameter so role.py is untouched.
   - create_file(name, folder, file_type, *, fields="id, name", delegated_user_email=None): keep the mimeType map and the ValueError for an unknown file_type (real domain logic, and the ValueError is asserted by an existing test).
   - create_file_from_template(name, folder, template, *, fields=None, delegated_user_email=None) -> files().copy(fileId=template, body={"name", "parents": [folder]}, supportsAllDrives=True, fields=fields). Kept - modules/incident/incident_document.py:29 still calls it; retirement belongs to TASK-25.1.6.

5. Migrate copy_file_to_folder(file_id, name, parent_folder_id, destination_folder_id, *, delegated_user_email=None) -> str. Build the service once and reuse it for both calls. Call one: files().copy(fileId=file_id, body={"name": name, "parents": [parent_folder_id]}, supportsAllDrives=True, fields="id") then read ["id"] from the response dict directly - the current code's [0]["id"] only works because it indexes the dispatcher's (response, unsupported_params) tuple, which no longer exists. Call two: files().update(fileId=copied_id, body={}, addParents=destination_folder_id, removeParents=parent_folder_id, supportsAllDrives=True, fields="id"). body={} is the minimal value the stub requires; see doubt (b). Replace the two print() calls with logger.debug - they are on lines this step rewrites anyway and print() in a request path is a defect.

6. Migrate and FIX the three list functions. Each keeps its q-DSL construction verbatim (genuine domain logic and the exact string is asserted by tests), builds files = service.files(), builds request = files.list(...) at the call site so the stub checks it, and returns _collect_files(files, request):
   - find_files_by_name(name, folder_id=None, *, fields="nextPageToken, files(appProperties, id, name)", pageSize=100, delegated_user_email=None) -> list[dict]. pageSize goes 1 -> 100 (the Drive default) and nextPageToken enters the projection, so all matches are returned. Both callers already index [0] after a len() check, so no consumer change is needed.
   - list_folders_in_folder(folder, query=None, *, fields="nextPageToken, files(id, name)", pageSize=100, delegated_user_email=None).
   - list_files_in_folder(folder, *, fields="nextPageToken, files(id, name)", pageSize=100, delegated_user_email=None).
   Keep corpora="user", includeItemsFromAllDrives=True and supportsAllDrives=True unchanged (product decisions about this workspace's shared-drive layout), each with a one-line comment.

7. healthcheck(): unchanged logic; it now calls the migrated list_metadata(INCIDENT_TEMPLATE) and keeps its broad try/except (a probe legitimately swallows).

8. THE SHIM (AC#4). Uncapping list_folders_in_folder is safe for the data but not for Slack. modules/incident/incident_folder.py::folder_item emits THREE blocks per folder, so today's 25-folder cap yields 75 blocks, under Slack's 100-block modal limit; unbounded, a workspace with more than 33 product folders breaks views_open. list_incident_folders() additionally feeds Slack option lists at four call sites (modules/incident/incident.py:71,85 and modules/incident/core.py:93,490), where the limit is 100 options. Add one named module constant in incident_folder.py, e.g. LEGACY_FOLDER_DISPLAY_LIMIT = 25, with a one-line comment stating it exists to respect Slack's block/option limits and is a temporary shim, and apply it in both list_incident_folders() and list_folders_view(). Do NOT put the cap back in the vendor module. Record the shim on TASK-25.1.6 via --comment.

9. Prune "integrations/google_workspace/google_drive.py" from app/bin/baselines/sdk_typing_antipatterns.txt (the checker only ratchets down). Leave the google_service.py entry - TASK-25.1.7 removes it.

10. Rewrite app/tests/integrations/google_workspace/test_google_drive.py (457 lines, about 20 tests, all patching google_service.execute_google_api_call). Patch integrations.google_workspace.google_drive.google_service_client.get_drive_service instead, returning a MagicMock whose .files() yields a resource mock; assert the exact .files().<method>(**kwargs) call args per function, plus the scopes and delegated_user_email passed to the factory. Keep every existing q-string and body assertion verbatim. Update the two pagination-shape assertions and the copy_file_to_folder side_effect, which currently return lists that only worked because they indexed the dispatcher's tuple. Keep the test file in place (siblings .1 through .4 all left theirs under tests/integrations/google_workspace/).

11. Add the coverage the dispatcher-based tests never had: multi-page pagination (list_next returns a second request once, then None; both pages concatenated); a page missing the "files" key contributes nothing; an HttpError raised by .execute() propagates out of each migrated function (proving decorator removal); create_file still raises ValueError for an unknown file_type without touching the SDK.

12. Consumer tests: tests/modules/incident/test_incident_folder.py needs new/updated cases for the display cap (more folders returned than the cap, result truncated) and its existing list_metadata patches stay at the modules.incident.incident_folder.google_drive boundary, so they need no edits. tests/modules/incident/test_incident_document.py, tests/modules/incident/test_incident_roles.py, tests/modules/role/test_role.py, tests/modules/reports (if present) and tests/integration/jobs/test_scheduled_tasks_integration.py all patch at the modules.<x>.google_drive boundary and should need zero edits - verify, do not assume. modules/reports/google_groups.py has NO test file; record in Notes that its two Drive call sites are unguarded by automated coverage before and after.

13. Re-run checks: grep execute_google_api_call in google_drive.py (expect zero) and repo-wide (expect only check_sdk_typing.py and the test_sheets.py hasattr line); python3 bin/check_sdk_typing.py; bin/generate_client_usage_matrix.sh; make test (use the Makefile split, not the single-process whole-tree run, which has pre-existing cross-directory-pollution failures); uv run ruff check .; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' - note the pre-existing whole-tree error baseline, the bar is zero errors naming the touched files.

AC-TO-STEP-TO-TEST
- AC#1 (factory + stub-typed DriveResource + classify) -> steps 1-7, verified by step 10's factory-boundary patches and step 11's error-propagation tests, plus the step 13 greps.
- AC#2 (no guessed/hidden SDK params, body on the move call) -> steps 3-6, verified by step 10's exact call-arg assertions and by mypy resolving files().update/copy/get/list signatures.
- AC#3 (correct pagination) -> step 6, verified by step 11's multi-page and missing-key tests.
- AC#4 (Slack display cap) -> step 8, verified by step 12's truncation test.
- AC#5 (nine consumers keep working) -> steps 3-7 preserve every signature's positional shape and return type; verified by step 12's untouched consumer tests plus the explicit no-coverage note for modules/reports/google_groups.py.
- AC#6 (classify_google_error verified against Drive) -> step 11's error-propagation tests; expected outcome is "no new family needed" (Drive raises googleapiclient HttpError, whose 404/401/403/429/5xx statuses the existing table already maps), to be recorded in Notes.
- AC#7 (zero dispatcher callers, baseline pruned) -> steps 9 and 13.

TEST MATRIX
Happy path per function: exact .files().<method>(**kwargs) args, including body shape, supportsAllDrives, fields and pageSize defaults; returned dict/list passes through unchanged. Delegation and scopes: default (None) and explicit override, asserted at the factory call. Pagination: single page (list_next -> None), two pages concatenated, a page with no "files" key. Query construction: find_files_by_name with and without folder_id and with an empty-string folder_id; list_folders_in_folder with and without an extra query. Composition: copy_file_to_folder issues copy then update in order and returns the updated id. Validation: create_file raises ValueError for an unknown file_type and never builds a service. Errors: HttpError from .execute() propagates for every migrated function. Shim: folder list longer than LEGACY_FOLDER_DISPLAY_LIMIT is truncated in both list_incident_folders and list_folders_view.
Commands: cd app && uv run pytest tests/integrations/google_workspace tests/unit/integrations/google_workspace tests/modules/incident tests/modules/role tests/unit/packages/incident_draft -v; then make test; uv run ruff check .; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'.

ASSUMPTIONS AND DOUBTS
(a) VERIFY BEFORE CODING - the appProperties claim in step 3 is load-bearing for AC#5. The plan asserts that Drive v3's default response for files.get/files.update does not include appProperties, which is why those projections must stay. Confirm against Google's Drive v3 reference (or an actual call) before finalizing the defaults; if appProperties were in fact returned by default, the projections could be dropped entirely and the signatures simplified.
(b) body={} on the move call. The stub makes body required on files().update(); today's dispatcher sends no body at all. body={} is the minimal compliant value and Drive treats an empty PATCH body plus addParents/removeParents as a move, but it is a real wire-level change (an empty JSON document is sent). Alternatives if the reviewer objects: a localized type: ignore[call-arg], or a loosely-typed local for that one call. Both defeat the point of adopting stubs, hence the recommendation.
(c) pageSize=100. The Drive files.list default is 100; today's values (1 and 25) were the truncation mechanism, not a tuning decision. If the reviewer wants fewer round trips for large incident folders, 1000 is the Drive maximum. Not behavior-relevant now that list_next runs to exhaustion.
(d) The display cap is a shim, not a fix. The correct answer is pagination or search in the Slack UI, which is a product change and out of scope. The cap is deliberately placed in the consumer, not the vendor module, so the vendor module stays SDK-faithful and the debt is visible where it is owed. Registered with TASK-25.1.6.
(e) modules/incident/core.py:170's duplicate-document risk is FIXED by this slice as a side effect (it can now see every file in the folder). This is a behavior change in the intended direction but was not an original acceptance criterion - call it out in the PR description so the reviewer evaluates it deliberately.
(f) execute_google_api_request is reused rather than inlined, consistent with siblings .1/.2/.3/.4 and still a tolerated temporary deviation from decisions/outbound-clients.md's vendor-package export contract. Its new call sites must be reported to TASK-25.1.6 at implementation time, per that task's tracking comment. No num_retries= is added, also consistent with the siblings and also TASK-25.1.6's business.
(g) modules/reports/google_groups.py has no test file. Behavior-neutrality for its find_files_by_name and create_file call sites rests on preserved signatures and return shapes alone. Do not treat a green suite as evidence of safety there.

BLAST RADIUS AND ROLLBACK
Production files changed: 3 (integrations/google_workspace/client.py - additive factory; integrations/google_workspace/google_drive.py - migrated; modules/incident/incident_folder.py - the display cap) plus one guardrail baseline line. Zero changes to the other eight consumers. Reachable surfaces: incident creation and folder management, the roles/talent Drive templating flow, the Google Groups report, and the scheduled healthcheck. New failure modes are the sprint-wide accepted one (an unmapped Drive error propagates instead of being logged and re-raised with a different event name) plus larger result sets from three list functions, bounded at the Slack boundary by the step 8 cap. Rollback is a single revert; the split-out TASK-25.1.5.1 and TASK-25.1.7 depend on this slice, so reverting it does not strand half-migrated code.

SIZE GATE VERDICT
Fits one PR: roughly 230 changed production LOC across 3 files (one of them a genuinely mechanical, repeated 12-call-site transformation), 1 baseline line, one 457-line test file rewritten, and small additive tests in one consumer test file. The two items that would have pushed it over - the incident_draft adapter repoint with its 1704-line, 135-mock-reference test file, and the google_service.py deletion with its 482-line test file - were split into TASK-25.1.5.1 and TASK-25.1.7 respectively. No further decomposition required.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented the Drive dispatcher migration. integrations/google_workspace/client.py provides a stub-typed get_drive_service factory; integrations/google_workspace/google_drive.py now builds typed files().get/create/copy/update/list requests, executes them through execute_google_api_request (and its classify_google_error handling), passes the required empty update body for copy-then-move, and drains files().list_next() to exhaustion. Drive functions expose SDK-named fields: str | None = None and pageSize: int = 100 rather than embedding projections. modules/incident/incident_folder.py explicitly requests id, name, appProperties where its Slack metadata views need them and caps display at LEGACY_FOLDER_DISPLAY_LIMIT = 25; modules/incident/incident_roles.py explicitly requests nextPageToken, files(appProperties, id, name). This resolves plan doubt (a): default Drive response fields are irrelevant because consumers declare their projections. Pagination now prevents incident-folder scans from truncating after 25 files, avoiding the prior duplicate-document risk; vendor listing is intentionally unbounded, with the Slack-only cap tracked on TASK-25.1.6. modules/reports/google_groups.py remains without dedicated automated coverage; preserved signatures/return shapes are its compatibility evidence. Drive HttpError statuses use the existing classifier table; no Drive-specific family was needed. Validation: 80 focused Drive/incident tests passed; targeted mypy passed for integrations/google_workspace/google_drive.py and modules/incident/incident_roles.py; python3 bin/check_sdk_typing.py passed; user verified make test, make fmt, and make lint all green. Full-tree mypy remains blocked by pre-existing unrelated errors/cache failure. Human DoD remaining: review/CI and deployment verification; task intentionally remains In Progress.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: task-planner
created: 2026-09-01 15:35
---
TRACKING NOTE (2026-09-01, task-planner): TASK-25.1.1 introduces a shared integrations/google_workspace/client.py::execute_google_api_request(request) helper (try/except + classify_google_error + log + raise) as a deliberate, TEMPORARY deviation from outbound-clients.md's exact vendor-package export contract, tracked by TASK-25.1.6. When implementing this slice, if google_drive.py's migrated call sites use execute_google_api_request (or you introduce an equivalent), update TASK-25.1.6's description/references with the exact files and call sites added here, so its eventual inline-vs-formalize decision is made against the full call-site inventory, not just TASK-25.1.1's. This is the last TASK-25.1 child (25.1.6 depends on it), so its landing should trigger TASK-25.1.6's implementation.
---

created: 2026-09-02 13:30
---
PLANNED 2026-09-02 (task-planner). Three human decisions recorded in the plan's DECISION section: (1) this slice removes the vendor module's guessed SDK parameters rather than merely swapping the dispatcher for a factory - the stated purpose of adopting stubs is to stop hand-mirroring the SDK; (2) the dead pagination is FIXED, not preserved, with a temporary display cap at the two Slack call sites tracked by TASK-25.1.6; (3) the slice was decomposed because bundling everything tripped the single-PR size gate.

DECOMPOSITION: TASK-25.1.5.1 (new child, dep this task) owns repointing packages/incident_draft/adapters/google_docs.py onto get_drive_service with its own inline try/except and deleting the then-zero-caller get_file_by_id - its test file is 1704 lines with 135 mock_drive references, which alone would have dominated this PR. TASK-25.1.7 (new sibling, dep this task) owns deleting the orphaned google_service.py module; no task previously owned it, because TASK-23 shipped Done deferring it to TASK-25.1 while TASK-25.1 AC#1 still says it is "slated for TASK-23 deletion".

CONSUMER COUNT CORRECTED: nine production files, not eight. packages/incident_draft/adapters/google_docs.py calls google_drive.create_file_from_template (:272), get_file_by_id (:1245) and find_files_by_name - it post-dates this task's original scoping, the same concurrent-work drift TASK-25.1.2 found for Docs.

TWO SUBSTANTIVE FINDINGS the reviewer should check first. (1) The hardcoded fields= projections are NOT uniformly guessed parameters: on files.get/files.update they are load-bearing, because appProperties is not in the Drive v3 default response field set, so removing them would silently strip the metadata the incident-folder Slack UI reads. On the three files.list calls they are harmful, because fields="files(...)" omits nextPageToken and kills list_next. The plan treats the two groups oppositely and flags the appProperties claim as doubt (a), to be verified against Google's reference before coding. (2) Fixing pagination is a real bug fix, not cosmetics: modules/incident/core.py:170 scans only the first 25 files of an incident folder before concluding no incident document exists and creating a duplicate. But it also needs the shim - modules/incident/incident_folder.py::folder_item emits three Slack blocks per folder, so today's 25-folder cap yields 75 blocks and an uncapped listing breaks views_open past 33 folders, and list_incident_folders() feeds four Slack option lists bounded at 100 options.
---

created: 2026-09-02 14:06
---
Implementation direction updated: all Google Drive vendor functions now expose fields: str | None = None with no projection defaults. The two incident-folder metadata reads explicitly request fields="id, name, appProperties"; incident-role lookup explicitly requests fields="nextPageToken, files(appProperties, id, name)". This resolves plan doubt (a): appProperties default response behavior is irrelevant because consumers now declare their required projection.
---
<!-- COMMENTS:END -->

---
id: TASK-25.1.6
title: >-
  Retire the Google Workspace vendor mirror layer: adapters own construction and
  classification
status: Done
assignee: []
created_date: '2026-09-01 15:31'
updated_date: '2026-09-11 14:56'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.1
  - TASK-25.1.2
  - TASK-25.1.3
  - TASK-25.1.4
  - TASK-25.1.5
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/feature-packages.md
  - app/integrations/google_workspace/client.py
  - app/integrations/google_workspace/google_docs.py
  - app/integrations/google_workspace/google_directory.py
  - app/integrations/google_workspace/google_calendar.py
  - app/integrations/google_workspace/meet.py
  - app/integrations/google_workspace/sheets.py
  - app/integrations/google_workspace/google_drive.py
  - app/integrations/utils/api.py
  - app/infrastructure/directory/provider.py
  - app/infrastructure/directory/google.py
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1
priority: high
ordinal: 128000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
COORDINATOR (re-scoped and retitled 2026-09-02, human-directed, after an assessment of the shipped TASK-25.1.1/.2/.3/.4/.5 slices against decisions/outbound-clients.md and decisions/sdk-typing.md). The previous title - "Reconcile client.py's shared execute helpers against the vendor-package export contract" - described one symptom. The task is the whole retirement.

WHAT THE SLICES ACTUALLY SHIPPED. TASK-25.1.1 through .5 removed the execute_google_api_call dispatcher, which was half the job. They kept the other half: a per-method wrapper module per Google surface (google_calendar.py, meet.py, google_docs.py, sheets.py, google_drive.py, google_directory.py), whose functions are mostly 1:1 SDK passthroughs returning raw dicts. decisions/sdk-typing.md item 1 retires "the generic dispatcher AND the per-method wrapper module" and names "google_directory.py etc. wrapping each method again" as half the anti-pattern; item 2 says "no per-service client class, no facade". decisions/outbound-clients.md says integrations/<vendor>/ provides EXACTLY factories + classify_<vendor>_error, that clients contain no business logic, and that "the adapter is the boundary". The mirror layer is none of those things.

That sequencing was correct, not a mistake: 16 legacy app/modules/* consumers have no adapter tier, so inlining classification would have meant building six feature adapters inside a dispatcher-removal PR. What is wrong is that nothing marked the modules themselves as temporary, so the current shape reads as the destination. TASK-25.1's Description now carries the explicit endstate; this task owns reaching it.

FOUR LIVE DEVIATIONS TO CLOSE.
1. Classification inside the vendor package. client.py::execute_google_api_request (added by TASK-25.1.1, reused by .2/.3/.4/.5) does try/except + classify + log + raise inside integrations/. Its known call-site inventory - Calendar/Meet, 3 Docs, 5 Sheets, ~12 Drive, plus google_directory.py's _list_all - is recorded in this task's Notes. Also client.py::execute_batch_request, which returns OperationResult from a vendor package (TASK-25 AC#2 forbids it).
2. Per-method mirror modules returning raw dicts. No frozen-dataclass translation happens at any Google boundary except infrastructure/directory/google.py, so sdk-typing.md item 3 is unimplemented for five of six surfaces.
3. Business logic inside app/integrations/. google_directory.py's list_groups_with_members / get_members_details / convert_google_groups_members_to_dataframe; google_calendar.py's four pure helpers (one of which makes an HTTP call to a NON-Google holidays API from inside the Google vendor package); google_docs.py's extract_google_doc_id; google_drive.py's q-DSL builders, mimeType map, copy-then-move composition and healthcheck.
4. integrations/utils/api.py::retry_request - a time.sleep retry loop inside app/integrations/, called from google_directory.py. Trips decisions/outbound-clients.md's Checks line and TASK-25's AC#5 directly.

DIRECTORY DUPLICATION - DECIDED (2026-09-02, human). infrastructure/directory/{provider,google,factory}.py::DirectoryProvider / GoogleDirectoryProvider IS THE WAY FORWARD. It survives; integrations/google_workspace/google_directory.py is deleted; the four legacy app/modules/* consumers (permissions/handler.py, provisioning/users.py, provisioning/groups.py, reports/google_groups.py) migrate onto the DirectoryProvider Protocol. This closes the duplicated-boundary investigation recorded in this task's 2026-09-01 comment - both sides build the same Resource from the same factory, hardcode the same scopes, resolve the same customer id and run structurally identical pagination, and the provider is additionally the better of the two (get_group_members_batch does in one batched request what the legacy path does in N behind time.sleep retries). No further analysis is required; the work is migration, owned by TASK-25.1.6.3/.4/.5.

DECOMPOSED (2026-09-02) - this task is now a coordinator and contains NO implementation. Twelve children, ordered:
- TASK-25.1.6.1 - characterization tests for the untested call sites (GATE; modules/reports/google_groups.py has no test file, modules/aws/spending.py has no Sheets coverage).
- TASK-25.1.6.12 - fix the unquoted A1 sheet-name range in modules/reports/google_groups.py (BUG, found while planning .1; blocks .10 so the Sheets migration repoints correct code rather than carrying a live defect across the seam).
- TASK-25.1.6.2 - relocate the pure-domain helpers out of integrations/google_workspace (independent, can run first).
- TASK-25.1.6.3 - close the DirectoryProvider capability gaps (unbounded list-users, unbounded list-groups, silent group dropping, batched groups-with-members).
- TASK-25.1.6.4 - migrate permissions/handler.py, provisioning/users.py and reports/google_groups.py Directory calls onto DirectoryProvider.
- TASK-25.1.6.5 - migrate provisioning/groups.py onto the batched path, delete google_directory.py, retire retry_request.
- TASK-25.1.6.6 - inline Docs construction/classification in packages/incident_draft/adapters/google_docs.py (pairs with TASK-25.1.5.1's Drive half).
- TASK-25.1.6.7 - build the incident Google Docs adapter; MAKES the boundary-placement decision the next three inherit.
- TASK-25.1.6.8 - move the eight legacy Drive consumers onto the incident Drive adapter; retire LEGACY_FOLDER_DISPLAY_LIMIT.
- TASK-25.1.6.9 - move the Calendar and Meet call sites onto the adapter.
- TASK-25.1.6.10 - move the Sheets call sites onto adapters, carrying the caller-specific parse-range rule across.
- TASK-25.1.6.11 - delete execute_google_api_request, resolve execute_batch_request, add a CI guardrail against the vendor package regrowing.

This task closes when all twelve are Done. Its own remaining direct work is nil.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 All children are Done: TASK-25.1.6.1 through .14 and .16 (TASK-25.1.6.15 was archived)
- [x] #2 app/integrations/google_workspace/ contains only client.py (per-API stub-typed factories plus classify_google_error), with Google settings in infrastructure/configuration/integrations/google.py; the six per-method mirror modules and google_service.py no longer exist
- [x] #3 Every Google Workspace call site lives in a packages/<feature>/adapters/ file or an infrastructure/ capability, builds its Resource from a client.py factory, and performs its own try/except plus classify_google_error. The Directory, Drive and Spreadsheet infrastructure capabilities and packages/incident_draft return typed domain values; the packages/incident/{documents,drive,meet,scheduling} and packages/talent adapters still return dicts to their legacy modules/ callers, and typing those returns is owned by TASK-38 (incident) and TASK-39 (talent)
- [x] #4 The Directory duplication is resolved as decided: GoogleDirectoryProvider survives, integrations/google_workspace/google_directory.py is deleted, and the live legacy consumers (modules/permissions/handler.py, modules/provisioning/users.py, modules/provisioning/groups.py) use the DirectoryProvider Protocol; modules/reports/google_groups.py was deleted rather than migrated
- [x] #5 No business logic remains under app/integrations/google_workspace/, and grep -rn 'time.sleep' app/integrations returns zero hits (TASK-25 AC#5)
- [x] #6 execute_google_api_request and execute_batch_request are deleted; batch orchestration was relocated into GoogleDirectoryProvider by TASK-25.1.6.3.1, so decisions/outbound-clients.md needed no amendment
- [x] #7 A CI guardrail (bin/check_vendor_package_contract.py, run as make check-vendor-package-contract in .github/workflows/ci_code.yml) prevents app/integrations/<vendor>/ from regrowing non-factory/non-classification/non-settings modules, and its baseline has no Google Workspace entries
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
CALL-SITE INVENTORY — TASK-25.1.2 (Docs) contribution, recorded 2026-09-01 at implementation time:

app/integrations/google_workspace/google_docs.py now has 3 execute_google_api_request call sites (all added by TASK-25.1.2, none pre-existing):
- create() -> service.documents().create(body=...)
- batch_update() -> service.documents().batchUpdate(documentId=..., body=...)
- get_document() -> service.documents().get(documentId=...)

AC#1 classification for these 3: NONE live in a real packages/<feature>/adapters/ or infrastructure/ file. google_docs.py is the vendor module itself, and its downstream production consumers are:
- app/modules/incident/incident_document.py, incident_status.py, incident_conversation.py, information_update.py — legacy app/modules/* with no adapter tier and no try/except around any google_docs call (AC#3 bucket).
- app/packages/incident_draft/adapters/google_docs.py — real adapters/ file, already named in comment #2 above (AC#2 bucket); it calls google_docs.get_document/batch_update rather than execute_google_api_request directly, so reconciling it means pointing it at get_docs_service + its own inline try/except, which then removes 2 of the 3 sites' reason to exist for that path.

So after TASK-25.1.2 the helper's known call sites are: TASK-25.1.1's (Calendar/Meet) + these 3 (Docs). Siblings .3/.4/.5 still to report.

CALL-SITE INVENTORY — TASK-25.1.3 (Sheets) contribution, recorded 2026-09-01 at implementation time:

app/integrations/google_workspace/sheets.py now has 5 execute_google_api_request call sites (all added by TASK-25.1.3, none pre-existing):
- get_values() -> service.spreadsheets().values().get(spreadsheetId=..., range=..., fields=...)
- get_sheet() -> service.spreadsheets().get(spreadsheetId=..., ranges=..., includeGridData=...)
- batch_update() -> service.spreadsheets().batchUpdate(spreadsheetId=..., body=...)
- batch_update_values() -> service.spreadsheets().values().batchUpdate(spreadsheetId=..., body=...)
- append_values() -> service.spreadsheets().values().append(spreadsheetId=..., range=..., body=..., valueInputOption=..., insertDataOption=...)

AC#1 classification for these 5: NONE live in a real packages/<feature>/adapters/ or infrastructure/ file. sheets.py is the vendor module itself; its production consumers are all legacy app/modules/* with no adapter tier (AC#3 bucket):
- app/modules/incident/incident_folder.py — append_values, get_values, batch_update_values, get_sheet. NOTE: this file now owns the ONLY caller-side Google error handling in the Sheets path: TASK-25.1.3 relocated the 'Unable to parse range' non-critical swallow out of google_service.py's handle_google_api_errors decorator into get_incidents_from_sheet (try/except HttpError -> warn + return []; any other HttpError re-raised). When this file eventually gets a real adapter, that swallow is the business rule to carry across — it is caller-specific, must NOT move back into the vendor package, and is the concrete precedent for what 'inline try/except + classify_google_error at the call site' should look like here.
- app/modules/reports/google_groups.py — get_sheet (wrapped in its own blanket 'except Exception: sheet = None', which is exactly the imprecise handling an adapter + classify_google_error should replace).
- app/modules/aws/spending.py — Sheets values calls only; no get_sheet.

TEST-COVERAGE GAP flagged for whoever picks this up (discovered during TASK-25.1.3): app/modules/reports/google_groups.py and app/modules/aws/spending.py have NO automated regression coverage for their Sheets call sites — before or after TASK-25.1.3. (app/tests/modules/aws/test_spending_handler.py covers a different function, not the Sheets call site.) TASK-25.1.3's behavior-neutrality for these two files rests solely on preserved public signatures/return shapes, not on a green test suite. Any reconciliation work that changes their error-handling shape (which is the whole point of AC#3 for them) is therefore UNGUARDED and must add characterization tests FIRST, before touching either file. Do not treat 'existing tests pass' as evidence of safety for these two.

DECOMPOSITION NOTE (2026-09-01): with .1/.2/.3 reported, the known inventory is already Calendar/Meet + 3 Docs + 5 Sheets sites across 3 vendor modules and ~7 legacy app/modules/* consumer files, plus app/packages/incident_draft/adapters/google_docs.py — and .4/.5 (legacy Directory consumers, Drive) have yet to report. This task as scoped (inline everywhere + build/file adapters for every legacy consumer + delete the helper) will NOT fit a single reviewable PR. Expect to decompose it before implementation, roughly: (a) one task per real adapters/ file to inline (incident_draft/adapters/google_docs.py is already named in comment 2026-09-01 17:13); (b) one task per legacy feature area needing a new adapter (incident Docs/Drive/Calendar; incident Sheets incl. the relocated parse-range rule; reports/google_groups; aws/spending — each gated on adding characterization tests first where coverage is missing); (c) a final small task deleting execute_google_api_request from client.py once the call-site count reaches zero. Run this through the implementation-planning size gate rather than attempting it as one change.

CLOSEOUT VERIFICATION (2026-09-11). All children Done (.1-.14, .16; .15 archived). ACs reworded where they had drifted from the shipped subtasks, then checked individually:
- app/integrations/google_workspace/ holds only __init__.py and client.py (six factories plus classify_google_error).
- rg for execute_google_api_call, get_google_api_command_parameters, execute_google_api_request, execute_batch_request and retry_request in app/: zero hits for the retired Google symbols (the only retry_request hits are the unrelated access-request service method).
- rg 'time\.sleep' app/integrations: zero hits.
- Only infrastructure/{directory,drive,spreadsheets} and packages/*/adapters import integrations.google_workspace; each call site classifies with classify_google_error.
- uv run python bin/check_vendor_package_contract.py -> "OK: no net-new vendor-package contract violations (29 baselined entry(ies) remain)", no Google entries; wired in ci_code.yml as make check-vendor-package-contract.
- uv run python bin/check_sdk_typing.py -> "OK: no net-new SDK anti-patterns (11 baselined file(s) remain)".
AC#3 amended (human-decided): the incident documents/drive/meet/scheduling adapters and the talent Drive adapter still return dicts because their callers are legacy modules/ code. Typing those returns moves with the caller migrations, recorded as TASK-38 AC#9 and TASK-39 AC#4.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-01 16:54
---
Corrected 2026-09-01 (task-planner, while planning TASK-25.1.2): the original 'inline vs. formalize-as-permanent' framing implied this was a fair two-option architectural choice. It is not — decisions/outbound-clients.md already decided the target (clients raise, adapters classify, one tier). execute_google_api_request is a tolerated, temporary deviation, not a candidate to become permanent. Description and ACs rewritten accordingly (bulk --acceptance-criteria replace). The real blocker to full reconciliation is that today's Google Workspace call sites (app/modules/incident/*.py, and app/packages/incident_draft/adapters/google_docs.py which is a real adapters/ file but performs no try/except/classify of its own) mostly have no compliant adapter to inline into — that gap may need its own follow-up task(s) once the full call-site inventory is known, not a unilateral 'keep the helper' decision.
---

created: 2026-09-01 17:13
---
Concrete instance for AC#2/#3 (2026-09-01, human-confirmed while planning TASK-25.1.2): app/packages/incident_draft/adapters/google_docs.py is a real packages/<feature>/adapters/ file (post-dates the original TASK-25.1 consumer inventory) that today calls google_docs.get_document/batch_update (the legacy module-level passthrough) with ZERO try/except of its own — target shape is to call integrations.google_workspace.client.get_docs_service directly and do its own inline try/except+classify_google_error. Deliberately deferred out of TASK-25.1.2 (not an oversight): its test file is 1704 lines with 44 patch(...) sites keyed to the current google_docs mock boundary, and building real classify-based error handling here is new business logic (OperationStatus-to-None/[]-on-failure mapping for read_sections/write_draft_document), not a mechanical rewire — combining it with 25.1.2's own work would exceed a reviewable single PR. When this task is picked up, treat this adapter as a named, already-identified item in the call-site inventory, not something to re-discover.
---

author: implementation
created: 2026-09-01 18:56
---
TASK-25.1.3 (Sheets) implemented 2026-09-01: appended its 5 execute_google_api_request call sites to the inventory in Notes. Two things for whoever picks this task up: (1) modules/reports/google_groups.py and modules/aws/spending.py have ZERO test coverage of their Sheets call sites, so any error-handling change there is unguarded and needs characterization tests written first; (2) the accumulated inventory (.1/.2/.3 reported, .4/.5 outstanding) already exceeds a single reviewable PR — this task should be decomposed into per-adapter / per-legacy-feature-area subtasks plus a final helper-deletion task before any code is written.
---

created: 2026-09-01 19:42
---
CALL-SITE INVENTORY UPDATE from TASK-25.1.4 planning (2026-09-01, per the tracking note on that task): TASK-25.1.4 DOES reuse integrations/google_workspace/client.py::execute_google_api_request. Its planned new call sites are inside integrations/google_workspace/google_directory.py, all funnelled through one module-private pagination helper _list_all(resource, response_key, **list_kwargs) that calls execute_google_api_request once per page, used by list_users, list_groups and list_group_members. No new shared primitive is added to client.py by that slice, so this task's deviation surface does not grow beyond the existing helper. Two additional items for this task's reconciliation, found while planning 25.1.4 and deliberately left in place there: (a) google_directory.py's list_groups_with_members / get_members_details / convert_google_groups_members_to_dataframe are business logic inside a vendor package, which decisions/outbound-clients.md forbids - they need a home outside integrations/ (or to die with the modules-strangler); (b) integrations/utils/api.py::retry_request, called from list_groups_with_members, is a time.sleep retry loop inside app/integrations/ and directly trips outbound-clients.md's Checks line, the correct replacement being the SDK-native num_retries= argument that execute_google_api_request currently does not pass.
---

author: @me
created: 2026-09-01 21:21
---
DUPLICATED-CONCERNS EVIDENCE (2026-09-01, human-directed after TASK-25.1.4 implementation). Scope of this task widened via description item (4) + AC#4/#5. Concrete side-by-side for the named example:

SAME construction path — app/integrations/google_workspace/google_directory.py calls integrations.google_workspace.client.get_admin_directory_service() directly; app/infrastructure/directory/factory.py:55 injects that SAME function into GoogleDirectoryProvider as its get_service callable. One factory, two consumers that then diverge.

SAME hardcoded inputs — scopes: google_directory.py holds DIRECTORY_USER_READONLY_SCOPES / DIRECTORY_GROUP_READONLY_SCOPES module constants; google.py inlines the identical .../admin.directory.user.readonly and .../admin.directory.group.readonly literals per method. Customer id: google_directory.py reads get_google_workspace_settings().GOOGLE_WORKSPACE_CUSTOMER_ID at import time into a module constant; google.py receives the same value as constructor arg self._customer_id (factory.py:61).

SAME pagination mechanic — google_directory.py::_collect_pages and google.py::_paginate are now structurally identical loops (list_next until None, response.get(key, [])). They differ only in that _paginate passes num_retries=_NUM_RETRIES to .execute() and google_directory.py does not — i.e. the vendor module is the one MISSING outbound-clients.md's SDK-native retry, while still carrying the forbidden time.sleep loop (integrations/utils/api.py::retry_request) in list_groups_with_members.

SAME API calls, different return contract — users.list / groups.list / members.list are called from both files. google_directory.list_users/list_groups/list_group_members raise and return raw list[dict]; provider.list_users/list_groups/get_group_members classify via classify_google_error into OperationResult and translate into DirectoryUser/DirectoryGroup/DirectoryMember dataclasses. The provider is the shape decisions/sdk-typing.md item 3 asks for.

WORSE-DUPLICATE case — google_directory.list_groups_with_members loops groups and calls list_group_members once per group behind retry_request (time.sleep). infrastructure/directory/google.py::get_group_members_batch already does the same job in ONE batched Directory request via client.execute_batch_request. The legacy path is not just duplicated, it is the inferior of the two.

CONSUMER SPLIT (the reason both still exist) — google_directory.py: modules/permissions/handler.py, modules/provisioning/users.py, modules/provisioning/groups.py (via list_groups_with_members), modules/reports/google_groups.py. GoogleDirectoryProvider: packages/access/catalog/service.py, packages/access/sync/desired_state.py, modules/dev/google.py. Purely legacy-vs-target; no capability justifies keeping two.

LIKELY RESOLUTION (to be confirmed by whoever plans this, not decided here): GoogleDirectoryProvider survives; the four legacy consumers move onto the DirectoryProvider Protocol; google_directory.py's three list functions are deleted; list_groups_with_members/get_members_details either die or are rebuilt on get_group_members_batch outside integrations/ (they are business logic in a vendor package, already flagged in the 2026-09-01 19:42 comment). That also retires this surface's dependency on execute_google_api_request, which is AC#2/#3's job — the two threads converge. Sizing: this is multi-PR work (4 consumer modules, 2 of which have thin or no coverage — modules/reports/google_groups.py has NO test file at all per TASK-25.1.4 notes), so run it through the implementation-planning size gate and decompose before writing code.

NOT DONE HERE and explicitly out of scope of TASK-25.1.4.
---

created: 2026-09-02 13:30
---
INVENTORY + SHIM REGISTRATION from TASK-25.1.5 planning (2026-09-02, task-planner). Two items land in this task's scope.

1. execute_google_api_request call sites. TASK-25.1.5 as planned adds about 12 more in integrations/google_workspace/google_drive.py (add_metadata, delete_metadata, list_metadata, get_file_by_id, create_folder, create_file, create_file_from_template, copy_file_to_folder x2, and one per page inside the shared _collect_files pagination helper used by find_files_by_name / list_folders_in_folder / list_files_in_folder). AC#1 classification: NONE live in a real packages/<feature>/adapters/ or infrastructure/ file. Eight of the nine downstream consumers are legacy app/modules/* or app/jobs/* with no adapter tier (AC#3 bucket): modules/incident/{incident_document,incident_helper,incident_folder,core,incident_roles}.py, modules/role/role.py, modules/reports/google_groups.py, jobs/scheduled_tasks.py. The ninth, packages/incident_draft/adapters/google_docs.py, is a real adapters/ file and belongs to the AC#2 bucket - but it is now owned by the new TASK-25.1.5.1, which repoints its two Drive call sites onto get_drive_service with an inline try/except and deletes google_drive.get_file_by_id. When TASK-25.1.5.1 lands, remove those two sites from this task's outstanding scope; its remaining google_drive.find_files_by_name call and all its google_docs calls stay here.

2. NEW TEMPORARY SHIM to retire. TASK-25.1.5 fixes the Drive list pagination that fields="files(...)" had silently disabled, which makes modules/incident/incident_folder.py's folder listings unbounded. Slack cannot take that: folder_item emits three blocks per folder against a 100-block modal limit, and list_incident_folders() feeds four static_select option lists against a 100-option limit. The slice therefore adds a named constant (LEGACY_FOLDER_DISPLAY_LIMIT) applied in list_incident_folders() and list_folders_view(). It is a display shim, not a fix - the real answer is pagination or search in the Slack UI, a product change. Fold its retirement into whichever follow-up builds a real adapter for modules/incident's Drive usage.
---

created: 2026-09-02 14:06
---
TASK-25.1.5 adds integrations/google_workspace/google_drive.py call sites to the temporary execute_google_api_request helper: add_metadata, delete_metadata, list_metadata, create_folder, create_file_from_template, create_file, get_file_by_id, find_files_by_name, list_folders_in_folder, list_files_in_folder, and both copy_file_to_folder requests. It also adds the temporary LEGACY_FOLDER_DISPLAY_LIMIT Slack display shim in modules/incident/incident_folder.py.
---

created: 2026-09-02 14:30
---
TASK-25.1.5 now uses integrations/google_workspace/client.py::execute_google_api_request at every migrated google_drive.py request boundary (single calls, pagination collector, and copy/move composition). It also adds modules/incident/incident_folder.py::LEGACY_FOLDER_DISPLAY_LIMIT = 25 as the temporary Slack block/option-limit shim while Drive folder pagination is unbounded.
---

created: 2026-09-02 15:05
---
RE-SCOPED AND RETITLED 2026-09-02 (human-directed). Title changed from "Reconcile integrations/google_workspace/client.py's shared execute helpers against the vendor-package export contract" to "Retire the Google Workspace vendor mirror layer". Priority medium -> high. The five previous acceptance criteria were REPLACED (not quietly reworded) with seven coordinator-level ones; the old AC#1/#2/#3 (execute_google_api_request call-site inventory and inlining) are now owned by the children, and the old AC#4/#5 (duplicated-concern inventory and the google_directory decision) are DISCHARGED - the inventory is in this task's Notes and the 2026-09-01 21:21 comment, and the decision is made below. Recording the replacement explicitly per the backlog-task-workflow rule against silently reshaping ACs.
---

created: 2026-09-02 15:05
---
DIRECTORY DECISION - MADE 2026-09-02 (human). AC#5 of the previous AC set asked for "a written decision (which survives, how the four legacy app/modules/* consumers move, what happens to list_groups_with_members/get_members_details and their time.sleep retry_request loop)". Here it is.

SURVIVES: infrastructure/directory/{provider,google,factory}.py - the DirectoryProvider Protocol and GoogleDirectoryProvider. app/integrations/google_workspace/google_directory.py is DELETED.

RATIONALE: the 2026-09-01 21:21 evidence comment established that the two sides are not a real separation - same factory (client.get_admin_directory_service), same hardcoded readonly scopes, same GOOGLE_WORKSPACE_CUSTOMER_ID, structurally identical pagination, same three calls (users.list/groups.list/members.list). The split is purely legacy-vs-target. The provider is additionally the better of the two: it classifies into OperationResult and translates into DirectoryUser/DirectoryGroup/DirectoryMember dataclasses (which is what decisions/sdk-typing.md item 3 asks for), it passes SDK-native num_retries in _paginate, and get_group_members_batch does in ONE batched request what google_directory.list_groups_with_members does in N behind a time.sleep loop. Keeping the vendor module would mean keeping the inferior implementation and the forbidden retry loop.

HOW THE FOUR CONSUMERS MOVE: via infrastructure/directory/factory.py::get_directory_provider(), per decisions/dependency-injection.md - never by constructing GoogleDirectoryProvider directly. modules/permissions/handler.py (2x list_group_members), modules/provisioning/users.py (list_users) and modules/reports/google_groups.py (list_groups + list_group_members) are TASK-25.1.6.4. modules/provisioning/groups.py (list_groups_with_members) is TASK-25.1.6.5, and moves onto the batched capability rather than a like-for-like port.

WHAT HAPPENS TO THE BUSINESS LOGIC: list_groups_with_members is rebuilt on get_group_members_batch OUTSIDE app/integrations/ (TASK-25.1.6.3 builds the capability). get_members_details and convert_google_groups_members_to_dataframe die with the module unless a consumer still needs them, decided per function in TASK-25.1.6.5. integrations/utils/api.py::retry_request is deleted - google_directory.py is its only production caller (the identically-named symbols in packages/access/request/{http,service}.py are unrelated domain methods). That satisfies TASK-25's AC#5 for the Google vendor.

BLOCKER FOUND WHILE WRITING THIS, now TASK-25.1.6.3: the Protocol cannot express two of the four call sites as-is. DirectoryProvider.list_users(query="", limit=100) truncates twice (maxResults=limit, then data[:limit]) where legacy list_users() paginates the whole domain - repointing provisioning/users.py blind would silently sync only 100 users. DirectoryProvider.list_groups(query) is required-argument and rewrites bare strings to email:{query}*, where reports/google_groups.py calls list_groups() expecting everything. Capability parity lands before any consumer moves.
---

created: 2026-09-02 15:05
---
ARGUMENT FOR DELETING execute_google_api_request THAT WAS NOT YET RECORDED (2026-09-02): it defeats the stated benefit of the stub adoption that TASK-70 paid for.

Its signature is execute_google_api_request(request: Any) -> Any. Every migrated call site hands it a stub-typed request object and gets back Any. google_drive.py compounds this with two module-private helpers of the same shape - _execute_file_request(request: Any) -> dict[str, Any] and _collect_files(files_resource: Any, request: Any). So the precisely-typed return of files().list() / documents().get() / spreadsheets().values().get() is laundered to Any (or a hand-written dict[str, Any]) at the exact seam where decisions/sdk-typing.md wanted the types to reach the caller. Item 3 of that record says the adapter "calls service.users().get(userKey=...).execute() directly with real method/parameter/return-shape completion and checking" - "directly" is doing real work in that sentence, and routing through an Any -> Any helper is not it.

This is a stronger argument than the export-contract one alone: the helper is not merely an extra symbol in the vendor package, it actively cancels the type resolution the stub packages were adopted to provide. Inlining try/except + classify_google_error at each adapter call site restores the SDK's own return type at the call site, which is the point. Recorded here so TASK-25.1.6.11 does not have to rediscover it.
---

created: 2026-09-02 16:38
---
CALL-SITE INVENTORY UPDATE (TASK-25.1.5.1, 2026-09-02): the two Drive call sites in packages/incident_draft/adapters/google_docs.py are DISCHARGED from this task's outstanding AC#2 scope.

- _copy_source_document now builds integrations.google_workspace.client.get_drive_service(scopes=google_drive.DRIVE_SCOPES) and calls service.files().copy(...).execute() inside its own try/except HttpError -> classify_google_error -> logs incident_draft_copy_failed and returns None.
- _source_name_and_folder does the same with service.files().get(fileId=..., fields="id, name, parents", supportsAllDrives=True).execute(), logging incident_draft_metadata_lookup_failed and falling back to get_google_resources_config().incident_folder_id.

Neither site uses execute_google_api_request or a google_drive passthrough any more; the adapter imports google_drive solely for its DRIVE_SCOPES constant. integrations/google_workspace/google_drive.py::get_file_by_id was deleted (zero callers repo-wide). create_file_from_template stays for its legacy modules/incident/incident_document.py caller and remains in this task's scope.

Reusable test helper left behind for TASK-25.1.6.6's Docs half, in app/tests/unit/packages/incident_draft/test_incident_draft_adapter.py:
  _drive_resource_fake(*, copy_response=None, copy_error=None, get_response=None, get_error=None) -> MagicMock
plus an autouse `drive_service` fixture patching packages.incident_draft.adapters.google_docs.google_workspace_client and a _copy_request(drive_service) accessor. Reuse these rather than reinventing the Resource mock chain.
---

author: @task-planner
created: 2026-09-02 18:54
---
TWELFTH CHILD ADDED 2026-09-02 (task-planner, human-approved). TASK-25.1.6.12 - "Fix the unquoted A1 sheet-name range in the Google Groups members report" - was found while planning TASK-25.1.6.1 and is a genuine production bug, not refactor work.

WHY IT IS A CHILD OF THIS COORDINATOR RATHER THAN A LOOSE TASK. It was surfaced by this decomposition, it sits in a file three other children touch (modules/reports/google_groups.py: Directory sites in .4, Drive sites in .8, Sheets sites in .10), and TASK-25.1.6.10 now depends on it. Making it a child adds no extra blocking, since .10 was already a child and already gates on it.

WHY IT IS NOT FOLDED INTO .10, WHICH OWNS THAT CALL SITE. The implementation-planning size gate separates mechanical migration diffs (reviewed for completeness) from behaviour diffs (reviewed for correctness). Folding a user-facing bug fix into a seam migration makes both harder to review, and would leave a live defect in place until a Medium-priority downstream slice ships.

DEPENDENCY WIRING APPLIED: .12 depends on .1 (the characterization gate pins todays unquoted output as a defect probe that .12 then flips); .10 now depends on TASK-25.1.6.7 AND TASK-25.1.6.12. Ordinal 132500 places it immediately after the gate task. AC#1 and the Description child list were updated from eleven to twelve; the other six acceptance criteria are unchanged, re-emitted only because the CLI replaces the set as a whole.

SCOPE FENCE BETWEEN .12 AND .10, recorded on both: .12 quotes the sheet name in the batch_update_values range and the get_sheet ranges through one shared helper and makes 50-char truncation collision-safe. It does NOT touch the two blanket excepts (.10 AC#3 owns those), does NOT add skip-instead-of-abort resilience around batch_update_values (left to .10, which is rewriting that error handling anyway), and migrates nothing.
---

created: 2026-09-03 14:21
---
GAP FLAGGED WHILE PLANNING TASK-25.1.6.2 (2026-09-03, task-planner). That slice's plan relocates get_federal_holidays (the non-Google canada-holidays.ca HTTP call) out of app/integrations/google_workspace/ into app/modules/incident/utils.py, which satisfies TASK-25.1.6.2's own AC#3 literally ("no longer made from inside app/integrations/google_workspace/"). It does NOT make that HTTP call decisions/outbound-clients.md-compliant: that record wants any outbound boundary call behind a dedicated app/integrations/<vendor>/ client + classify_<vendor>_error, which a plain function in a legacy modules/incident/ file is not. None of this coordinator's twelve children currently own building that (a canada_holidays vendor tier). Not fixed by TASK-25.1.6.2 itself — building a vendor tier there would exceed a pure-function-relocation slice's scope and mix mechanical move with new-pattern establishment. Left as accepted, tracked debt; flagging here so it isn't lost. If desired, a follow-up task (sibling to these twelve, or its own ticket) should be created to give canada-holidays.ca a proper vendor client.
---

created: 2026-09-03 15:10
---
LOCATION UPDATE for the 2026-09-03 gap comment above (task-planner). TASK-25.1.6.2's destination changed during planning from app/modules/incident/utils.py to a new app/packages/incident_scheduling/ package (no hookimpls/entry-point yet), authorized by a new coexistence rule 5 added to decisions/migration.md to permit relocating host-surface-free pure logic out of a frozen module ahead of its full migration. get_federal_holidays now lives at app/packages/incident_scheduling/availability.py. The outbound-clients.md compliance gap flagged in the prior comment is unchanged in substance (still no dedicated canada_holidays vendor client + classify function) - only the location reference moves.
---

author: @task-planner
created: 2026-09-03 18:03
---
TASK-25.1.6.3 SPLIT INTO TWO (2026-09-03, task-planner, human-approved during planning). Your AC#1 counts twelve children; that count is unchanged - the new task is a GRANDCHILD under TASK-25.1.6.3, not a thirteenth child. TASK-25.1.6.3 is not Done until it is Done.

- TASK-25.1.6.3 (Slice A, retitled 'Make DirectoryProvider list-all generic and unbounded, and close the mapping gaps blocking the legacy consumers') - list-all semantics, generic/managed group-mapping split, observable drops, DirectoryUser.given_name/family_name, field inventory. Unblocks TASK-25.1.6.4 on its own.
- TASK-25.1.6.3.1 (Slice B, NEW) - batch orchestration moved into GoogleDirectoryProvider, batch pagination, groups-with-members composition. TASK-25.1.6.5 now depends on it as well as on .4.

Rationale: gate trigger #3 - the combined scope mixed a mechanical mapping/pagination change with a behavioural rearchitecture of the Google batch surface. Combined estimate was ~295 production LOC over 3 files, under the 400 LOC threshold, so this is a deliberate reviewability split rather than a hard-gate requirement.

THREE FINDINGS FROM THAT PLANNING THAT AFFECT THIS COORDINATOR.

1. YOUR AC#6 GETS EASIER. execute_batch_request has exactly ONE consumer repo-wide (infrastructure/directory/google.py:17 and :525). TASK-25.1.6.3.1 relocates that orchestration into the provider, so by the time TASK-25.1.6.11 runs, AC#6's 'relocated to the provider' branch is already satisfied and no amendment to decisions/outbound-clients.md is needed. Comment left on .11.

2. TWO DEFECTS FOUND IN THE SURVIVING PROVIDER, i.e. in the side this coordinator decided keeps living. (a) list_users' limit is a post-hoc slice applied after walking EVERY page (google.py:402 then :418), so list_users(limit=3) pulls the whole directory today; fixed by Slice A. (b) get_group_members_batch ignores nextPageToken and silently truncates any group past the first page; fixed by Slice B. Both predate this work and neither is caused by the mirror retirement - worth knowing that 'the provider is the better of the two' (your 2026-09-02 Directory decision) was true but not defect-free.

3. TWO FOLLOW-UPS CREATED OUTSIDE THIS COORDINATOR'S TREE, both deliberately NOT children of TASK-25.1.6 because neither is Google vendor-mirror work: TASK-76 (relocate managed-group prefix/domain policy out of infrastructure/directory into packages/access - the layering correction behind Slice A's mapper split, gated on TASK-25.1.6.3) and TASK-77 (safety review of packages/access/sync/desired_state.py:163 swallowing an IDP batch failure and returning an empty desired state).
---

created: 2026-09-08 14:37
---
RISK-CONTROLLED EXECUTION ORDER (2026-09-08): completed prerequisites are .6.1 characterization gate, .6.2 helper relocation, .6.3/.3.1 Directory capability work, .6.4/.6.5 Directory consumer migration and google_directory deletion, .6.12 A1 report bug fix, plus parent .1.1-.5 and .1.5.1 surface migrations. Remaining order is strictly: (1) .6.6 inline incident_draft Docs construction/classification; (2) .6.7 build the incident Docs adapter and migrate legacy incident Docs callers; (3) .6.8 migrate legacy Drive callers; (4) .6.9 migrate Calendar/Meet callers; (5) .6.10 migrate Sheets callers; (6) .7 delete orphaned google_service.py; (7) .6.11 delete execute_google_api_request, resolve execute_batch_request, verify the exact vendor export contract, and install the CI guardrail. Keep one slice per PR and run focused tests plus ruff/mypy/check_sdk_typing after each; run the full non-smoke suite before .6.11. The sequence is intentionally serialized because .6.7-.10 touch shared legacy modules and .6.11 is only meaningful after all deletions are complete.
---

created: 2026-09-08 14:44
---
SCOPE UPDATE (2026-09-08): the legacy modules/reports/google_groups.py feature is unused and will be deleted, not migrated. TASK-25.1.6.10 now owns that simple deletion alongside the live incident-folder and AWS-spending Sheets migration; no replacement reporting feature is part of TASK-25.1.
---

created: 2026-09-08 16:01
---
TASK-25.1.6.6 discharged the 3 Docs call sites in app/packages/incident_draft/adapters/google_docs.py: read_sections documents().get, write_draft_document post-copy documents().get, and write_draft_document documents().batchUpdate. Remaining integrations/google_workspace/google_docs.py production consumers are app/modules/incident/incident_document.py (get_document x2, batch_update x3), owned by the legacy incident Docs adapter task. google_docs.py::create remains pre-existing dead code with only its vendor test as a caller.
---

created: 2026-09-08 18:55
---
DRIVE ARCHITECTURE PIVOT (2026-09-08, task-planner, human-directed while planning TASK-25.1.6.8). google_drive.py has two real, unrelated feature consumers today: the incident feature (core.py, incident_document.py, incident_folder.py, incident_roles.py, jobs/scheduled_tasks.py's healthcheck) and the talent/hiring `role` workflow (modules/role/role.py: create_folder + copy_file_to_folder x7). No packages/role package exists. Building "the incident Drive adapter" as TASK-25.1.6.8 was originally titled would have made an unrelated feature import packages/incident's adapter, or forced a second flat Path-B adapter duplicating the same Drive semantics.

DECISION: Drive graduates directly to a Path A infrastructure capability instead of a Path B feature adapter, since two independent feature consumers are already known upfront (the layers.md "promotion on second consumer" trigger, applied proactively rather than after building and later promoting a first adapter). New app/infrastructure/drive/ (DriveProvider Protocol + GoogleDriveProvider + settings + factory), mirroring the existing infrastructure/directory/{provider,google,factory,models,settings}.py shape exactly. Two thin feature adapters then consume DriveProvider: packages/incident/<subdomain>/adapters/google_drive.py and a new packages/role/adapters/google_drive.py.

TASK-25.1.6.8 RETITLED to a coordinator with three children: .8.1 (build DriveProvider), .8.2 (incident feature adapter + migrate incident/jobs consumers), .8.3 (role feature adapter + migrate modules/role/role.py). TASK-25.1.6.9's dependency is repointed from TASK-25.1.6.8 to TASK-25.1.6.8.2,TASK-25.1.6.8.3 (both Drive migrations must land before Calendar/Meet per the coordinator's serialized execution order). TASK-25.1.6.10 gains ownership of actually deleting app/integrations/google_workspace/google_drive.py + its test file, since modules/reports/google_groups.py (deleted only by .10) keeps calling google_drive.find_files_by_name/create_file until then — neither .8.2 nor .8.3 can reach a zero-production-reference state on their own.
---

author: @task-planner
created: 2026-09-09 15:06
---
CHILD .10 DECOMPOSED 2026-09-09 (task-planner, human-approved). Your child count goes from twelve to sixteen: TASK-25.1.6.10 becomes a coordinator with five children (.10.1 through .10.5) and no direct implementation, mirroring what TASK-25.1.6.8 did for Drive.

ARCHITECTURE PIVOT, SAME AS .8's: Sheets graduates to a Path A infrastructure capability (app/infrastructure/spreadsheets/, SpreadsheetProvider) rather than a feature-owned adapter, because two independent live consumers already exist (modules/incident/incident_folder.py and modules/aws/spending.py). Unlike Drive, neither consumer needs a feature adapter at all - the contract is fully vendor-neutral, so both legacy modules call get_spreadsheet_provider() directly, following the Directory precedent from .4/.5.

WHAT THIS MOVES THE COORDINATOR'S OWN ACs TOWARD:
- AC#2 (integrations/google_workspace/ contains only client.py and settings): .10.4 deletes sheets.py, .10.5 deletes google_drive.py. After the .10 series, the surviving mirror modules are google_docs.py, google_calendar.py and meet.py.
- AC#3 (every Google call site lives in an adapter or infrastructure capability with its own classify): .10.2 adds the fourth infrastructure capability; .10.5 converts the last legacy Drive pass-throughs into real Path B adapter code.
- AC#5 (no time.sleep under app/integrations, no business logic there): .10.1 deletes the last time.sleep pacer in this series along with the report module's business logic.
- AC#6 (execute_google_api_request deleted): the .10 series removes roughly 17 of its call sites. Impact recorded on TASK-25.1.6.11.

ONE DEVIATION SURFACED FOR THE RECORD: classify_google_error maps only {404}, {401,403} and {429,5xx} and re-raises everything else, so an expected Sheets HTTP 400 ('Unable to parse range') would escape a Path A boundary. Handled locally in the Sheets Google implementation without modifying the shared classifier; flagged to .11 in case the guardrail work wants to generalize it.
---

created: 2026-09-10 15:45
---
ARCHITECTURE CONSTRAINT ADDED 2026-09-10 (human-directed). Do not introduce new infrastructure services for workplace concerns: calendar, documents, files, directory, mail, notifications, people or identity. That means no new app/infrastructure/<service>/ package, Protocol or factory.

Why: the organization will run Google Workspace with Slack and Microsoft 365 with Teams side by side for the long term. Three Draft decision records describe the direction:
- decisions/workplace-systems.md
- decisions/capability-packages.md
- decisions/people-and-accounts.md

Until those are accepted:
- keep vendor behavior in feature Path B adapters (app/packages/<feature>/adapters/);
- the existing infrastructure/directory, drive and spreadsheets providers stay usable, including changes needed to finish migrating their current consumers;
- do not create capability packages yet.

This applies to every open child of this coordinator. Finishing SDK isolation is unaffected.
---
<!-- COMMENTS:END -->

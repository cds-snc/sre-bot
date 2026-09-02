---
id: TASK-25.1.6
title: >-
  Reconcile integrations/google_workspace/client.py's shared execute helpers
  against the vendor-package export contract
status: To Do
assignee: []
created_date: '2026-09-01 15:31'
updated_date: '2026-09-02 14:30'
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
  - app/integrations/google_workspace/client.py
  - app/integrations/google_workspace/google_docs.py
  - app/integrations/google_workspace/google_directory.py
  - app/infrastructure/directory/google.py
  - app/packages/incident_draft/adapters/google_docs.py
parent_task_id: TASK-25.1
priority: medium
ordinal: 128000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
decisions/outbound-clients.md's Checks require each vendor package to export exactly: factories, classify_<vendor>_error, settings — "the adapter is the boundary", not the vendor client. TASK-22.4 already added one narrow deviation (execute_batch_request, needed only for the Directory batch API's per-item error-reporting shape). TASK-25.1.1 added a second, more general one: execute_google_api_request(request), a shared try/except+classify_google_error+log+raise helper in integrations/google_workspace/client.py, reused by TASK-25.1.1/.2/.3/.5's call sites.

CORRECTION (2026-09-01): this task's original framing — "decide between (a) inline per-adapter or (b) keep execute_google_api_request as a permanent, formalized shared primitive" — was inaccurate and is replaced. decisions/outbound-clients.md already decided the target shape (one adaptation tier: clients raise, adapters classify). execute_google_api_request performing classification inside the vendor package is a real, currently-necessary deviation from that decision, not a genuinely open two-way choice. It is tolerated only because today's actual Google Workspace call sites have no compliant adapter tier to inline the try/except into: TASK-25.1.1/.2's consumers are legacy app/modules/incident/*.py files with zero error handling of their own, plus app/packages/incident_draft/adapters/google_docs.py — a real packages/<feature>/adapters/ file (per decisions/feature-packages.md) that itself performs no try/except/classify today either.

Reconciliation must correct this deviation, not ratify it as permanent. Once all of TASK-25.1's children (Calendar/Meet, Docs, Sheets, legacy Directory consumers, Drive) are Done and the full execute_google_api_request call-site inventory is known, this task's job is to: (1) inline try/except + classify_google_error directly at every call site that already lives in a real packages/<feature>/adapters/ or infrastructure/ file, deleting that call site's dependency on execute_google_api_request; (2) for every remaining call site that is legacy app/modules/* code with no adapter tier, file (or point at) the follow-up work that migrates it onto a real per-feature adapter — this may itself need its own decomposition, since building a first adapter for app/modules/incident's Google Docs/Drive/Calendar usage is new architecture, not a mechanical inline; (3) delete execute_google_api_request from client.py entirely once no call site depends on it. Keeping it as a permanent vendor-package export is not an acceptable resolution of this task.

SCOPE ADDITION (2026-09-01, human-directed): (4) investigate and resolve DUPLICATED CONCERNS between the vendor modules and their infrastructure/ or packages/ counterparts on the same API surface — the shared-helper question above is only one symptom of a broader "two implementations of the same boundary" problem. The named, confirmed example is app/integrations/google_workspace/google_directory.py versus app/infrastructure/directory/google.py::GoogleDirectoryProvider: both build the SAME Admin Directory Resource from the SAME factory (integrations.google_workspace.client.get_admin_directory_service), both hardcode the same OAuth readonly scope strings, both resolve the same GOOGLE_WORKSPACE_CUSTOMER_ID, both implement a near-identical list/list_next pagination loop, and both cover the same three calls (users.list, groups.list, members.list) — differing only in that the provider classifies into OperationResult + typed dataclasses while the vendor module raises + returns raw dicts. The split is legacy-vs-target, not a real separation: google_directory.py exists only for its four legacy app/modules/* consumers (permissions/handler.py, provisioning/users.py, provisioning/groups.py, reports/google_groups.py) while GoogleDirectoryProvider already serves app/packages/access. Under decisions/outbound-clients.md ("one adaptation tier") and decisions/sdk-typing.md (one construction path per vendor) exactly one of these should survive. This is an INVESTIGATE-AND-DECOMPOSE item, not something to implement inside this task; it is deliberately out of scope for TASK-25.1.4, which migrated google_directory.py in place and explicitly rejected the DirectoryProvider route to keep that slice behaviour-neutral. NOTE: the task title now under-describes this scope.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The full execute_google_api_request call-site inventory across TASK-25.1.1/.2/.3/.4/.5 is enumerated, naming which call sites already live in a real packages/<feature>/adapters/ or infrastructure/ file vs. which are legacy app/modules/* code with no adapter tier
- [ ] #2 Every call site already in a real packages/<feature>/adapters/ or infrastructure/ file has its own inline try/except + classify_google_error + raise, and no longer depends on execute_google_api_request
- [ ] #3 Every remaining legacy app/modules/* call site either has its own real per-feature adapter built and inlined, or a follow-up task migrating it there is filed/linked here; execute_google_api_request is deleted from client.py once zero call sites depend on it
- [ ] #4 Duplicated-concern inventory produced for the Google Workspace surface: for each vendor module in app/integrations/google_workspace/, its infrastructure/ or packages/ counterpart (if any) is named, the overlapping API calls and duplicated mechanics (service construction, scopes, customer id, pagination, retry, error handling) are listed, and a single survivor is chosen per surface with the losing side's consumers enumerated
- [ ] #5 The google_directory.py vs infrastructure/directory/google.py::GoogleDirectoryProvider duplication specifically has a written decision (which survives, how the four legacy app/modules/* consumers move, what happens to list_groups_with_members/get_members_details and their time.sleep retry_request loop) and follow-up subtasks filed for the migration; no implementation is done inside this task
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
<!-- COMMENTS:END -->

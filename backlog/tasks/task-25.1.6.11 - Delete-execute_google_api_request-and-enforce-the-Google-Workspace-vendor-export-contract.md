---
id: TASK-25.1.6.11
title: >-
  Delete execute_google_api_request and enforce the Google Workspace vendor
  export contract
status: To Do
assignee: []
created_date: '2026-09-02 15:04'
updated_date: '2026-09-10 17:50'
labels:
  - clients
  - phase-3
  - cleanup
milestone: m-3
dependencies:
  - TASK-25.1.6.5
  - TASK-25.1.6.7
  - TASK-25.1.6.8
  - TASK-25.1.6.9
  - TASK-25.1.6.10
  - TASK-25.1.7
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/integrations/google_workspace/client.py
parent_task_id: TASK-25.1.6
priority: medium
ordinal: 142000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Closing slice of TASK-25.1.6. Small by design: every consumer has already moved, so this is deletion plus a guardrail.

BY THIS POINT the six vendor mirror modules are gone (google_directory.py via TASK-25.1.6.5; google_docs.py via .7; google_drive.py via .8; google_calendar.py and meet.py via .9; sheets.py via .10) and every Google call site lives in an adapter that does its own try/except + classify_google_error. The temporary shared helper therefore has zero callers.

SCOPE:
1. Delete integrations/google_workspace/client.py::execute_google_api_request and its tests. It was introduced by TASK-25.1.1 as an explicitly temporary, in-code-documented deviation from decisions/outbound-clients.md's export contract, because no compliant adapter existed to inline it into. That reason is gone.
2. Decide execute_batch_request's fate. TASK-22.4 added it as a narrower deviation, needed for the Admin SDK batch protocol's per-item error-reporting shape, and it returns OperationResult from inside the vendor package - which decisions/outbound-clients.md forbids ("no client returns OperationResult", TASK-25 AC#2). Its only consumer is GoogleDirectoryProvider. Either move the batch orchestration into that provider (leaving the vendor package with factories + classify only) or record why the batch protocol genuinely cannot be expressed at the adapter, as an explicit amendment to decisions/outbound-clients.md rather than a silent exception.
3. Verify and lock in the export contract: app/integrations/google_workspace/ contains client.py (factories + classify_google_error) and settings, and nothing else.
4. Add the guardrail so this cannot regress: extend app/bin/check_sdk_typing.py (or the equivalent CI check) to fail when app/integrations/<vendor>/ gains a module that is neither a factory/classification/settings module, or when a file under app/integrations/ imports OperationResult outside the classification return type. A convention this expensive to re-establish should be machine-enforced, not remembered.

THEN: TASK-25.1's AC#1 and TASK-25's AC#1/#2 become provable for the Google vendor, and TASK-25.1.6 can close.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 TASK-25.1.6.11.1, TASK-25.1.6.11.2 and TASK-25.1.6.11.3 are Done
- [ ] #2 integrations/google_workspace/client.py::execute_google_api_request and execute_batch_request are deleted with their tests, and grep confirms zero references repo-wide outside backlog/ and tmp/. execute_batch_request's orchestration was already relocated into GoogleDirectoryProvider by TASK-25.1.6.3.1, so no amendment to decisions/outbound-clients.md is needed
- [ ] #3 app/integrations/google_workspace/ contains only __init__.py and client.py (settings.py permitted once TASK-24 creates it). The six per-method mirror modules, google_meet.py and google_service.py are gone, and schemas.py lives under app/tests/factories/
- [ ] #4 No file under app/integrations/google_workspace/ references OperationResult, and every remaining reference elsewhere under app/integrations/ is frozen in the vendor-package guardrail baseline (TASK-25 AC#2 provable for the Google vendor)
- [ ] #5 A CI guardrail fails the build when app/integrations/<vendor>/ gains a non-factory/non-classification/non-settings module or a new OperationResult reference, proven by a deliberately failing fixture in the check's own tests
- [ ] #6 app/bin/baselines/sdk_typing_antipatterns.txt and the vendor-package guardrail baseline both have zero google_workspace entries, and both checks pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR (decomposed 2026-09-10, human-approved). No direct implementation. As one PR this task was about 11 production files and mixed a dead-code deletion/relocation with a new CI enforcement rule, tripping size-gate rules #1 and #3. A third slice was added the same day, when the human ruled integrations/utils/ is not a vendor package.

SLICES AND ORDER
1. TASK-25.1.6.11.1 - delete google_calendar.py, meet.py and google_meet.py (all orphaned), execute_google_api_request and execute_batch_request (zero consumers), and the stale docstring references; relocate the test-only schemas.py to tests/factories. No blockers.
2. TASK-25.1.7 - delete google_service.py (existing task, unchanged).
3. TASK-25.1.6.11.2 and TASK-25.1.6.11.3 can run in parallel once 1 and 2 land:
   - .11.2: new bin/check_vendor_package_contract.py covering all vendors, with a rule-qualified ratchet-down baseline, Makefile target and CI step. utils/ is a declared non-vendor directory that only warns.
   - .11.3: retire integrations/utils/api.py. Delete the six case converters (no production callers once 1 and 2 land) and the scheduling adapter's unused body_kwargs parameter; move generate_unique_id verbatim into its only consumer, packages/incident/scheduling/adapters/google_calendar.py.

SURFACE FINDINGS THAT CHANGED THE SCOPE (verified on main 2026-09-10)
- TASK-25.1.6.9 checked the deletion of google_calendar.py and meet.py, but both are still on disk with zero importers and are the last callers of execute_google_api_request. Not reopened; folded into slice 1 and recorded on TASK-25.1.6.9.
- google_meet.py (dead URL builder) and schemas.py (Pydantic models used only by test factories) were owned by no task. Both are folded into slice 1.
- No settings.py exists in the vendor package. Google settings stay in infrastructure/configuration/integrations/google.py until TASK-24, so AC#3 permits settings.py rather than requiring it.
- Checked across all vendors, the contract fails today: aws, slack and openai have extra modules; aws/shield, maxmind, openai and slack reference OperationResult. The guardrail freezes those in a baseline instead of fixing them. AC#4 was reworded from "no file under app/integrations/" to that frozen-baseline form.
- integrations/utils/api.py was owned by no task (TASK-25.1.6.5 removed only retry_request). None of its seven functions justifies both its form and its location, hence slice .11.3.

DECISIONS CLOSING EARLIER NOTES ON THIS TASK (human, 2026-09-10)
- orderBy="email" parity (comment of 2026-09-03, TASK-25.1.6.4 planning): NOT added. The Admin Directory API's default order is accepted. The only order-sensitive consumer, modules/reports/google_groups.py, was deleted by TASK-25.1.6.10.1.
- classify_google_error and 400s (comment of 2026-09-09, TASK-25.1.6.10 planning): NO classifier change. 400s stay mapped per provider, so the Sheets "Unable to parse range" local mapping in infrastructure/spreadsheets/google.py remains the only 400 handling.
- Directory residuals (comment of 2026-09-03, TASK-25.1.6.3.1 planning): excluded from this sweep, because neither isolates vendor SDK calls. Filed as standalone, low-priority tasks: R1 duplicated member mapping -> TASK-84; R2 inconsistent OAuth scope -> TASK-85.
- execute_batch_request: straight deletion. The relocation branch of the original AC was discharged by TASK-25.1.6.3.1. Carry into slice 1's PR description that the provider classifies per-item HttpErrors via classify_google_error and does not reproduce the helper's blanket PERMANENT_ERROR/BATCH_ERRORS.
- utils/ is not a vendor package: the guardrail warns and never fails CI for it, and never baselines it.
- Bug found while tracing generate_unique_id: modules/incident/schedule_retro.py builds description, reminders and a requestId that the scheduling adapter silently drops (pre-existing, carried over from the legacy module). Filed as standalone bug TASK-86. Kept out of every slice here.

CLOSURE VERIFICATION (from app/, after all three slices and TASK-25.1.7 merge)
- rg -n --hidden -g '!backlog/**' -g '!tmp/**' -g '!**/.venv/**' 'execute_google_api_request|execute_batch_request|integrations[./]utils' .. -> zero (AC#2)
- ls integrations/google_workspace -> __init__.py client.py; integrations/utils absent (AC#3)
- make check-vendor-package-contract (exit 0, no WARN) ; make check-sdk-typing ; rg -n google_workspace bin/baselines/ -> zero (AC#4, AC#6)
- uv run pytest tests/unit/bin -> the deliberately failing fixture test passes (AC#5)
Once this closes, TASK-25.1's AC#1 and TASK-25's AC#1/#2 are provable for the Google vendor, and TASK-25.1.6 can close.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-03 18:02
---
execute_batch_request WILL ALREADY BE DEAD WHEN YOU GET HERE (2026-09-03, task-planner, human-approved while planning TASK-25.1.6.3).

Your scope says 'resolve execute_batch_request' - either relocate it to the provider or write an amendment to decisions/outbound-clients.md. The first option is now taken by the new TASK-25.1.6.3.1, which moves the batch orchestration into GoogleDirectoryProvider (the adapter is the boundary, per decisions/outbound-clients.md) so it can add cross-round pagination and per-group failure reporting that the current all-or-nothing helper cannot express.

GREP-CONFIRMED 2026-09-03: execute_batch_request has exactly one consumer repo-wide - infrastructure/directory/google.py:17 (import) and :525 (call). Definition at integrations/google_workspace/client.py:170. Nothing else.

So once TASK-25.1.6.3.1 merges, your item collapses from a design decision to a straight deletion of a zero-consumer function plus its tests. No amendment to decisions/outbound-clients.md is needed - the deviation is removed rather than legalised. Note TASK-25.1.6.3.1 deliberately LEAVES the dead function in place rather than deleting it, because its AC#7 confines that PR's diff to app/infrastructure/directory/**; the deletion is yours.

Worth folding into your AC#7 CI guardrail: a vendor package exporting an OperationResult-returning orchestration helper is exactly the regrowth shape the guardrail should catch, since decisions/outbound-clients.md says app/integrations/<vendor>/ provides exactly factories, classify_<vendor>_error and settings.
---

author: @task-planner
created: 2026-09-03 20:08
---
TWO RESIDUALS ADDED TO YOUR SWEEP 2026-09-03 (task-planner, human-approved while planning TASK-25.1.6.3.1). Both are inside app/infrastructure/directory/google.py, deliberately left there because fixing them in TASK-25.1.6.3.1 would have mixed a mechanical refactor of out-of-scope methods into a behaviour PR (implementation-planning size-gate trigger #3).

R1. DUPLICATED MEMBER MAPPING. TASK-25.1.6.3.1 extracts _normalize_member_types and _map_members and uses them from the batch path and the new groups-with-members composition, but leaves get_group_members (today google.py:499-557) with its own inline copy of the same type-filter + _build_directory_member loop. Three call sites, two implementations. Collapsing it is a pure refactor with no behaviour change.

R2. INCONSISTENT OAUTH SCOPE FOR THE SAME CALL. get_group_members and the new composition request https://www.googleapis.com/auth/admin.directory.group.member.readonly; get_group_members_batch requests the broader https://www.googleapis.com/auth/admin.directory.group.readonly (today google.py:583). Same underlying members.list call, two scopes. TASK-25.1.6.3.1's AC#3 forbade changing it (it is a live path used by packages/access/sync/desired_state.py:160 and an OAuth scope change is not a no-op). Converging on the narrower member.readonly scope is safe - the delegation grant demonstrably exists, since get_group_members uses it in production - but it deserves its own small PR.

ALSO CONFIRMING YOUR AC#2: after TASK-25.1.6.3.1 merges, integrations/google_workspace/client.py::execute_batch_request has ZERO consumers repo-wide and is a straight delete. The 'relocated to the provider' branch of your AC#2 is satisfied and no amendment to decisions/outbound-clients.md is needed. One thing to carry into the PR description when you delete it: the provider's replacement does NOT reproduce execute_batch_request's blanket PERMANENT_ERROR/BATCH_ERRORS - it classifies per-item HttpErrors via classify_google_error, which is why the vendor helper could not simply move.
---

author: @task-planner
created: 2026-09-03 21:30
---
BEHAVIOURAL DELTA FOUND IN THE SURVIVING PROVIDER - TASK-25.1.6.4 PLANNING (2026-09-03, task-planner). Recording here because .11 is the final sweep over this surface and .3/.3.1 are already Done.

LOST orderBy="email". The legacy vendor module passed orderBy="email" on both list calls (integrations/google_workspace/google_directory.py:64 users.list, :98 groups.list). GoogleDirectoryProvider does NOT: infrastructure/directory/google.py's list_users builds users_resource.list(customer=..., maxResults=..., query=...) and list_groups builds groups_resource.list(customer=..., maxResults=...), neither with orderBy.

CONSEQUENCE. After TASK-25.1.6.4 repoints the legacy consumers, modules/reports/google_groups.py iterates groups in whatever order the Admin Directory API returns, so the sheet-creation order in the Google Groups members report changes. No correctness impact on modules/provisioning/users.py or modules/aws/identity_center.py, which filter by email membership.

HUMAN DECISION (2026-09-03): NOT fixed in .4 - that slice touches app/modules/ only and does not modify the provider. Recorded as a finding, named in .4's PR, and left for this sweep to decide: either add orderBy="email" to the provider's two list builders for parity, or accept API order and delete this note. If you add it, verify against the Admin SDK docs which orderBy values each endpoint accepts rather than assuming symmetry between users.list and groups.list.

ALSO, SMALLER: this task's AC#6 branch about execute_batch_request was already discharged by TASK-25.1.6.3.1 (the orchestration moved into the provider), per the note left on this task on 2026-09-03.
---

created: 2026-09-08 14:37
---
ORDERING UPDATE (2026-09-08): final closeout depends on TASK-25.1.7. The export-contract guardrail must observe google_service.py and all mirror modules already removed; it is the last task in the Google Workspace sequence.
---

author: @task-planner
created: 2026-09-09 15:06
---
SURFACE UPDATE FROM TASK-25.1.6.10 PLANNING (2026-09-09, task-planner). Your execute_google_api_request call-site count shrinks, and the shape of what is left changes.

REMOVED BY THE .10 SERIES: the 5 sites in integrations/google_workspace/sheets.py go when TASK-25.1.6.10.4 deletes that file, and the ~12 sites in integrations/google_workspace/google_drive.py go when TASK-25.1.6.10.5 deletes that one. Neither replacement uses the helper: infrastructure/spreadsheets/google.py and the reworked packages/incident/drive/adapters/google_drive.py each own their try/except plus classify_google_error at the SDK seam, per decisions/outbound-clients.md.

ONE THING TO CHECK WHEN YOU PLAN: TASK-25.1.6.10.2 establishes a precedent you may want to generalize or record. classify_google_error currently maps only {404}, {401,403} and {429,5xx} and RE-RAISES every other status, including 400. That makes an expected, documented Sheets outcome ('Unable to parse range', an HTTP 400) escape a Path A provider boundary. The Sheets Google implementation handles it locally by mapping that specific 400 to OperationStatus.NOT_FOUND before delegating to classify_google_error; the shared classifier is deliberately NOT modified, to keep the blast radius off Directory/Drive/Docs/Calendar. If your vendor-export-contract guardrail work touches classify_google_error, decide explicitly whether 400s deserve a mapped family there rather than per-provider - and if you widen the classifier, revisit the Sheets local mapping so the two do not disagree.
---
<!-- COMMENTS:END -->

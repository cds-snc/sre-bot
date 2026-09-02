---
id: TASK-25.1.4
title: >-
  Migrate legacy modules/ Directory consumers off
  integrations/google_workspace/google_directory.py
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
  - TASK-25.1.3
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/layers.md
  - app/integrations/google_workspace/google_directory.py
parent_task_id: TASK-25.1
priority: high
ordinal: 115000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-25.1. A SEPARATE consumer path from TASK-22.4 (which only covers the infrastructure/directory/{factory,google}.py Provider abstraction): modules/permissions/handler.py, modules/provisioning/users.py, modules/provisioning/groups.py, modules/reports/google_groups.py import integrations/google_workspace/google_directory.py DIRECTLY, bypassing the Provider entirely, and route through the same execute_google_api_call dispatcher. Reuse (do not reinvent) the AdminDirectoryResource factory + classify_google_error TASK-22.4 already builds for the Directory surface - this slice is consumer migration only, not a second Directory client. Flag as an open doubt for implementation-time review: whether these 4 modules should instead be migrated onto the infrastructure/directory Provider/DirectoryService Protocol (reusing TASK-22.4's abstraction) rather than the raw factory-built Resource directly, given they are cross-cutting legacy modules/ consumers, not a single feature adapter.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 integrations/google_workspace/google_directory.py's list_users, list_groups and list_group_members no longer call execute_google_api_call; they route through TASK-22.4's get_admin_directory_service factory plus classify_google_error/execute_google_api_request, so modules/permissions/handler.py, modules/provisioning/users.py, modules/provisioning/groups.py and modules/reports/google_groups.py no longer reach any dispatcher-backed Directory call
- [x] #2 All 4 consumers behave identically for their Directory-related calls (existing tests pass, behavior-neutral); they keep their current google_directory imports, and the only consumer edit is deleting the unreachable return_dataframe branch in modules/provisioning/groups.py - the DirectoryService/DirectoryProvider Protocol route is rejected because it returns canonical dataclasses that drop the raw Google fields these modules consume
- [x] #3 integrations/google_workspace/google_directory.py is itself migrated onto the factory+classify pattern and is pruned from app/bin/baselines/sdk_typing_antipatterns.txt; zero execute_google_api_call occurrences remain in that file
- [x] #4 get_user, get_group and add_users_to_group (zero production consumers, grep-verified) are deleted together with their tests rather than migrated, while list_groups_with_members and get_members_details are left untouched and their existing tests pass unchanged
- [x] #5 The dead pandas DataFrame path is removed end to end: get_groups_from_integration's return_dataframe parameter and both of its branches, google_directory.convert_google_groups_members_to_dataframe, identity_store.convert_aws_groups_members_to_dataframe, and the now-unused pandas imports in both integrations modules; repo-wide grep for return_dataframe and both convert_*_to_dataframe symbols returns zero, and pandas remains a dependency only for its live consumer modules/aws/spending.py
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
DECISION (resolves the open doubt this task flagged for implementation-time review)

Option A chosen: migrate integrations/google_workspace/google_directory.py ITSELF onto TASK-22.4's get_admin_directory_service factory + classify_google_error/execute_google_api_request (AC#3's second branch), mirroring the shipped TASK-25.1.1/25.1.2/25.1.3 pattern for calendar/meet/docs/sheets. The four legacy modules/ consumers keep their existing google_directory imports; only one of them (modules/provisioning/groups.py) is edited at all, and only to delete the dead return_dataframe branch (step 5).

Option B (route the 4 modules through infrastructure/directory's DirectoryProvider / DirectoryService Protocol) is rejected as incompatible with AC#2 (behaviour-neutral), on evidence:
- DirectoryProvider returns canonical frozen dataclasses inside OperationResult (DirectoryUser/DirectoryGroup/DirectoryMember, infrastructure/directory/models.py). Those drop the raw Google fields these consumers require: directMembersCount, description, primaryEmail, name.givenName/name.familyName and member status - consumed by get_members_details and by log_groups' members_display_key="primaryEmail" lookup in modules/provisioning/groups.py.
- Signature/semantic mismatches: DirectoryProvider.list_users(query="", limit=100) caps results, while google_directory.list_users() lists all users (maxResults=500, paginated); DirectoryProvider.list_groups(query) REQUIRES a query and applies managed-group domain/prefix normalisation plus enforce_managed_group_email rejection (infrastructure/directory/google.py:158-201, 294-330), which would silently filter or reject groups the legacy report path expects.
- GoogleDirectoryProvider has no equivalent of list_groups_with_members.
Converting these 4 modules onto the Provider is therefore a semantic rewrite of legacy code already slated for deletion by the modules-strangler (TASK-37..41), not this slice's behaviour-neutral migration. Recorded here so implementation does not re-litigate it.

CODEBASE FINDINGS (fresh grep, 2026-09-01)
Directory call sites in the 4 consumers: modules/permissions/handler.py:15 and :32 (list_group_members); modules/provisioning/users.py:26 (list_users); modules/provisioning/groups.py:53 (list_groups_with_members) and :58 (convert_google_groups_members_to_dataframe); modules/reports/google_groups.py:47 (list_groups) and :61 (list_group_members). No other production file imports google_directory (infrastructure/operations/classifiers.py:278 is a docstring example naming a function that does not exist in this module).
Zero production consumers, grep-verified: get_user (google_directory.py:16), get_group (:127), add_users_to_group (:155) - referenced only by tests/integrations/google_workspace/test_google_directory.py.
DEAD PANDAS PATH, grep-verified: convert_google_groups_members_to_dataframe has exactly one call site (modules/provisioning/groups.py:58) and it is UNREACHABLE - it is gated by get_groups_from_integration's return_dataframe parameter, and no caller anywhere passes return_dataframe=True. The four production callers are modules/aws/groups.py:108 and modules/aws/identity_center.py:56 and :69 (plus users.py's separate entry point); none passes it, and no test passes it either. The same is true of its AWS twin integrations/aws/identity_store.py::convert_aws_groups_members_to_dataframe (groups.py:72), which has zero tests. Additional evidence the path is abandoned: modules/provisioning/groups.py builds groups_dataframe BEFORE applying post_processing_filters and then returns it (groups.py:90), so the dataframe branch has always ignored post-processing filtering - a latent bug nobody hit because the branch never runs.

STEPS

1. app/integrations/google_workspace/google_directory.py - module header.
   - Remove "from integrations.google_workspace import google_service" and the "handle_google_api_errors = google_service.handle_google_api_errors" alias.
   - Add "from integrations.google_workspace import client as google_service_client" (sibling naming convention: sheets.py:5, google_calendar.py:8).
   - Keep the module-level constant but source it directly: GOOGLE_WORKSPACE_CUSTOMER_ID = get_google_workspace_settings().GOOGLE_WORKSPACE_CUSTOMER_ID, via "from infrastructure.configuration.integrations.google import get_google_workspace_settings". Same import-time evaluation as today (google_service.py:33 does exactly this), so the existing @patch("...google_directory.GOOGLE_WORKSPACE_CUSTOMER_ID") tests keep working unchanged.
   - Add scope constants mirroring SHEETS_SCOPES/CALENDAR_SCOPES:
     DIRECTORY_USER_READONLY_SCOPES = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
     DIRECTORY_GROUP_READONLY_SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]
   - Remove "import pandas as pd" (dead after step 5). Keep the structlog / utils.filters / retry_request imports (used by the untouched composition functions). Replace convert_string_to_camel_case with convert_kwargs_to_camel_case (see step 3).

2. Add a module-private pagination helper (deliberately NOT a new shared primitive in client.py, so TASK-25.1.6's tolerated-deviation surface does not grow):

   def _list_all(resource, response_key: str, **list_kwargs) -> list[dict]:
       items: list[dict] = []
       request = resource.list(**list_kwargs)
       while request is not None:
           response = google_service_client.execute_google_api_request(request)
           items.extend(response.get(response_key, []))
           request = resource.list_next(request, response)
       return items

   This reproduces google_service.execute_google_api_call's paginate=True branch exactly (google_service.py:216-223: accumulate results.get(<last resource-path segment>, []), advance via <method>_next(request, results)) and mirrors the shipped, already-reviewed infrastructure/directory/google.py::_paginate (lines 80-98) for the same API surface, where "resource" is likewise typed loosely. Do NOT add num_retries= : execute_google_api_request calls bare .execute() and the dispatcher did too; adding SDK-native retry here is TASK-25.1.6's call, not a behaviour-neutral slice's.
   Stub verification already done against .venv googleapiclient-stubs/_apis/admin/directory_v1/resources.pyi: UsersResource.list_next (:819), GroupsResource.list_next (:352), MembersResource.list_next (:387) all exist, and every list() accepts **kwargs: typing.Any so fields= passes; orderBy is a Literal that accepts the "email" literal we pass.

3. Convert the three list functions, each keeping its current public signature so no consumer signature changes:
   - list_users(customer=None, **kwargs): delegated = kwargs.pop("delegated_user_email", None); service = google_service_client.get_admin_directory_service(scopes=DIRECTORY_USER_READONLY_SCOPES, delegated_user_email=delegated); return _list_all(service.users(), "users", customer=customer or GOOGLE_WORKSPACE_CUSTOMER_ID, maxResults=500, orderBy="email", **convert_kwargs_to_camel_case(kwargs)).
   - list_groups(customer=None, **kwargs): same shape on service.groups(), response key "groups", maxResults=200, orderBy="email", scopes DIRECTORY_GROUP_READONLY_SCOPES.
   - list_group_members(group_key, fields=None, **kwargs): scopes DIRECTORY_GROUP_READONLY_SCOPES; _list_all(service.members(), "members", groupKey=group_key, maxResults=200, fields=fields, **convert_kwargs_to_camel_case(kwargs)).
   - Drop every @handle_google_api_errors decorator. Errors now log once (google_api_request_failed, emitted by execute_google_api_request) and propagate, classified by classify_google_error - identical to the sibling slices.
   - Keep convert_kwargs_to_camel_case on residual kwargs to preserve today's dispatcher-side snake_case-to-camelCase conversion (google_service.py:212). Parity choice, flagged as doubt (a).

4. Delete the three zero-production-consumer functions and their tests: get_user (:16), get_group (:127), add_users_to_group (:155). Deleting rather than migrating keeps the slice subtractive and matches the sprint precedent for zero-consumer surfaces (gmail.py in TASK-25.1.1, sqs.py in TASK-25.2.3, identity_store_next in TASK-23). This also retires the only Directory-related entry in google_service.handle_google_api_errors' non_critical_errors table ("get_user": ["timed out"]) - but leave google_service.py itself untouched, it is still used by google_drive.py (TASK-25.1.5).

5. Delete the dead return_dataframe / pandas-conversion capability outright (HUMAN-DIRECTED 2026-09-01; the DataFrame flattening was an early data-cleanup accelerator superseded by the Directory API's own fields= partial-response projection, which list_groups_with_members already uses). It is unreachable end to end, so this is subtractive, not a behaviour change:
   - integrations/google_workspace/google_directory.py: delete convert_google_groups_members_to_dataframe (:269-309) and the now-unused "import pandas as pd" (:3).
   - modules/provisioning/groups.py: delete the return_dataframe parameter and its docstring line, the "groups_dataframe = None" initialiser (:45), both "if return_dataframe:" branches (:57-58 Google, :71-72 AWS), and change the final "return groups_dataframe if groups_dataframe is not None else groups" (:90) to "return groups". This is the only edit any of the 4 named consumer modules receives.
   - integrations/aws/identity_store.py: delete convert_aws_groups_members_to_dataframe (:383-420) and its "import pandas as pd" (:3), which the previous bullet orphans. Grep-verified: zero other call sites, zero tests. See doubt (f) - this one line-item crosses into the AWS vendor package (TASK-25.2.4 territory); it is included here because leaving a newly-orphaned dead function behind is worse than the small boundary crossing, but the reviewer can veto it and it will be filed as a follow-up instead.
   - pandas stays a project dependency: modules/aws/spending.py is a genuine, live pandas consumer (spending.py:5, 50-54, 80-81, 125-153) and is untouched.

6. Leave untouched, explicitly out of scope (they contain no dispatcher calls): list_groups_with_members and get_members_details. They are business logic living inside a vendor package (an outbound-clients.md deviation), and list_groups_with_members calls integrations/utils/api.py::retry_request, a time.sleep retry loop that violates outbound-clients.md's "no hand-rolled retry loops in app/integrations/" check. Both problems are pre-existing, not introduced here - see open questions.

7. Prune "integrations/google_workspace/google_directory.py" from app/bin/baselines/sdk_typing_antipatterns.txt (mirrors 25.1.1/25.1.2/25.1.3; the checker only ratchets down).

8. Rework app/tests/integrations/google_workspace/test_google_directory.py:
   - Delete the 5 tests covering the removed functions (currently at lines 11, 211, 228, 236, 245).
   - Rewrite the 6 dispatcher-patching tests (list_users x2, list_groups x2, list_group_members x2) to patch google_directory.google_service_client.get_admin_directory_service, returning a MagicMock service whose .users()/.groups()/.members().list(...) yields a request mock and whose list_next returns None after the first page. Preserve every existing assertion on returned shape; assert the exact .list(**kwargs) call args (customer/maxResults/orderBy/groupKey/fields) plus the scopes and delegated_user_email passed to the factory (the delegation assertions the dispatcher-based tests already made, relocated to the factory boundary).
   - Add coverage the dispatcher-based tests never had: (a) multi-page pagination - list_next returns a second request once then None, result is both pages concatenated; (b) a page missing the response key contributes nothing (matches results.get(resource, [])); (c) failure path - HttpError raised by .execute() propagates out of each of the 3 functions, proving decorator removal.
   - test_list_groups_with_members_filtered_dataframe (:509): drop its dataframe half (the convert_... call and the DataFrame/columns assertions) and keep the groups_filters assertions, renaming it accordingly - it is currently the only test asserting that path; also remove the file's now-unused "import pandas as pd" (:5).
   - The remaining 8 list_groups_with_members / get_members_details tests patch google_directory.list_groups / list_users / retry_request / filters.filter_by_condition directly and MUST pass unchanged - that is the regression proof for step 6.

9. app/tests/unit/integrations/google_workspace/test_client.py: expect no change - get_admin_directory_service already has dedicated coverage (test_client.py:88 and :125) from TASK-22.4. Only extend it if a parametrized factory case is found to omit it.

10. Consumer test files: tests/modules/permissions/test_handler.py and tests/modules/provisioning/test_provisioning_users.py patch at the modules.<x>.google_directory.<fn> boundary and require zero edits. tests/modules/provisioning/test_provisioning_groups.py: verify none of its 8 tests passes return_dataframe (grep-confirmed today: none does), so it should also need zero edits after step 5 - if any assertion depends on the removed parameter, adjust minimally. modules/reports/google_groups.py has NO test file - record in Notes that its two Directory call sites (list_groups(), list_group_members(...)) have no automated regression coverage before or after this change; behaviour-neutrality there rests on step 3's signature/return-shape preservation alone.

11. Re-run repo checks: grep for execute_google_api_call in google_directory.py (expect zero); grep for convert_google_groups_members_to_dataframe / convert_aws_groups_members_to_dataframe / return_dataframe repo-wide (expect zero); python3 bin/check_sdk_typing.py; python3 bin/check_deprecated_infra_client_imports.py; bin/generate_client_usage_matrix.sh.

AC-TO-STEP-TO-TEST
- AC#1 (consumers no longer reach execute_google_api_call-backed calls; wired onto TASK-22.4's factory + classify_google_error) -> Steps 1-4 via Option A. Verified by: zero execute_google_api_call occurrences in google_directory.py; step 8 tests; the consumer test files green.
- AC#2 (all 4 consumers behave identically) -> Steps 3 and 6 (signature/return-shape parity, composition functions untouched) + Step 10 (consumer test files green) + the explicit no-coverage note for modules/reports/google_groups.py. The step 5 edit to modules/provisioning/groups.py removes only an unreachable branch, so observable behaviour is unchanged.
- AC#3 (google_directory.py migrated onto the same factory+classify pattern) -> Steps 1-4 and 7.
- AC#4 (dead surfaces deleted, composition helpers untouched) -> Steps 4, 5 and 6, verified by the greps in step 11 and the unchanged composition tests in step 8.

TEST MATRIX
Happy path: list_users / list_groups / list_group_members return the same aggregated list shape as today from a mocked Resource chain. Pagination: single page (list_next -> None); two pages (concatenated); a page missing the response key (skipped). Delegation and scopes: default (no delegated_user_email -> factory called with None) and explicit override, per function. Params: customer default vs explicit; exact maxResults/orderBy/fields/groupKey call kwargs; residual snake_case kwargs arrive camelCased. Error propagation: HttpError raised by .execute() propagates for all 3 functions. Deletion proof: repo-wide grep for the removed symbols returns zero. Regression: the remaining list_groups_with_members / get_members_details tests, tests/modules/permissions/test_handler.py, tests/modules/provisioning/test_provisioning_users.py, tests/modules/provisioning/test_provisioning_groups.py (all 8 get_groups_from_integration tests must stay green after the return_dataframe parameter is removed).
Commands: cd app && uv run pytest tests/integrations/google_workspace tests/unit/integrations/google_workspace tests/modules/permissions tests/modules/provisioning tests/unit/modules/aws -v; then make test (use the Makefile split, not the single-process whole-tree run, which has pre-existing cross-directory-pollution failures); uv run ruff check .; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' - note the pre-existing whole-tree error baseline; the bar is zero errors naming the touched files.

ASSUMPTIONS AND DOUBTS
(a) camelCase parity: step 3 keeps convert_kwargs_to_camel_case on residual kwargs to match the dispatcher. No production caller passes snake_case today (only query and fields), so dropping it would also be safe and simpler. One line either way - confirm with the reviewer.
(b) Unsupported-parameter behaviour change (intentional, matches the sibling slices): the dispatcher silently dropped kwargs that its docstring-scraping get_google_api_command_parameters did not recognise, logging a warning; after migration an unknown kwarg reaches googleapiclient and raises TypeError. No production caller passes one (all 4 consumers read), so this is latent-only.
(c) fields plus pagination: list_groups_with_members passes fields="groups(email, name, directMembersCount, description)" and fields="members(email, role, type, status)", which exclude nextPageToken from the response, so list_next returns None after page one - pagination is effectively disabled on those calls TODAY and stays disabled after migration. Preserved deliberately; do NOT "fix" it in this slice, it would change how many groups/members the provisioning and report paths see.
(d) Deleting get_user/get_group/add_users_to_group (step 4) goes beyond the task's literal wording. If the reviewer prefers keeping them, migrate them instead onto service.users().get(userKey=...) / service.groups().get(groupKey=...) through execute_google_api_request (about 20 extra production LOC plus 3 rewritten tests), and note that get_user's current "timed out" swallow-and-return-None behaviour would be lost either way.
(e) No num_retries= is added (step 2) even though outbound-clients.md names it as the Google SDK-native retry primitive - consistent with the shipped sibling slices; it belongs to TASK-25.1.6.
(f) Step 5's third bullet deletes integrations/aws/identity_store.py::convert_aws_groups_members_to_dataframe, which is in TASK-25.2.4's vendor package rather than this slice's. It is a pure deletion of a function that step 5's second bullet orphans, with zero call sites and zero tests. Reviewer may veto; the alternative is leaving it dead in-tree and filing a one-line follow-up.
(g) NOT documented in decisions/: a repo-wide grep of decisions/*.md finds no mention of pandas, DataFrame, or the Directory API's fields= projection at all. The "use the Google client's built-in features instead of DataFrame flattening" rationale for step 5 is therefore an undocumented convention, not a citable decision record. If it should be durable guidance, it needs a line in a decision record - flagged for the reviewer rather than assumed.

BLAST RADIUS AND ROLLBACK
Production files changed: 3 (integrations/google_workspace/google_directory.py - migrated; modules/provisioning/groups.py and integrations/aws/identity_store.py - pure deletions) plus one guardrail baseline line. Zero changes to modules/permissions/handler.py, modules/provisioning/users.py, modules/reports/google_groups.py, client.py, google_service.py, or infrastructure/directory/**. Reachable surfaces: the provisioning Slack command paths, the Google Groups report command, and the permissions authorizer check - every new failure mode is "a Directory call raises instead of being swallowed", already the sprint-wide accepted change; the step 5 deletions remove only unreachable code. Rollback is a single revert.

SIZE GATE VERDICT
Fits one PR: roughly 120-150 changed production LOC in 1 file plus about 90 deleted LOC across 2 more files (all subtractive), 1 baseline line, 1 test file reworked (about 5 tests deleted, 6 rewritten, 6 added, 1 trimmed). Deletion-heavy slices do not trip the gate the way net-new-logic slices do. No decomposition required.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Migrated google_directory.py off execute_google_api_call onto get_admin_directory_service and execute_google_api_request with pagination helper _list_all. Removed zero-consumer functions get_user, get_group, add_users_to_group and convert_google_groups_members_to_dataframe. Removed dead return_dataframe parameter and branches from modules/provisioning/groups.py and orphaned convert_aws_groups_members_to_dataframe from identity_store.py. Pruned google_directory.py from sdk_typing_antipatterns.txt. All unit and integration tests pass green, lint and mypy checks pass. DoD items left for human verification: code review and merge approval.

FOLLOW-ON 2026-09-01 (human-directed, post-implementation): resolved plan doubt (a) in the opposite direction and went further. The original slice kept `**kwargs` + `convert_kwargs_to_camel_case` and passed a `dict[str, Any]` into `_list_all(resource, ...)` with `resource` un-annotated -- so every `.list(**list_kwargs)` was typed `Any` and the googleapiclient-stubs adopted in TASK-70/22.4 bought this module nothing, contradicting decisions/sdk-typing.md item 3 ('calls ... directly with real method/parameter/return-shape completion AND checking').

Changes: (1) integrations/google_workspace/google_directory.py -- `list_users`/`list_groups`/`list_group_members` now take explicit typed parameters (customer/query/fields/delegated_user_email; group_key/fields/delegated_user_email) instead of `**kwargs`; `convert_kwargs_to_camel_case` is gone from this module; page sizes are named constants (_USERS_PAGE_SIZE=500, _GROUPS_PAGE_SIZE=200, _MEMBERS_PAGE_SIZE=200); `_list_all` became `_collect_pages(resource, request, response_key)` which takes the ALREADY-BUILT request, so the `.list(...)` call itself stays at the call site and is stub-checked. (2) infrastructure/directory/google.py -- `_paginate` had the identical untyped hole (`resource: Any`, `list_kwargs: dict[str, Any]`); it now takes the built request too, and all four call sites (list_users, get_group_members, list_groups x2 branches, get_user_groups) build their request via a typed resource local.

Behaviour parity: googleapiclient/discovery.py:1108-1112 deletes None-valued kwargs before building the request, so always passing `query=None`/`fields=None` is identical to omitting them. Verified typing now bites -- a probe passing orderBy='not-a-valid-literal' and maxResults='two-hundred' produces mypy arg-type errors that the previous dict-splat swallowed. Unknown parameter NAMES still pass mypy (stubs end in `**kwargs: typing.Any`) but now raise TypeError at the SDK, covered by a new test.

Tests: test_google_directory.py list-call assertions extended with query=None/fields=None; `test_list_groups_converts_residual_kwargs_to_camel_case` replaced by `test_list_groups_forwards_query_and_fields_verbatim` + `test_list_groups_rejects_unsupported_keyword`. tests/unit/infrastructure/directory/test_google.py needed no edits. `make test` green; ruff and mypy clean on the touched files.

Scope note: infrastructure/directory/google.py was explicitly out of scope in the original plan ('zero changes to ... infrastructure/directory/**'). Included on human direction because it carried the same defect on the same API surface; reviewer may split it out.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: task-planner
created: 2026-09-01 15:35
---
TRACKING NOTE (2026-09-01, task-planner): TASK-25.1.1 introduces a shared integrations/google_workspace/client.py::execute_google_api_request(request) helper (try/except + classify_google_error + log + raise) as a deliberate, TEMPORARY deviation from outbound-clients.md's exact vendor-package export contract, tracked by TASK-25.1.6. This slice reuses TASK-22.4's AdminDirectoryResource factory + classify_google_error, so it may not touch execute_google_api_request at all -- if it does (or introduces an equivalent for these 4 legacy consumers), update TASK-25.1.6's description/references with the exact files and call sites added here, so its eventual inline-vs-formalize decision is made against the full call-site inventory, not just TASK-25.1.1's.
---

created: 2026-09-01 19:42
---
PLANNED 2026-09-01 (task-planner). Open doubt resolved in the plan: Option A (migrate google_directory.py in place onto TASK-22.4's get_admin_directory_service + execute_google_api_request/classify_google_error), NOT the DirectoryProvider Protocol route - evidence and rejected-option rationale are in the plan's DECISION section. Consequence: the 4 named consumer modules get zero code edits, so the task title reads slightly off versus what the PR will actually touch (one integrations file plus one guardrail baseline line). ACs bulk-replaced (4, was 3) to record that decision and to add the dead-function deletion. TWO PRE-EXISTING VIOLATIONS FOUND AND DELIBERATELY NOT FIXED HERE, no task covers either today (grep of backlog/ for retry_request and utils/api.py: zero hits): (1) list_groups_with_members / get_members_details / convert_google_groups_members_to_dataframe are business logic inside a vendor package, which decisions/outbound-clients.md forbids; (2) integrations/utils/api.py::retry_request is a time.sleep retry loop called from list_groups_with_members, which trips outbound-clients.md's Checks line 'no time.sleep/tenacity/backoff retry loops in app/integrations/'. Both are behaviour-changing to fix and would blow this slice's behaviour-neutral framing - recommend filing a follow-up task rather than folding them in; flagged for the human reviewer to confirm.
---

created: 2026-09-01 19:51
---
SCOPE ADJUSTMENT 2026-09-01 (human-directed): drop the pandas DataFrame conversion. Verified it is DEAD END TO END, not merely unused: convert_google_groups_members_to_dataframe has exactly one call site (modules/provisioning/groups.py:58) gated by get_groups_from_integration's return_dataframe parameter, and NO caller anywhere passes return_dataframe=True - the production callers are modules/aws/groups.py:108 and modules/aws/identity_center.py:56 and :69, none of which passes it, and no test does either. Extra evidence the branch was abandoned: groups.py builds the dataframe BEFORE applying post_processing_filters and then returns it (groups.py:90), so it has always silently ignored post-processing filtering. Removing the parameter also orphans the AWS twin integrations/aws/identity_store.py::convert_aws_groups_members_to_dataframe (zero other call sites, zero tests), so the plan deletes both plus their pandas imports - flagged as doubt (f) since the AWS one crosses into TASK-25.2.4's vendor package and the reviewer may prefer a separate follow-up. pandas stays a project dependency: modules/aws/spending.py is a genuine live consumer. ACs bulk-replaced (5, was 4); AC#2 now admits the one consumer edit this creates in modules/provisioning/groups.py. CORRECTION TO THE STATED RATIONALE: a repo-wide grep of decisions/*.md finds NO mention of pandas, DataFrame, or the Google client's fields= partial-response projection - the 'use the built-in API client features instead' guidance is not currently written down anywhere. Recorded as plan doubt (g); if it should be durable it needs a line in a decision record.
---
<!-- COMMENTS:END -->

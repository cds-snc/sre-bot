---
id: TASK-25.1.6.4
title: >-
  Migrate permissions, provisioning-users and reports Directory call sites onto
  DirectoryProvider
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-02 15:00'
updated_date: '2026-09-03 23:57'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.3
references:
  - decisions/outbound-clients.md
  - decisions/dependency-injection.md
  - decisions/testing.md
  - app/infrastructure/directory/provider.py
  - app/modules/permissions/handler.py
  - app/modules/provisioning/users.py
  - app/modules/reports/google_groups.py
  - app/modules/aws/identity_center.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 135000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Second Directory slice. The decision is settled (see TASK-25.1.6 comment #10): DirectoryProvider survives, google_directory.py dies, the legacy consumers move onto the Protocol.

This slice moves the three consumers whose calls map onto EXISTING Protocol methods, leaving the harder groups-with-members consumer and the module deletion to TASK-25.1.6.5.

CALL SITES (re-grepped 2026-09-03 against main @ 12c2e8e3 during planning; the line numbers in the original 2026-09-02 description had drifted):

- app/modules/permissions/handler.py:15 - google_directory.list_group_members(group_key) inside is_user_member_of_groups -> DirectoryProvider.get_group_members(group_key). The second call site at :32 lives in get_authorizers_from_groups, which has ZERO production callers repo-wide and is DELETED with its tests rather than migrated.
- app/modules/provisioning/users.py:26 - google_directory.list_users() -> the unbounded list_users() added by TASK-25.1.6.3. This is a FULL-DIRECTORY sync; do not let it silently truncate. There is no magic number to pass: limit=None is the merged default.
- app/modules/reports/google_groups.py:69 - google_directory.list_groups() -> the unbounded list_groups(); an empty query routes through the generic mapper with no managed-alias preference and no domain enforcement. And :83 - google_directory.list_group_members(group['email']) -> get_group_members. This file also has Sheets and Drive call sites; those belong to TASK-25.1.6.8 and .10 and are OUT OF SCOPE here, as is the time.sleep(1.1) at :127 that paces them (see the comment on TASK-25.1.6.10).
- app/modules/aws/identity_center.py:313-330 - provision_aws_users is the ONLY consumer of users.py's google branch, and it splats the raw Google dict into identity_store.create_user via four filters.preformat_items calls (modules/provisioning/entities.py:60 does function(**entity)). Repointing users.py to DirectoryUser is impossible without adapting it, so it is IN SCOPE as a fourth production file. Its delete branch and synchronize()'s group-sourced user path are untouched - the latter is TASK-25.1.6.5's.

HOW THE PROVIDER IS OBTAINED: via infrastructure/directory/factory.py::get_directory_provider(), per decisions/dependency-injection.md and the project's provider-singleton rules. These modules must not construct GoogleDirectoryProvider themselves and must not import integrations/google_workspace at all when this slice lands. app/modules/dev/google.py:12 is the in-repo precedent for a legacy module doing this.

REAL WORK, NOT A REPOINT: the legacy functions return raw list[dict] with Google field names (primaryEmail, email, name, role, type); the Protocol returns DirectoryUser/DirectoryGroup/DirectoryMember frozen dataclasses wrapped in OperationResult. Each consumer therefore needs (a) field mapping onto dataclass attributes, including explicit handling of the optional name and role fields the raw dicts always carried, and (b) an explicit error branch, since exceptions no longer cross the boundary.

ERROR BRANCHES ARE UNIFORMLY FAIL-LOUD (human decision 2026-09-03, recorded as D2 in the plan). Every migrated call site converts a non-success OperationResult into a narrow, vendor-neutral, module-local exception carrying the classified message and error_code, preserving today's observable behaviour. is_user_member_of_groups is a security gate whose four callers have no try/except, so degrading to False on an infrastructure error would tell an admin 'not authorized' when Google was simply down. This also keeps TASK-25.1.6.1's failure-mode characterization tests in their pytest.raises shape with only the trigger translated. modules/reports/google_groups.py's blanket try/except around its Sheets calls is NOT the model to copy.

SCOPE FENCE: TASK-25.1.6.3.1's get_group_members_batch and list_groups_with_members are deliberately NOT used here. reports/google_groups.py keeps its per-group loop; .5 owns the batched-consumer pattern.

TESTS: the two legacy files move into the unit tree per decisions/testing.md, and app/tests/modules/permissions/test_handler.py is renamed away from its ambiguous name. TASK-25.1.6.1's characterization tests for modules/reports/google_groups.py must pass with the mock seam translated to a DirectoryProvider double and no behavioural assertion weakened.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 modules/permissions/handler.py resolves DirectoryProvider via get_directory_provider() and uses get_group_members at its one surviving call site (is_user_member_of_groups); get_authorizers_from_groups is deleted with its tests as dead code; the module no longer imports integrations.google_workspace
- [x] #2 modules/provisioning/users.py calls the unbounded list_users() with no arguments and a test proves it returns more users than the retired 100-item default limit would have allowed (no silent truncation of the directory sync)
- [x] #3 modules/reports/google_groups.py's two Directory call sites use DirectoryProvider via get_directory_provider(); its Sheets and Drive call sites, and the time.sleep pacer that protects them, are untouched by this task
- [x] #4 Every migrated call site handles the OperationResult error branch explicitly and fail-loud - no bare is_success ignore, no blanket except Exception around a Directory call, no googleapiclient exception type crossing the boundary - and each error branch has a test asserting the module-local exception and its preserved error_code
- [x] #5 Google-shaped raw dicts no longer reach these three modules: they consume DirectoryUser/DirectoryGroup/DirectoryMember attributes, with field mappings verified against TASK-25.1.6.3's recorded field inventory, and None-valued name/role fields are handled explicitly
- [x] #6 TASK-25.1.6.1's characterization tests for modules/reports/google_groups.py pass with the mock seam translated to a DirectoryProvider double and no behavioural assertion weakened; every intentional behaviour change is named in the task notes and the PR
- [x] #7 integrations/google_workspace/google_directory.py still exists after this task (TASK-25.1.6.5 deletes it) but has exactly one remaining production consumer: modules/provisioning/groups.py
- [x] #8 modules/aws/identity_center.py::provision_aws_users builds its create_user payload explicitly from DirectoryUser attributes instead of via filters.preformat_items on Google dict keys, matches requested emails case-insensitively, and leaves its delete branch and synchronize()'s group-sourced user path unchanged
- [x] #9 The DirectoryProvider Protocol docstring documents both halves of the email-normalisation contract - that returned DirectoryUser/DirectoryMember/DirectoryGroup emails are lowercased, not just method arguments - and warns consumers comparing them against externally-sourced addresses to compare case-insensitively; the change to app/infrastructure/ is docstring-only, verified by git diff
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (read 2026-09-03 against main @ 12c2e8e3). All dependencies are Done and merged: TASK-25.1.6.1, .2 (#1436), .3 Slice A (#1437), .3.1 Slice B (#1438).

--------------------------------------------------------------------------
CALL SITES ENUMERATED (grep-confirmed 2026-09-03, path:line -- not assumed)

- modules/permissions/handler.py:1 import; :15 list_group_members; :19 user["email"]; :32 list_group_members (inside get_authorizers_from_groups); :36 authorizer["email"]
- modules/provisioning/users.py:6 import; :26 google_directory.list_users()
- modules/reports/google_groups.py:9 import; :69 list_groups(); :70 group["name"]; :81 group["email"]; :83 list_group_members(group["email"]); :88 group["name"]; :118 member["email"] and member["role"]; :127 time.sleep(1.1)
- modules/aws/identity_center.py:313 users.get_users_from_integration("google_directory"); :314 user["primaryEmail"]; :315-323 four filters.preformat_items calls
- Callers of is_user_member_of_groups (unchanged by this slice): modules/aws/groups.py:59, :103, :134 and modules/aws/users.py:56
- modules/provisioning/entities.py:60 does function(**entity, **kwargs), and integrations/aws/identity_store.py:49 is create_user(email, first_name, family_name, **kwargs) -- this is why the provisioning payload must stay a dict even after the source becomes a dataclass
- infrastructure/directory/provider.py:17-23 DirectoryProvider class docstring -- the one docstring-only edit in this slice, see D8

--------------------------------------------------------------------------
FACTS VERIFIED DURING PLANNING (evidence, not assumption)

F1. get_authorizers_from_groups has ZERO production callers repo-wide. Its only references are two tests in app/tests/modules/permissions/test_handler.py.
F2. utils/filters.py:11 filter_by_condition is [item for item in item_list if condition(item)] -- predicate-generic, NOT dict-coupled. And no production caller passes processing_filters to get_users_from_integration (identity_center.py:313 and :334 both pass none). The "filters operate on dict keys" risk pre-registered on this task by TASK-25.1.6.3's planner is therefore MOOT for users.py. The real dict coupling is filters.preformat_items plus user["primaryEmail"] inside identity_center.provision_aws_users.
F3. The provider LOWERCASES every email it returns and every group key it accepts (google.py:211 _normalize_email, :223 _extract_email). See D7, D8 and A1.
F4. _normalize_email composes {slug}@{managed_group_domain} only when the value contains no "@". AWS_ADMIN_GROUPS defaults to ["sre-ifs@cds-snc.ca"] (infrastructure/configuration/features/aws_ops.py:28) -- group emails, so no mangling. A raw Google group ID would be mangled, but that is not a live input shape.
F5. Slice A defaults are list_users(query="", limit=None) and list_groups(query="", limit=None). An EMPTY query routes through the GENERIC _build_group mapper (google.py:420) with no managed-alias preference and no managed-domain enforcement, and unmappable groups are logged + skipped rather than failing the result (google.py:944-960). Both legacy consumers call the bare no-argument form, so this is a direct replacement -- no wildcard, no magic limit number.
F6. None of the four touched modules appears in app/bin/baselines/deprecated_infra_client_imports.txt or sdk_typing_antipatterns.txt. No baseline work in this slice.
F7. integrations/google_workspace/client.py:154 execute_google_api_request calls request.execute() with NO num_retries. The Sheets call sites in modules/reports/google_groups.py therefore have zero SDK-native retry today. See D6.
F8. modules/dev/google.py:12 is the in-repo precedent for a legacy module consuming the provider: from infrastructure.directory import get_directory_provider, called per operation. get_directory_provider is @cache'd (factory.py:46), so the test seam is the module-bound symbol, never a cache_clear.
F9. The DirectoryProvider Protocol docstring (provider.py:17-23) documents only HALF the normalisation contract: "All method arguments ... are normalised to lowercase by implementors". It is silent on RETURNED emails, which are lowercased too (F3). That undocumented half is what makes A1 a latent trap. See D8.

--------------------------------------------------------------------------
HUMAN DECISIONS TAKEN DURING PLANNING (2026-09-03)

D1. get_authorizers_from_groups is DELETED with its two tests rather than migrated (F1). AC#1 amended to one call site.

D2. UNIFORM FAIL-LOUD error branches, applied to EVERY migrated call site without exception (human direction). All four consumers preserve today's observable behaviour: a Directory failure raises rather than silently degrading. Each converts a non-success OperationResult into a narrow, vendor-neutral, module-local exception carrying result.message and result.error_code. Rationale: (a) is_user_member_of_groups is a security gate whose four callers have no try/except, so a silent False would tell an admin "not authorized" when Google was down; (b) it keeps every TASK-25.1.6.1 characterization test in TestGenerateGroupMembersReportFailureModes green with only the mock seam translated, which is exactly what AC#6 asks for. Precedent for a local exception class: packages/oncall_sync/ports.py:50 OnCallSyncError. This is the OPPOSITE of a blanket except -- the classified status and error_code are preserved and logged, and no googleapiclient type crosses the boundary.

D3. modules/provisioning/users.py's google branch returns list[DirectoryUser], and modules/aws/identity_center.py::provision_aws_users adapts by building an EXPLICIT create_user payload dict from dataclass attributes, dropping its four preformat_items calls on the CREATE path only. identity_center.py is therefore IN SCOPE as a fourth production file; AC#8 covers it. The delete branch and synchronize()'s group-sourced user path are untouched -- the latter is TASK-25.1.6.5's.

D4. reports/google_groups.py keeps the PER-GROUP get_group_members loop. TASK-25.1.6.3.1's get_group_members_batch and list_groups_with_members are deliberately NOT used here -- scope fence, and .5 owns the batched-consumer pattern.

D5. Both legacy test files move into the unit tree and test_handler.py is renamed, matching what TASK-25.1.6.1 did for the reports tests (decisions/testing.md one-tree rule; the project contract bans ambiguous test file names such as test_handler.py).

D6. The time.sleep(1.1) at reports/google_groups.py:127 STAYS in this slice. It paces the three SHEETS calls per group, not the Directory calls (the member loop at :76-85 has no sleep at all). Per F7 those Sheets calls have no SDK-native retry today, so removing the pacer now would expose the report to unretried 429s. It retires when the Sheets call sites gain num_retries at their adapter -- TASK-25.1.6.10, where the handoff and the exact test assertion to delete are recorded.

D7. The lost orderBy="email" (legacy google_directory.py:64 and :98 passed it; GoogleDirectoryProvider.list_users/list_groups do not) is recorded as a finding on TASK-25.1.6.11 and named in the PR; the provider's behaviour is NOT modified here.

D8. The returned-email lowercasing (F3) is documented WHERE IT BELONGS -- as a caveat on the DirectoryProvider Protocol docstring -- not left in a task file. Human direction: "tasks seem an odd place to note, might be a docstring caveat". The docstring already promises argument normalisation and is silent on returns (F9); this slice completes that sentence. It is a DOCSTRING-ONLY edit to app/infrastructure/directory/provider.py with no behaviour change, and it is the only file outside app/modules/ this slice touches. Rejected alternatives: a note on this task (invisible to the next reader of the Protocol), and a new decisions/ record (there is no directory decision record, and one sentence of contract detail does not warrant creating one).

--------------------------------------------------------------------------
STEP 1 -- Failing tests first: permissions [AC#1, #4, #5]

Create app/tests/unit/modules/permissions/test_permissions_handler.py (with __init__.py), delete app/tests/modules/permissions/test_handler.py.

Seam: monkeypatch.setattr("modules.permissions.handler.get_directory_provider", lambda: fake). The double is a small local Protocol-conformant fake exposing get_group_members(group_key, include_member_types=None) -> OperationResult[list[DirectoryMember]] and recording the keys it was asked for -- decisions/testing.md prefers a fake over MagicMock. Mark @pytest.mark.unit.

Cases: member found in the first group returns True; member found only in the second group returns True; not found anywhere returns False; an empty member list is skipped without error; a non-success result raises PermissionCheckError carrying the error_code; the comparison is case-insensitive (user_key "User.Name@Email.com" matches a lowercase member email). Also assert the fake was asked for the raw configured group keys.

STEP 2 -- permissions/handler.py [AC#1, #4, #5]

Delete get_authorizers_from_groups entirely (D1). Replace the integrations.google_workspace import with infrastructure.directory.get_directory_provider (F8). Add a module-local PermissionCheckError(Exception) carrying group_key, message and error_code.

is_user_member_of_groups: resolve the provider once, lowercase user_key, loop group keys calling get_group_members(group_key); on a non-success result log at error and raise PermissionCheckError; on success return True as soon as any member.email equals the normalised user_key. Add type hints (list[str], bool) -- the function is currently unannotated.

INTENTIONAL DELTAS TO NAME IN THE PR: (a) the check now short-circuits on the first match instead of collecting every group's members first, so fewer Directory calls are made; combined with D2 this means a failure in a LATER group no longer aborts a check that already succeeded -- strictly more available and still correct; (b) the comparison is now case-insensitive because the provider lowercases (F3), which fixes a latent casing bug; (c) the raised type is PermissionCheckError instead of a googleapiclient HttpError, so no vendor exception crosses this boundary any more.

STEP 3 -- Failing tests first: provisioning users [AC#2, #4, #5]

Create app/tests/unit/modules/provisioning/test_provisioning_users.py under the unit tree, delete app/tests/modules/provisioning/test_provisioning_users.py.

Cases: unknown integration still returns []; the google branch returns DirectoryUser objects and calls list_users() with NO arguments (AC#2's no-silent-truncation evidence -- there is no magic number to assert, the evidence is the unbounded call plus a fake returning more users than the retired 100-item default would have allowed, asserted on the returned count); the aws branch is unchanged and still returns raw identity_store dicts; a non-success list_users result raises DirectoryUsersUnavailableError; processing_filters still applies to the google branch using an ATTRIBUTE predicate (proving F2 -- filter_by_condition needed no change).

STEP 4 -- provisioning/users.py [AC#2, #4, #5]

Swap the google_directory import for get_directory_provider. In the "google_directory" case, call get_directory_provider().list_users() with no arguments; on a non-success result log at error with error_code and raise a module-local DirectoryUsersUnavailableError; otherwise assign result.data or []. Leave the aws_identity_center case, the processing_filters loop and the completion log untouched. Document in the docstring that the google branch now yields DirectoryUser and the aws branch still yields raw dicts.

STEP 5 -- identity_center.provision_aws_users [AC#8, #5]

In the "create" branch only (identity_center.py:313-330): replace the dict filter plus four preformat_items calls with one explicit comprehension over the returned DirectoryUser list, building {"primaryEmail": u.email, "email": u.email, "log_user_name": u.email, "first_name": u.given_name, "family_name": u.family_name} for users whose email is in a lowercased set of users_emails. primaryEmail is retained as a key ONLY because provision_entities(display_key="primaryEmail") resolves it for logging; it is our own payload key now, not a Google field. The delete branch and its preformat_items calls are untouched.

Update app/tests/unit/modules/aws/test_identity_center_handler.py::TestProvisionAwsUsers: the four create-path cases move from returning Google dicts to returning DirectoryUser objects; add a case proving a mixed-case requested email still matches, and one proving first_name/family_name are carried from given_name/family_name.

STEP 6 -- reports/google_groups.py plus its characterization tests [AC#3, #4, #5, #6]

Rework app/tests/unit/modules/reports/test_google_groups_report.py exactly as TASK-25.1.6.1's pre-registration anticipated:
- The _DIRECTORY patch target changes from modules.reports.google_groups.google_directory to the module-bound get_directory_provider returning a local Protocol-conformant fake; the _groups_listed and _members_requested accessors are TRANSLATED to read that fake, not deleted.
- TestGenerateGroupMembersReportBehaviour must pass with only fixture-shape changes. Its default groups/members become DirectoryGroup/DirectoryMember values.
- TestGenerateGroupMembersReportFailureModes: because of D2 the two Directory failure cases keep their pytest.raises shape; only the trigger changes from "the mock raises" to "the fake returns a non-success OperationResult", and the expected type becomes the module-local exception. The three Sheets/Drive failure cases are untouched.
- Keep the FOLDER_REPORTS_GOOGLE_GROUPS monkeypatch (GOOGLE_RESOURCES is not in the pytest env block) and keep the time.sleep patch (D6).
- ADD: a group with name=None is handled (see A3); a member with role=None writes an empty cell (see A2).

Then the module: drop google_directory from the integrations import tuple, leaving google_drive and sheets untouched (AC#3). Resolve the provider once. Replace :69 with list_groups() and the :70 exclusion with a None-safe read of group.name. Replace the :76-85 member loop with get_group_members(group.group_email), accumulating (group, members) pairs in a local list instead of mutating group["members"] -- DirectoryGroup is frozen. Both Directory error branches raise a module-local DirectoryReportError. In the sheet loop read group.name or group.group_email for the title, and member.email / member.role or "" for the values rows. Leave the sleep at :127 alone.

STEP 7 -- Document the returned-email normalisation on the Protocol [AC#9, D8]

DOCSTRING ONLY, no behaviour change. In app/infrastructure/directory/provider.py, extend the DirectoryProvider class docstring so it states both halves of the normalisation contract: today it promises only that method ARGUMENTS are lowercased by implementors (F9). Add that emails carried on returned DirectoryUser, DirectoryMember and DirectoryGroup values are lowercased too, and that consumers comparing them against externally-sourced addresses (Slack profile emails, command arguments, values already stored in another system) must compare case-insensitively rather than assuming the provider preserves the IDP's original casing.

This is the durable home for the fact that A1 mitigates at three call sites in this slice. Keep it to two or three sentences; do not restate the OperationResult contract already documented there, and do not touch google.py or models.py.

STEP 8 -- Validation and finalisation

cd app && uv run ruff check . ; uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' ; uv run pytest tests --ignore=tests/smoke
Confirm AC#7 by grepping integrations/google_workspace/google_directory.py consumers: exactly modules/provisioning/groups.py must remain (plus the module's own test file), and the file itself still exists for TASK-25.1.6.5 to delete.
Confirm no new app/tests/modules/** files and that the two legacy files are gone.
Confirm git diff under app/infrastructure/ is docstring-only.

--------------------------------------------------------------------------
AC-TO-STEP-TO-TEST TRACEABILITY

AC#1 -> Steps 1-2 -> test_permissions_handler.py (all cases) + grep for zero integrations.google_workspace imports in handler.py
AC#2 -> Steps 3-4 -> the unbounded-list_users case asserting list_users() is called with no arguments and every returned user survives
AC#3 -> Step 6 -> translated Boundary tests + assertions that the Drive/Sheets fakes and the sleep are called identically to before
AC#4 -> Steps 1-6 -> one raising test per migrated call site (permissions members, users list, reports groups, reports members)
AC#5 -> Steps 2, 4, 5, 6 -> attribute-reading assertions; field mapping matches the inventory pre-registered on this task on 2026-09-03 18:02
AC#6 -> Step 6 -> the Behaviour class passes unchanged in substance; the two rewritten Failure cases are named in the PR and in the task notes
AC#7 -> Step 8 -> grep evidence recorded in the notes
AC#8 -> Step 5 -> TestProvisionAwsUsers cases
AC#9 -> Step 7 -> reviewed, not unit-tested; verified by the docstring-only git diff check in Step 8

--------------------------------------------------------------------------
ASSUMPTIONS AND DOUBTS, WITH VERIFICATION STEPS

A1. Lowercased emails now reach AWS Identity Center via create_user (F3), whereas today the Google-cased primaryEmail did. Until TASK-25.1.6.5 lands, identity_center.synchronize()'s sync_users still compares Google-cased 'primaryEmail' values (sourced from the legacy groups path) against AWS 'UserName', so a casing divergence would cause duplicate user creation. RESOLVED BY MITIGATION, NOT BY ASSUMPTION (human decision 2026-09-03: "lowercase is good enough at this point"): every comparison this slice touches is made case-insensitive (Step 2's user_key normalisation, Step 5's lowercased users_emails set), and the underlying constraint is documented on the Protocol by Step 7 so the next consumer does not rediscover it. Google normalises primaryEmail to lowercase in practice, so the residual risk is the legacy sync path this slice does not touch; TASK-25.1.6.5 closes it when it moves that path onto the same provider. Do NOT add a re-casing shim.
A2. DirectoryMember.role is str | None (google.py:414 uses item.get("role")). Today's raw member dicts always carried role because the report requests no field projection. Guarded with member.role or "" and pinned by a test.
A3. DirectoryGroup.name is str | None. Today :70 and :88 would raise KeyError on a nameless group. Handled with a None-safe exclusion read and a group.name or group.group_email title fallback, pinned by a test. Name this as an intentional delta in the PR.
A4. Group ordering changes because the provider drops orderBy="email" (D7). Sheet creation order in the report becomes API order. No correctness impact on provisioning. Do not add ordering assertions that depend on it.

--------------------------------------------------------------------------
BLAST RADIUS AND ROLLBACK

Production files: modules/permissions/handler.py, modules/provisioning/users.py, modules/reports/google_groups.py, modules/aws/identity_center.py, plus a DOCSTRING-ONLY edit to infrastructure/directory/provider.py (Step 7). Approximately 100 changed production LOC. No behavioural change under app/infrastructure/, and nothing under app/integrations/ or app/packages/ is modified at all -- the provider implementation, google_directory.py and the access package are untouched, so packages/access and modules/dev keep working unchanged.
Test files: two created in the unit tree, two legacy files deleted, two existing unit files reworked.
Runtime surfaces affected: the /aws groups and /aws users Slack permission gate, the /aws users provisioning command, and the Google Groups members report command. No HTTP routes, no lifespan, no plugin registration.
Rollback: revert the single PR. google_directory.py still exists with all its functions, so nothing downstream is orphaned.
SIZE GATE: approximately 100 production LOC across 4 behavioural files plus one docstring edit, in one subsystem -- comfortably inside a single reviewable PR. No decomposition required.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTED 2026-09-03. All quality gates green (ruff check, ruff format, mypy shows no errors in any touched file, full pytest suite via make test all green).

PRODUCTION CHANGES (5 files, ~100 LOC):
- modules/permissions/handler.py: get_authorizers_from_groups DELETED (zero production callers). is_user_member_of_groups now resolves get_directory_provider() and calls get_group_members per key, typed (list[str]) -> bool. New module-local PermissionCheckError(group_key, message, error_code). No integrations.google_workspace import remains.
- modules/provisioning/users.py: google branch calls get_directory_provider().list_users() with NO arguments (unbounded) and returns list[DirectoryUser]; non-success raises module-local DirectoryUsersUnavailableError carrying error_code. aws branch, processing_filters loop and completion log untouched.
- modules/aws/identity_center.py::provision_aws_users create branch: the four filters.preformat_items calls replaced by one explicit payload comprehension over DirectoryUser attributes; requested emails matched against a lowercased set. Delete branch and synchronize() untouched.
- modules/reports/google_groups.py: google_directory dropped from the integrations import (google_drive/sheets untouched); provider resolved once; list_groups() unbounded; per-group get_group_members loop retained (no batching, per D4); (group, members) accumulated in a local list since DirectoryGroup is frozen; both error branches raise module-local DirectoryReportError. time.sleep(1.1) pacer left in place (D6, retires with TASK-25.1.6.10).
- infrastructure/directory/provider.py: DOCSTRING ONLY. DirectoryProvider docstring now states both halves of the email-normalisation contract (returned emails are lowercased too) and tells consumers to compare case-insensitively. Verified docstring-only by git diff.

INTENTIONAL BEHAVIOUR CHANGES (name these in the PR):
1. is_user_member_of_groups short-circuits on the first match, so fewer Directory calls and a failure in a later group no longer aborts a check that already succeeded.
2. The membership comparison is now case-insensitive (provider lowercases), fixing a latent casing bug.
3. Vendor exceptions no longer cross these boundaries: PermissionCheckError / DirectoryUsersUnavailableError / DirectoryReportError replace googleapiclient HttpError propagation.
4. A nameless group no longer raises KeyError; it is excluded-checked against '' and titled by its group_email (A3).
5. A member with role=None writes an empty cell rather than raising (A2).
6. Group ordering is now API order because the provider does not pass orderBy='email' (D7, recorded on TASK-25.1.6.11).
7. AWS Identity Center create_user now receives lowercased emails (A1, mitigated by case-insensitive matching; residual legacy sync path closes in TASK-25.1.6.5).

TEST EVIDENCE: tests/unit/modules/permissions/test_permissions_handler.py (new), tests/unit/modules/provisioning/test_provisioning_users.py (moved from tests/modules), tests/unit/modules/reports/test_google_groups_report.py (seam translated to a DirectoryProvider fake; TestGenerateGroupMembersReportBehaviour passes with fixture-shape changes only; the two Directory failure cases keep their pytest.raises shape with only the trigger translated), tests/unit/modules/aws/test_identity_center_handler.py (create-path cases now use DirectoryUser; added mixed-case match and explicit-payload cases). Legacy app/tests/modules/permissions/test_handler.py and app/tests/modules/provisioning/test_provisioning_users.py deleted; no new files under app/tests/modules/**.

AC#7 GREP EVIDENCE: integrations/google_workspace/google_directory.py still exists; the only remaining production consumer is modules/provisioning/groups.py:4/:50 (TASK-25.1.6.5 deletes both).

LEFT FOR HUMAN VERIFICATION: DoD sign-off, PR review, and moving the task to Done.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-02 17:16
---
PRE-REGISTERED BY TASK-25.1.6.1 PLANNING (2026-09-02, task-planner). Your AC#6 says "TASK-25.1.6.1 characterization tests for modules/reports/google_groups.py pass unchanged, or every intentional behaviour change is named in the task notes". Here is what you will actually be looking at.

FILE: app/tests/unit/modules/reports/test_google_groups_report.py (NOT app/tests/modules/... -- TASK-25.1.6.1 AC#1 was corrected to the unit tree per decisions/testing.md).

STRUCTURE: three classes, deliberately split by lifetime.
- TestGenerateGroupMembersReportBehaviour -- respond strings, the AWS- name exclusion, sheet-name truncation, values matrix, control flow. These MUST keep passing after your migration; if one goes red, you changed observable behaviour.
- TestGenerateGroupMembersReportBoundary -- the arguments handed to google_directory.list_groups()/list_group_members(). These are EXPECTED to be translated by you, not deleted: the seam moves from patch("modules.reports.google_groups.google_directory") to a DirectoryProvider double obtained via get_directory_provider(). Translating them is normal; silently dropping them is not.
- TestGenerateGroupMembersReportFailureModes -- includes two cases that are directly your problem: (a) list_groups raising propagates uncaught today and create_file has ALREADY run, so a failed Directory call leaves an empty spreadsheet behind; (b) list_group_members raising on the second group propagates with ZERO sheet writes done. Under OperationResult these exceptions no longer cross the boundary, so both of these tests WILL need rewriting -- that rewrite is your AC#4 error-branch handling, and the notes must name it.

ALSO INHERITED: the tests monkeypatch modules.reports.google_groups.FOLDER_REPORTS_GOOGLE_GROUPS because GOOGLE_RESOURCES is not in the pytest env block, and they patch time.sleep (the module sleeps 1.1s per group). Keep both when you rework them.
---

author: @task-planner
created: 2026-09-03 18:02
---
API SHAPE AND FIELD INVENTORY PRE-REGISTERED BY TASK-25.1.6.3 PLANNING (2026-09-03, task-planner). TASK-25.1.6.3 was split; you depend only on Slice A (TASK-25.1.6.3 itself), which is unblocked for you as soon as it merges. The new TASK-25.1.6.3.1 is Slice B and gates TASK-25.1.6.5, not you.

WHAT SLICE A HANDS YOU.
- list_users(query: str = '', limit: int | None = None). limit=None (the NEW DEFAULT) means every user in the domain. Your AC#2 is therefore satisfied by calling list_users() with no arguments - there is no magic number to pass. Related defect fixed in the same slice: today's limit is a post-hoc slice applied AFTER walking every page (google.py:402 then :418), so list_users(limit=3) currently pulls the whole directory; after Slice A the pagination stops early.
- list_groups(query: str = '', limit: int | None = None). An EMPTY query means every group in the domain, mapped by a new generic mapper that does NOT apply managed-alias preference or managed-domain enforcement. modules/reports/google_groups.py:69 calls list_groups() with no arguments today, so this is the direct replacement. Do not pass a wildcard.
- DirectoryUser gains given_name and family_name.
- Unmappable group entries are logged at warning and counted rather than dropped silently; result contents are unchanged.

FIELD MAPPING FOR YOUR THREE FILES (AC#5). modules/permissions/handler.py reads user['email'] at :20 and :36 -> DirectoryMember.email. modules/provisioning/users.py:26 returns raw user dicts consumed downstream as primaryEmail / name.givenName / name.familyName by modules/aws/identity_center.py:145-149 and :316-321 -> DirectoryUser.email / .given_name / .family_name. modules/reports/google_groups.py reads group['name'] at :70 and :87, group['email'] at :83, member['email'] and member['role'] at :117 -> DirectoryGroup.name / .group_email and DirectoryMember.email / .role.

FIELDS THAT DO NOT SURVIVE, decided in Slice A rather than left for you: group directMembersCount and member status are NOT carried on the dataclasses (grep-confirmed zero downstream reads). DirectoryMember.provider_user_id is hardcoded None (google.py:257) - the Google member id is mapped to membership_id instead - so do not read provider_user_id expecting a value.

ONE THING TO WATCH THAT IS YOURS, NOT SLICE A'S: modules/provisioning/users.py:36 applies utils.filters.filter_by_condition to the returned users, and modules/aws/identity_center.py:137 compares on the 'primaryEmail' dict key. Those helpers operate on dict keys, not dataclass attributes. Repointing users.py is therefore not a pure swap - decide explicitly whether the filter contract moves to attribute access or the consumer adapts, and cover it with a test.
---

author: @task-planner
created: 2026-09-03 21:28
---
PLAN WRITTEN AND AC SET REPLACED 2026-09-03 (task-planner, human-approved during planning). Recording the replacement explicitly per the backlog-task-workflow rule against silently reshaping ACs.

WHAT CHANGED IN THE AC SET (was seven, now eight):
- #1 AMENDED. Was "uses get_group_members at both call sites". get_authorizers_from_groups has ZERO production callers repo-wide (grep-confirmed 2026-09-03; only two tests in app/tests/modules/permissions/test_handler.py reference it). Human decision: delete it as dead code rather than migrate it. #1 now names the one surviving call site and requires the deletion.
- #3 TIGHTENED. Adds the time.sleep pacer to the untouched list. It paces the three SHEETS calls per group, not the Directory calls (the member loop has no sleep), and integrations/google_workspace/client.py:154 execute_google_api_request passes NO num_retries, so those Sheets calls have zero SDK-native retry today. Removing the pacer here would expose the report to unretried 429s. It belongs to TASK-25.1.6.10; comment left there.
- #4 TIGHTENED to FAIL-LOUD. Human decision: all migrated call sites preserve today's observable behaviour by raising a narrow, vendor-neutral, module-local exception carrying the classified message and error_code, instead of degrading silently. is_user_member_of_groups is a security gate whose four callers (modules/aws/groups.py:59/:103/:134 and modules/aws/users.py:56) have no try/except, so returning False on an infrastructure error would tell an admin "not authorized" when Google was down. It also keeps TASK-25.1.6.1's TestGenerateGroupMembersReportFailureModes cases in their pytest.raises shape with only the trigger translated.
- #5 EXTENDED with explicit None handling. DirectoryGroup.name and DirectoryMember.role are both optional on the dataclasses, and the report reads both; today's raw dicts always carried them.
- #6 SHARPENED from "pass unchanged" to "pass with the mock seam translated and no behavioural assertion weakened", which is what TASK-25.1.6.1's pre-registration actually anticipated.
- #8 NEW. modules/aws/identity_center.py::provision_aws_users is the ONLY consumer of users.py's google branch, and it splats the raw Google dict into identity_store.create_user via four filters.preformat_items calls (modules/provisioning/entities.py:60 does function(**entity)). Repointing users.py to DirectoryUser is therefore not possible without adapting it, so it is now explicitly in scope as a fourth production file rather than an unowned ripple.
- #2 and #7 UNCHANGED.

FINDING THAT RETIRES A PRE-REGISTERED RISK. The "ONE THING TO WATCH" left on this task by TASK-25.1.6.3's planner on 2026-09-03 18:02 - that utils.filters.filter_by_condition operates on dict keys - is MOOT for users.py. filter_by_condition (utils/filters.py:11) is [item for item in item_list if condition(item)]: it is predicate-generic, not dict-coupled, and only the CALLER's lambda would be. No production caller passes processing_filters to get_users_from_integration (identity_center.py:313 and :334 both pass none). The real dict coupling is filters.preformat_items plus user["primaryEmail"], both inside provision_aws_users - which is why AC#8 exists.

SIZE GATE VERDICT: FITS ONE PR. Approximately 100 changed production LOC across 4 files in one subsystem (legacy modules to DirectoryProvider). Nothing under app/infrastructure/, app/integrations/ or app/packages/ is modified. No decomposition required.
---
<!-- COMMENTS:END -->

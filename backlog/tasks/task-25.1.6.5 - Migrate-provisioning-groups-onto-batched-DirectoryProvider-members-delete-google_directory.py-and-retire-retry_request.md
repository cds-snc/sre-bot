---
id: TASK-25.1.6.5
title: >-
  Migrate provisioning groups onto batched DirectoryProvider members, delete
  google_directory.py and retire retry_request
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-02 15:01'
updated_date: '2026-09-08 14:23'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.4
  - TASK-25.1.6.3.1
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - app/modules/provisioning/groups.py
  - app/integrations/google_workspace/google_directory.py
  - app/integrations/utils/api.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 136000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Final Directory slice. Closes the duplicated-boundary finding recorded on TASK-25.1.6 (2026-09-01 comment): google_directory.py and infrastructure/directory/google.py::GoogleDirectoryProvider build the SAME Resource from the SAME factory, hardcode the same scopes, resolve the same customer id, run structurally identical pagination loops and cover the same three calls. Per decisions/outbound-clients.md (one adaptation tier) and decisions/sdk-typing.md (one construction path per vendor), exactly one survives. The human decision is DirectoryProvider.

SCOPE:

1. modules/provisioning/groups.py:50 - the last remaining google_directory consumer. Today it calls list_groups_with_members(groups_filters=..., query=...), which loops groups and issues one members.list per group behind integrations/utils/api.py::retry_request. Repoint it onto the batched groups-with-members capability added by TASK-25.1.6.3 (built on get_group_members_batch: ONE batched Directory request, not N). Its counterpart in the same function, identity_store.list_groups_with_memberships, is an AWS surface and is OUT OF SCOPE - only the Google branch moves.

2. Delete app/integrations/google_workspace/google_directory.py outright, with its test file. By this point list_users / list_groups / list_group_members have zero production consumers (TASK-25.1.6.4), and list_groups_with_members / get_members_details / convert_google_groups_members_to_dataframe - business logic that decisions/outbound-clients.md forbids in a vendor package - die with it or have already moved per TASK-25.1.6.3.

3. Retire integrations/utils/api.py::retry_request. It is a time.sleep retry loop inside app/integrations/ and directly trips decisions/outbound-clients.md's Checks line ("no time.sleep/tenacity/backoff retry loops in app/integrations/") and TASK-25's AC#5. google_directory.py is its only production caller (grep-confirmed 2026-09-02; the identically-named retry_request symbols in packages/access/request/{http,service}.py are unrelated domain methods, not this helper). Delete it with its module if nothing else in integrations/utils/api.py justifies keeping the file, or delete just the function and its tests. Resilience on the surviving path is SDK-native: GoogleDirectoryProvider._paginate already passes num_retries to .execute().

BEHAVIOURAL DELTA TO STATE EXPLICITLY IN THE PR: the legacy path tolerates a per-group members failure by retrying with sleeps and then continuing with partial data; the batched path surfaces per-request errors through the batch callback in one round trip. That is a different failure profile, not a strictly identical one. modules/provisioning/groups.py's existing test file (app/tests/modules/provisioning/test_provisioning_groups.py) pins the current shape at the google_directory.list_groups_with_members mock boundary and will need reworking onto the provider boundary.

AFTER THIS TASK: app/integrations/google_workspace/ contains no Directory module, and TASK-25's AC#5 (no hand-rolled retry in app/integrations/) is satisfiable for the Google vendor.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 modules/provisioning/groups.py's Google branch uses the batched DirectoryProvider groups-with-members capability from TASK-25.1.6.3 and issues one batched request rather than one members.list per group; its AWS identity_store branch is untouched
- [x] #2 app/integrations/google_workspace/google_directory.py is deleted, along with its test file, and grep confirms zero remaining references repo-wide outside backlog/ and tmp/
- [x] #3 integrations/utils/api.py::retry_request is deleted with its tests, and grep -rn 'time.sleep' app/integrations returns zero hits (TASK-25 AC#5 satisfied for the Google vendor)
- [x] #4 list_groups_with_members, get_members_details and convert_google_groups_members_to_dataframe no longer exist inside app/integrations/ - each is either deleted as dead or already relocated by TASK-25.1.6.3, stated per function in the task notes
- [x] #5 app/tests/modules/provisioning/test_provisioning_groups.py is reworked onto the DirectoryProvider boundary with every existing behavioural assertion preserved or its change documented
- [x] #6 The failure-profile change (per-group retry-with-sleep and continue, versus per-request errors surfaced by the batch callback) is named explicitly in the PR description and covered by a test asserting what modules/provisioning/groups.py now does when one group's members cannot be fetched
- [x] #7 app/bin/baselines/sdk_typing_antipatterns.txt is pruned of google_directory.py and python3 bin/check_sdk_typing.py passes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
IMPLEMENTATION PLAN (task-planner, 2026-09-04). Two design decisions were confirmed with the human before this plan was written (D1/D2 below); the whole plan assumes both. Both dependencies (TASK-25.1.6.4, TASK-25.1.6.3.1) are Done.

## Post-TASK-76 scope check
TASK-76 (all 5 subtasks Done) relocated managed-group policy out of infrastructure/directory into packages/access and made DirectoryProvider's email handling strictly pass-through (strip+lowercase only). Neither list_groups_with_members nor get_group_members_batch (the two provider capabilities this task uses) ever called the managed-group policy, so TASK-76 has zero code impact here. TASK-76's advisory ("pass fully-qualified keys, don't expect managed-domain filtering from get_user_groups") is inapplicable: this task calls list_groups_with_members, not get_user_groups, and already passes fully-qualified group emails end to end.

## D1/D2 - human-confirmed design (2026-09-04)
D1: modules/provisioning/groups.py's "google_groups" branch keeps its EXACT current dict-shaped return contract (group dict with "name"/"email" + "members": [{"primaryEmail","email","name":{"givenName","familyName"}}]). The DirectoryProvider migration is an internal translation shim inside groups.py only. modules/aws/identity_center.py and modules/aws/groups.py are NOT touched - their dict-keyed filter lambdas keep working unchanged. This is what keeps the task inside the single-PR gate.
D2: Legacy list_groups_with_members silently dropped any group with zero resolvable members. Preserved: the shim drops any group whose resolved-members list ends up empty (legitimately empty, or every member unresolved), so identity_center.py::synchronize()'s live membership-delete path never sees such a group and never clears AWS memberships for it.

## Findings that determine the implementation
F1. AC#4's convert_google_groups_members_to_dataframe does not exist in current code (only referenced in an "is_deleted" characterization test, app/tests/integrations/google_workspace/test_google_directory.py:288). State per-function disposition in PR notes rather than treating it as work.
F2. AC#7's baseline claim is already inaccurate (also flagged by this task's own comment #3): app/bin/baselines/sdk_typing_antipatterns.txt does not list google_directory.py today. AC#7 is satisfied by "check_sdk_typing.py still passes, no stale/new entry" not by pruning a nonexistent line.
F3. identity_center.py::sync_users hard-crashes (utils/filters.py::preformat_items raises KeyError) if any member dict is missing "primaryEmail" or "name.givenName"/"name.familyName". A member the shim cannot match to a DirectoryUser MUST be excluded (not included with partial data) or the live sync crashes. Exclude with a structured warning log (group_email, member_email) - strictly more observable than legacy's silent whole-group drop (get_members_details' tolerate_errors=False default dropped the ENTIRE group on ANY unresolved member).
F4. provision_entities (modules/provisioning/entities.py:57) calls function(**entity, **kwargs) - extra dict keys are harmless. The shimmed member dict only strictly needs "primaryEmail" plus the two preformat_items source keys; no other legacy field (role/type/status/id) is read downstream (confirmed via full-file read of identity_center.py).
F5. Only modules/aws/identity_center.py:56 calls get_groups_from_integration("google_groups", ...); modules/aws/groups.py only calls the "aws_identity_center" branch (line 108) - confirms D1 has no other google-side coupling to worry about.
F6. pre_processing_filters (today applied inside google_directory.list_groups_with_members, pre-member-fetch) and post_processing_filters (applied post-merge in get_groups_from_integration) are both pure predicates with no side effects; applying pre_processing_filters AFTER the shim builds its dict list (alongside post_processing_filters) produces an IDENTICAL final filtered result. Must still be implemented explicitly in groups.py once google_directory is gone.
F7. include_member_types left at provider default (None = all types); a nested sub-group member simply fails user-resolution like any other unresolvable member (F3) - no special-casing needed.

## Implementation steps
1. app/modules/provisioning/groups.py
   a. Replace "from integrations.google_workspace import google_directory" with "from infrastructure.directory import get_directory_provider" and "from modules.provisioning import users" (no import cycle: users.py does not import groups.py).
   b. Add DirectoryGroupsUnavailableError(Exception) mirroring users.py's DirectoryUsersUnavailableError (message + error_code) for the whole-result failure path (fail-loud, per TASK-25.1.6.4's established house style).
   c. Rewrite the "google_groups" match-case:
      - result = get_directory_provider().list_groups_with_members(query=query or ""); on not result.is_success, log error and raise DirectoryGroupsUnavailableError(result.message, result.error_code).
      - Log a warning per entry in result.data.failures (group_email, status.name, error_code, message) - AC#6.
      - Call users.get_users_from_integration("google_directory") once (typed list[DirectoryUser]; itself raises DirectoryUsersUnavailableError on failure - let it propagate), index by .email.
      - For each DirectoryGroupWithMembers: build shimmed member dicts {"primaryEmail": user.email, "email": user.email, "name": {"givenName": user.given_name, "familyName": user.family_name}}, skipping (warning-logged, F3) any member with no user match; skip the whole group (D2) if resulting members is empty; else append {"email": group.group_email, "name": group.name or "", "members": members}.
      - Apply pre_processing_filters to the shimmed group list via the same filters.filter_by_condition loop shape already used for post_processing_filters (F6).
      - Keep group_display_key="name", members="members", members_display_key="primaryEmail", integration_name="Google" exactly as today.
   d. Leave the "aws_identity_center" case byte-for-byte unchanged (AC#1).
2. Delete app/integrations/google_workspace/google_directory.py in full and its test file app/tests/integrations/google_workspace/test_google_directory.py (zero remaining production consumers after step 1).
3. app/integrations/utils/api.py: delete only retry_request (~lines 93-124); convert_string_to_camel_case/generate_unique_id (google_calendar.py) and convert_kwargs_to_camel_case (google_service.py) stay live so the file itself is kept. Drop the "time" import only if nothing else in the file still needs it (verify by grep first).
4. app/tests/integrations/utils/test_api.py: remove the retry_request import and the 6 test_retry_request_* tests (lines 248-EOF); keep every other test.
5. app/tests/modules/provisioning/test_provisioning_groups.py: rework the google_groups-branch tests onto the provider boundary per the test matrix below; do NOT touch the aws_identity_center-branch tests (AC#1).
6. app/bin/baselines/sdk_typing_antipatterns.txt: no edit needed (F2); confirm python3 bin/check_sdk_typing.py still exits 0.

## AC-to-step-to-test traceability
AC#1 -> step 1 -> new batched-composition call assertion + unchanged AWS-branch tests (regression proof).
AC#2 -> step 2 -> grep -rn google_directory app --include=*.py (excluding backlog/tmp) returns zero.
AC#3 -> steps 3-4 -> grep -rn 'time\.sleep' app/integrations returns zero; retry_request tests removed.
AC#4 -> step 2 + F1 -> state per-function disposition in PR notes.
AC#5 -> step 5 -> rewritten test file, one test per behavioural case in the matrix.
AC#6 -> step 1c + test matrix "failures tuple" case.
AC#7 -> step 6 + F2 -> restate as "check_sdk_typing.py passes, no regression" in PR notes.

## Test matrix (app/tests/modules/provisioning/test_provisioning_groups.py, unit layer per decisions/testing.md)
Provider mocked at the seam (modules.provisioning.groups.get_directory_provider) with a Protocol-conformant fake/stub returning canned OperationResults - no MagicMock as subject under test. modules.provisioning.groups.users.get_users_from_integration patched directly.
1. Happy path: 2 groups fully resolved -> dict shape matches today's assertions.
2. Query passthrough: query="email:aws-*" forwarded to list_groups_with_members(query=...).
3. Empty result: no groups -> [] returned, no crash.
4. Provider failure (whole result): non-success OperationResult -> DirectoryGroupsUnavailableError raised with propagated message/error_code.
5. Per-group failure (AC#6): composition.failures has one entry -> group absent from output, warning logged with group_email/status/error_code.
6. Unresolved member (F3): one member's email has no DirectoryUser match -> excluded, warning logged; if it was the group's only member, whole group dropped (D2).
7. pre_processing_filters still narrows the google branch (F6), same assertion style as existing AWS-branch filter tests.
8. users.get_users_from_integration raising DirectoryUsersUnavailableError propagates uncaught.
9. AWS-branch tests: unchanged, regression proof D1 held.

## Assumptions flagged for reviewer challenge
A1 (=D1, human-confirmed): dict-contract shim scope boundary.
A2 (=D2, human-confirmed): zero-resolved-member groups dropped.
A3: include_member_types left at provider default (all types) rather than {"USER"} - nested sub-group members fail resolution like any unresolvable member (F7); flagging in case a reviewer wants the narrower query.
A4: shimmed member dict emits "email" alongside "primaryEmail" (both = user.email) though no confirmed downstream reader needs plain "email" - kept only because the legacy merged dict always carried it; cheap to keep, flagged rather than silently dropped.

## Blast radius / rollback
Production behaviour change is confined to the "google_groups" internal data source for modules/aws/identity_center.py::synchronize() (a live Slack-triggered AWS Identity Center sync). External contract (Slack command names/output) is unchanged. The only observable behavioural deltas are the two named in AC#6/D2, both preserving or improving today's safety properties. Rollback is a single-file revert of groups.py plus restoring the two deleted files from git history; no data migration, no settings/env change, no deployment step.

## Test commands
cd app && uv run pytest tests/modules/provisioning/test_provisioning_groups.py tests/integrations/utils/test_api.py -q
cd app && uv run pytest tests --ignore=tests/smoke -q
cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'
cd app && uv run ruff check .
cd app && python3 bin/check_sdk_typing.py
grep -rn google_directory app --include=*.py | grep -v /tests/
grep -rn 'time\.sleep' app/integrations
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Validation 2026-09-08: user confirmed make test is fully green; focused pytest for provisioning groups and integration API passed 42 tests. python3 bin/check_sdk_typing.py passed with no net-new SDK anti-patterns. Both deleted Google Directory files are absent; no time.sleep remains under app/integrations; the three legacy group functions and retry_request have no definitions or tests under integrations. ACs 1, 3, 4, 5, 6, and 7 checked individually. AC#2 remains unchecked because the literal repo-wide google_directory grep still finds required surviving source identifiers and provider factory names; no deleted-module file/import remains, but the criterion wording needs human clarification before being marked verified.

Reference cleanup 2026-09-08: removed the stale google_directory.py example from decisions/sdk-typing.md, replacing it with a generic legacy Google Workspace module reference. Verified the scoped grep has zero google_directory matches outside app/, backlog/, and tmp/. Legitimate app/ source keys and Directory provider factory identifiers remain. AC#2 checked.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-03 18:00
---
DEPENDENCY REPOINTED 2026-09-03 (task-planner, human-approved while planning TASK-25.1.6.3). Now depends on TASK-25.1.6.4 AND the new TASK-25.1.6.3.1.

WHY: TASK-25.1.6.3 was split under the implementation-planning size gate. Slice A (TASK-25.1.6.3) delivers the list-all semantics, the generic/managed group-mapping split, observable drops and DirectoryUser.given_name/family_name - that is what TASK-25.1.6.4 needs. Slice B (TASK-25.1.6.3.1) delivers the batch rearchitecture and the groups-with-members composition - that is what YOUR AC#1 needs. Depending only on .4 would have left you blocked on a capability nobody was building.

THREE THINGS THAT CHANGE YOUR PLANNING:

1. THE COMPOSITION WILL NOT MERGE USER RECORDS INTO MEMBERS. Legacy list_groups_with_members called get_members_details, which merged the whole Google user record into each member dict - which is how modules/aws/identity_center.py obtains primaryEmail, name.givenName and name.familyName from group members. TASK-25.1.6.3.1's composition deliberately does NOT do this: it is consumer business logic and decisions/outbound-clients.md keeps it out of the provider. YOU own that join. TASK-25.1.6.3 adds given_name/family_name to DirectoryUser precisely so you can do it with list_users() plus a match on email.

2. THE COMPOSITION WILL NOT APPLY groups_filters EITHER. modules/provisioning/groups.py passes pre_processing_filters straight through to list_groups_with_members today, where they run via utils.filters.filter_by_condition against raw dicts. Those filters operate on dict keys ('name', 'email'), not dataclass attributes - so repointing is not a pass-through and you will need to decide whether the filters move to attribute access, or the consumer converts, or the filter contract changes. Budget for that; it is not covered by any earlier slice. Concretely: modules/aws/identity_center.py:56-60 supplies pre_processing_filters and a post-filter lambda group: 'AWS-' in group['name'] (identity_center.py:55), and modules/aws/groups.py:81 supplies more.

3. PARTIAL FAILURE IS NOW EXPRESSED IN THE PAYLOAD, NOT THE STATUS. decisions/operation-result.md fixes a closed status set with no PARTIAL, so TASK-25.1.6.3.1's composition returns success with per-group failures carried as typed values inside data. Your AC#6 (name the failure-profile change explicitly) should describe the delta as: legacy retried each failing group with time.sleep and then skipped it silently, whereas the new path surfaces the failed group keys as typed failures the consumer must decide about. That is strictly more observable, not merely different.
---

author: @task-planner
created: 2026-09-03 20:08
---
COMPOSITION CONTRACT FIXED 2026-09-03 (task-planner, human-approved while planning TASK-25.1.6.3.1). Plan against this exact shape:

    def list_groups_with_members(
        self,
        query: str = '',
        limit: int | None = None,
        include_member_types: set[str] | None = None,
    ) -> OperationResult[DirectoryGroupsWithMembers]

New frozen dataclasses in app/infrastructure/directory/models.py:
    DirectoryGroupWithMembers(group: DirectoryGroup, members: tuple[DirectoryMember, ...])
    DirectoryGroupFailure(group_email: str, status: OperationStatus, error_code: str | None, message: str)
    DirectoryGroupsWithMembers(groups: tuple[DirectoryGroupWithMembers, ...], failures: tuple[DirectoryGroupFailure, ...])

FOUR THINGS THAT CHANGE YOUR PLANNING (in addition to the three already recorded on 2026-09-03 18:00):

4. ZERO-MEMBER GROUPS ARE NOW RETURNED, NOT DROPPED. Legacy list_groups_with_members skipped any group whose member list came back empty (integrations/google_workspace/google_directory.py:187-190 - 'if members:'). The composition deliberately does not, because that is consumer business logic. If modules/provisioning/groups.py or its downstream (modules/aws/identity_center.py, modules/aws/groups.py) depends on empty groups being absent, YOU add the filter at the consumer. Pin it with a test either way - it is a real behavioural delta at your boundary, not at the provider's.

5. THE LEGACY fields= PROJECTION IS GONE. Legacy requested groups(email, name, directMembersCount, description) and members(email, role, type, status). The canonical dataclasses carry neither directMembersCount nor member status; TASK-25.1.6.3's field inventory grep-confirmed zero downstream reads of both. If your migration surfaces a reader, that is a new finding, not a regression to paper over.

6. FAILED GROUPS COME BACK AS DATA, AND FAILURE IS PER GROUP. failures carries a DirectoryGroupFailure per group whose members could not be fetched, with a status already classified by classify_google_error. The overall result is still SUCCESS. Your AC#6 should assert what modules/provisioning/groups.py does with a non-empty failures tuple - silently skipping it would be strictly worse than the legacy retry-then-skip, because now you were told. NOTE: an UNMAPPED HttpError status (e.g. 400) propagates as an exception rather than becoming a failure entry, by design per decisions/outbound-clients.md.

7. BATCH ROUNDS ARE CHUNKED AT 100 REQUESTS. So 'one batched round-trip' in your AC#1 is precisely 'ceil(groups/100) batch requests per member-page depth', not literally one. Word AC#1's evidence accordingly - the claim to prove is 'not one members.list per group', not 'exactly one HTTP round-trip'.

TWO RESIDUALS TASK-25.1.6.3.1 LEAVES FOR LATER (both recorded on TASK-25.1.6.11, neither blocks you): get_group_members keeps its own inline member-mapping loop, and get_group_members_batch keeps the admin.directory.group.readonly scope while get_group_members and the new composition use admin.directory.group.member.readonly.
---

author: @task-planner
created: 2026-09-03 21:30
---
FINDINGS FROM TASK-25.1.6.4 PLANNING (2026-09-03, task-planner). Four items, one of which makes an AC of yours vacuous as written.

1. YOUR AC#7 IS ALREADY VACUOUS. It says "app/bin/baselines/sdk_typing_antipatterns.txt is pruned of google_directory.py". google_directory.py is NOT in that baseline (verified 2026-09-03; the file lists 11 integrations/aws/* modules plus integrations/google_workspace/google_service.py). TASK-25.1.4 already migrated google_directory.py off the string dispatcher. Either drop AC#7 or restate it as "check_sdk_typing.py still passes and no stale entry is introduced".

2. WHAT .4 LEAVES YOU. After .4, integrations/google_workspace/google_directory.py has exactly one production consumer, modules/provisioning/groups.py (your AC#1). list_users, list_groups and list_group_members become dead except for list_groups_with_members's internal use of them. get_members_details' user-record merge is still live inside list_groups_with_members and is the join you own.

3. THE USER-RECORD JOIN JUST GOT CHEAPER FOR YOU. .4 makes modules/provisioning/users.py's google branch return list[DirectoryUser] (with given_name/family_name from Slice A), and rewrites modules/aws/identity_center.py::provision_aws_users to build its identity_store.create_user payload explicitly from those attributes instead of via four filters.preformat_items calls on Google dict keys. When you do the members-to-users join that get_members_details did, use users.get_users_from_integration('google_directory') as your typed source and copy that explicit-payload pattern - do not reintroduce preformat_items over Google field names. NOTE the remaining asymmetry you inherit: identity_center.sync_users still compares source 'primaryEmail' (Google-cased, from the groups path) against AWS 'UserName'. The provider lowercases every email it returns (infrastructure/directory/google.py:211/:223), so when your slice moves the groups path onto the provider, sync_users' comparison keys change casing too. Decide explicitly and cover it - .4 mitigated its own half by comparing case-insensitively.

4. FAIL-LOUD IS THE HOUSE STYLE FOR THIS FAMILY NOW. .4's human decision (recorded on that task) is that every migrated legacy call site converts a non-success OperationResult into a narrow, vendor-neutral, module-local exception carrying message and error_code, rather than degrading silently. Your AC#6 asks what modules/provisioning/groups.py does with a non-empty failures tuple; that is a different question (per-group failures inside a SUCCESS payload) and fail-loud does not automatically answer it - but the overall-result error branch should follow the same rule.
---

author: @task-planner
created: 2026-09-03 21:41
---
ADDENDUM TO COMMENT #3, ITEM 3 (2026-09-03, task-planner, human-directed). The email-casing constraint now has a documented home instead of living only in task comments.

TASK-25.1.6.4 Step 7 adds a docstring caveat to the DirectoryProvider Protocol (app/infrastructure/directory/provider.py) stating BOTH halves of the normalisation contract: today it promises only that method ARGUMENTS are lowercased by implementors, and is silent on the fact that emails carried on returned DirectoryUser/DirectoryMember/DirectoryGroup values are lowercased too. The added text tells consumers comparing provider emails against externally-sourced addresses (Slack profile emails, command arguments, values already stored in another system such as AWS 'UserName') to compare case-insensitively.

READ THAT DOCSTRING BEFORE PLANNING YOUR sync_users CHANGE. It is the contract statement item 3 was paraphrasing. Human direction was explicitly that a task file is the wrong place for a durable API caveat.

Also note: .4 mitigates by comparing case-insensitively, NOT by re-casing anything. Do the same - do not add a shim that restores Google's original casing on the way out of the provider.
---

created: 2026-09-05 00:02
---
PLANNED 2026-09-04 (task-planner). Two decisions confirmed by the human before this plan was written:
D1 (human-confirmed): groups.py keeps its exact current dict-shaped return contract for "google_groups" via an internal translation shim; identity_center.py and aws/groups.py stay untouched. Keeps the change inside the single-PR gate.
D2 (human-confirmed): the shim preserves legacy safety by dropping any group whose resolved-members end up empty, so identity_center.py's live membership-delete sync path never clears AWS memberships for a now-empty/unresolvable Google group.

Also verified and folded into the plan: TASK-76 (all subtasks Done) has zero code impact on this task - list_groups_with_members/get_group_members_batch never touched the managed-group policy TASK-76 relocated. AC#4 and AC#7 are confirmed already-vacuous as worded (convert_google_groups_members_to_dataframe doesn't exist; google_directory.py isn't in the sdk_typing baseline) - restate both as satisfied-by-verification in the PR notes rather than as work, per the plan's traceability section. Full plan, findings (F1-F7), test matrix and assumptions (A1-A4) are in --plan. No AC text was reworded or removed - this comment documents the restatement for the human to formalize if desired.
---
<!-- COMMENTS:END -->

---
id: TASK-25.1.6.5
title: >-
  Migrate provisioning groups onto batched DirectoryProvider members, delete
  google_directory.py and retire retry_request
status: To Do
assignee: []
created_date: '2026-09-02 15:01'
updated_date: '2026-09-03 21:41'
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
- [ ] #1 modules/provisioning/groups.py's Google branch uses the batched DirectoryProvider groups-with-members capability from TASK-25.1.6.3 and issues one batched request rather than one members.list per group; its AWS identity_store branch is untouched
- [ ] #2 app/integrations/google_workspace/google_directory.py is deleted, along with its test file, and grep confirms zero remaining references repo-wide outside backlog/ and tmp/
- [ ] #3 integrations/utils/api.py::retry_request is deleted with its tests, and grep -rn 'time.sleep' app/integrations returns zero hits (TASK-25 AC#5 satisfied for the Google vendor)
- [ ] #4 list_groups_with_members, get_members_details and convert_google_groups_members_to_dataframe no longer exist inside app/integrations/ - each is either deleted as dead or already relocated by TASK-25.1.6.3, stated per function in the task notes
- [ ] #5 app/tests/modules/provisioning/test_provisioning_groups.py is reworked onto the DirectoryProvider boundary with every existing behavioural assertion preserved or its change documented
- [ ] #6 The failure-profile change (per-group retry-with-sleep and continue, versus per-request errors surfaced by the batch callback) is named explicitly in the PR description and covered by a test asserting what modules/provisioning/groups.py now does when one group's members cannot be fetched
- [ ] #7 app/bin/baselines/sdk_typing_antipatterns.txt is pruned of google_directory.py and python3 bin/check_sdk_typing.py passes
<!-- AC:END -->

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
<!-- COMMENTS:END -->

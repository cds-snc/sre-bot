---
id: TASK-25.1.6.5
title: >-
  Migrate provisioning groups onto batched DirectoryProvider members, delete
  google_directory.py and retire retry_request
status: To Do
assignee: []
created_date: '2026-09-02 15:01'
labels:
  - clients
  - phase-3
milestone: m-3
dependencies:
  - TASK-25.1.6.4
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

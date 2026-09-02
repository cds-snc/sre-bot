---
id: TASK-25.1.6.3
title: >-
  Close the DirectoryProvider capability gaps that block the legacy Directory
  consumers
status: To Do
assignee: []
created_date: '2026-09-02 15:00'
labels:
  - clients
  - phase-3
  - architecture
milestone: m-3
dependencies:
  - TASK-25.1.6.1
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/layers.md
  - app/infrastructure/directory/provider.py
  - app/infrastructure/directory/google.py
  - app/integrations/google_workspace/google_directory.py
parent_task_id: TASK-25.1.6
priority: high
ordinal: 134000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
DECISION RECORDED (2026-09-02, human-directed): infrastructure/directory/{provider,google,factory}.py::DirectoryProvider / GoogleDirectoryProvider IS THE WAY FORWARD. It survives; app/integrations/google_workspace/google_directory.py is deleted; the four legacy app/modules/* consumers move onto the DirectoryProvider Protocol. This settles TASK-25.1.6's AC#5 for the Directory surface - no further "which side wins" analysis is needed, only migration.

This first slice is capability parity ONLY. No consumer moves here. It exists because a straight repoint would silently change behaviour: the Protocol as written today cannot express what two of the four legacy call sites need.

VERIFIED GAPS (read against app/infrastructure/directory/google.py, 2026-09-02):

1. list_users truncation. Legacy google_directory.list_users() paginates to exhaustion (maxResults=_USERS_PAGE_SIZE, orderBy="email", no cap) and returns every user in the domain - which is what modules/provisioning/users.py relies on for a full-directory sync. DirectoryProvider.list_users(query="", limit=100) defaults to 100 AND hard-truncates twice (maxResults=limit on the request, then result.data[:limit]). Repointing provisioning/users.py at it as-is would silently sync only the first 100 users. Decide and implement the unbounded/streaming semantics (an explicit "all" sentinel, a large explicit limit, or a separate iterate-users method) - do not leave the caller to pass a magic number.

2. list_groups requires a query and rewrites bare strings. Legacy google_directory.list_groups() takes NO argument and lists every group. DirectoryProvider.list_groups(query: str) is required-argument, translates a bare string into email:{query}* and, when _managed_group_query_prefix matches, switches to an unfiltered list plus a client-side managed-prefix filter. modules/reports/google_groups.py calls list_groups() with no arguments and expects all groups. Give the Protocol an unambiguous way to express "all groups" without going through the managed-prefix path.

3. Silent group dropping. _build_directory_group can return None and list_groups then omits that group from the result with no error. The legacy path returned the raw dict regardless. Decide whether that is acceptable for a reporting consumer that expects a complete list, and make it observable if it stays.

4. No groups-with-members composition. Legacy list_groups_with_members(groups_filters, query) loops groups and calls list_group_members once per group behind integrations/utils/api.py::retry_request (a time.sleep loop that trips decisions/outbound-clients.md's Checks line). GoogleDirectoryProvider.get_group_members_batch already does the same job in ONE batched Directory request via client.execute_batch_request - the legacy path is not merely duplicated, it is the inferior of the two. A groups-with-members composition needs to exist on the target side, built on get_group_members_batch, and it must live OUTSIDE app/integrations/ (it is business logic; decisions/outbound-clients.md forbids it in a vendor package).

SCOPE: extend DirectoryProvider (and GoogleDirectoryProvider, and any other implementor/fake) to close gaps 1-4, with tests, and nothing else. The consumers move in TASK-25.1.6.4 and TASK-25.1.6.5.

NOTE ON DATA SHAPE: the legacy functions return raw list[dict]; the provider returns DirectoryUser/DirectoryGroup/DirectoryMember frozen dataclasses. That translation is the point (decisions/sdk-typing.md item 3), not an obstacle - but the consuming slices will need field-by-field mapping, so record any legacy field the dataclasses do not currently carry as part of this slice's output rather than discovering it mid-migration.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 DirectoryProvider can express 'every user in the domain' without a caller-supplied magic limit, GoogleDirectoryProvider implements it by paginating to exhaustion, and a test proves a >limit-page result set is returned in full
- [ ] #2 DirectoryProvider can express 'every group in the domain' without a query and without routing through the managed-group-prefix path; a test proves it against a multi-page groups payload
- [ ] #3 The silent-drop behaviour of _build_directory_group returning None in list_groups is either removed or made observable (logged/counted/returned as an error), with a test covering an unmappable group entry
- [ ] #4 A groups-with-members composition exists outside app/integrations/, is built on get_group_members_batch (one batched request, not one request per group), returns typed dataclasses, and has tests covering multi-group success, a per-group failure inside the batch, and an empty group list
- [ ] #5 Any legacy google_directory.py response field that the DirectoryUser/DirectoryGroup/DirectoryMember dataclasses cannot currently carry is enumerated in the task notes, so TASK-25.1.6.4/.5 do not discover it mid-migration
- [ ] #6 No consumer is repointed in this task and integrations/google_workspace/google_directory.py is not modified (git diff touches app/infrastructure/directory/** and its tests only)
<!-- AC:END -->

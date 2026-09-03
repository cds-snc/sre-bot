---
id: TASK-25.1.6.3.1
title: >-
  Rearchitect Directory batch orchestration into the provider and add a
  paginated groups-with-members composition
status: To Do
assignee: []
created_date: '2026-09-03 17:57'
labels:
  - architecture
milestone: m-3
dependencies:
  - TASK-25.1.6.3
references:
  - decisions/outbound-clients.md
  - decisions/sdk-typing.md
  - decisions/operation-result.md
  - decisions/testing.md
  - app/infrastructure/directory/provider.py
  - app/infrastructure/directory/google.py
  - app/integrations/google_workspace/client.py
parent_task_id: TASK-25.1.6.3
priority: high
ordinal: 134500
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
SLICE B of the DirectoryProvider capability-parity work, split out of TASK-25.1.6.3 on 2026-09-03 (task-planner, human-approved) under the implementation-planning size gate. Slice A (TASK-25.1.6.3) owns list-all semantics, the generic/managed group-mapping split, observable drops and the DirectoryUser name fields; it unblocks TASK-25.1.6.4 on its own. This slice owns the batch surface and the composition, which only TASK-25.1.6.5 needs.

WHY SPLIT: Slice A is a mapping/pagination change reviewed for completeness; this slice is a behavioural rearchitecture of the batch failure profile reviewed for correctness. Gate trigger #3 (mixing mechanical refactor with behaviour change) applies.

THREE VERIFIED FACTS ESTABLISHED WHILE PLANNING TASK-25.1.6.3 (2026-09-03, read against the code and the installed googleapiclient-stubs):

1. integrations/google_workspace/client.py::execute_batch_request returns OperationResult from inside a vendor package, which decisions/outbound-clients.md forbids (clients raise; the adapter classifies). GoogleDirectoryProvider is its ONLY caller repo-wide (grep-confirmed: google.py:17 import, google.py:525 call, client.py:170 definition; zero others).

2. get_group_members_batch (google.py:499-566) does NOT paginate. It issues one members.list(groupKey=key) per group inside the batch and reads group_response.get('members', []), ignoring nextPageToken. Any group with more members than the Admin SDK page default is SILENTLY TRUNCATED. The legacy integrations/google_workspace/google_directory.py path this work replaces paginated members per group, so the batched path is not parity until this is fixed. This defect also affects the existing caller packages/access/sync/desired_state.py:160 today.

3. decisions/operation-result.md fixes a CLOSED status set (SUCCESS, NOT_FOUND, TRANSIENT_ERROR, PERMANENT_ERROR, UNAUTHORIZED). There is no PARTIAL. A partial batch outcome must therefore be expressed in the typed data payload, never as a new status. Adding a status would require amending that decision record.

SCOPE.

a) Move the batch orchestration OUT of execute_batch_request and INTO GoogleDirectoryProvider as a private helper (the provider is the adapter, and decisions/outbound-clients.md says the adapter is the boundary). The helper runs one batch round via service.new_batch_http_request(callback=...) and returns per-key raw responses PLUS per-key exceptions, so callers can decide their own failure policy. googleapiclient-stubs types new_batch_http_request, BatchHttpRequest.add(request, request_id=...) and the (request_id, response, HttpError | None) callback, so no Any-laundering is needed.

b) Paginate across batch rounds: after each round, re-batch only the groups whose response carried a nextPageToken, until none remain. This closes fact 2.

c) get_group_members_batch KEEPS its current signature and its current all-or-nothing error contract (human decision, 2026-09-03). It is rebuilt on the new helper and gains ONLY the pagination fix, which can only ever return MORE members. packages/access/sync/desired_state.py must not be touched by this task - changing that contract would pull a second subsystem into the PR.

d) Add the groups-with-members composition to DirectoryProvider and GoogleDirectoryProvider, built on the paginated batch helper (ONE batched round-trip per page depth, not one request per group). It returns typed frozen dataclasses and carries per-group failures inside the success payload, per fact 3. It composes Slice A's list_groups(query, limit) with the batch helper.

e) The composition contains NO feature-specific logic: no groups_filters, no user-record merging (the legacy get_members_details behaviour), no dataframe conversion. Those are consumer business logic and stay with the consumer in TASK-25.1.6.5. Slice A adds given_name/family_name to DirectoryUser so that consumer can do the member-to-user join itself.

AFTER THIS TASK: execute_batch_request has zero consumers and TASK-25.1.6.11 deletes it (a comment was left on that task).

OUT OF SCOPE: repointing any consumer; modifying integrations/google_workspace/**; modifying packages/access/**.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 GoogleDirectoryProvider performs its own batch orchestration via service.new_batch_http_request and no longer imports or calls integrations.google_workspace.client.execute_batch_request; the helper surfaces per-key responses and per-key exceptions rather than collapsing them
- [ ] #2 get_group_members_batch paginates across batch rounds: a test with a group whose first batched response carries a nextPageToken proves every page is returned, and a test proves only the unfinished groups are re-batched
- [ ] #3 get_group_members_batch keeps its existing signature and all-or-nothing error contract; packages/access/** is not modified and its existing tests pass unchanged
- [ ] #4 A groups-with-members composition exists on DirectoryProvider and GoogleDirectoryProvider, is built on the batched helper (one batched round-trip per page depth, not one request per group), and returns typed frozen dataclasses
- [ ] #5 Per-group failures are carried inside the composition's success payload as typed values with a classified status and error_code - no new OperationStatus member is introduced (decisions/operation-result.md status set is closed)
- [ ] #6 Composition tests cover: multi-group success, a per-group failure inside the batch, a group requiring a second page, and an empty group list
- [ ] #7 The composition contains no consumer business logic - no groups_filters, no user-record merging, no dataframe conversion - and git diff touches app/infrastructure/directory/** and its tests only
<!-- AC:END -->

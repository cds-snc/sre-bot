---
id: TASK-25.1.6.3.1
title: >-
  Rearchitect Directory batch orchestration into the provider and add a
  paginated groups-with-members composition
status: To Do
assignee: []
created_date: '2026-09-03 17:57'
updated_date: '2026-09-03 20:09'
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
- [ ] #3 get_group_members_batch keeps its existing signature and its all-or-nothing error contract; its failure status is now classified by classify_google_error rather than the blanket PERMANENT_ERROR/BATCH_ERRORS the vendor helper hardcoded; packages/access/** is not modified and its existing tests pass unchanged
- [ ] #4 A groups-with-members composition exists on DirectoryProvider and GoogleDirectoryProvider, is built on the batched helper (one batched round-trip per chunk of at most _BATCH_MAX_REQUESTS groups per page depth, not one request per group), and returns typed frozen dataclasses
- [ ] #5 Per-group failures are carried inside the composition's success payload as typed values with a classified status and error_code - no new OperationStatus member is introduced (decisions/operation-result.md status set is closed)
- [ ] #6 Composition tests cover: multi-group success, a per-group failure inside the batch, a group requiring a second page, an empty group list, and a group set spanning more than one batch chunk
- [ ] #7 The composition contains no consumer business logic - no groups_filters, no user-record merging, no dataframe conversion, and zero-member groups are returned rather than dropped - and git diff touches app/infrastructure/directory/** and its tests only
- [ ] #8 Batch rounds are chunked at _BATCH_MAX_REQUESTS=100 so a group set larger than googleapiclient's MAX_BATCH_LIMIT never raises the unclassifiable BatchError; a test with more than one chunk's worth of groups proves multiple batch requests are issued and all results merged
- [ ] #9 Batched members.list requests pass maxResults=_MEMBERS_PAGE_SIZE (200), matching the legacy google_directory.py page size
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
GROUNDING (read 2026-09-03 against main @ e625b638, after Slice A merged as PR #1437)

Slice A is MERGED. models.py already carries DirectoryUser.given_name/family_name; google.py already
has _build_group / _build_managed_group, _extract_name_parts, _USERS_PAGE_SIZE=500, _GROUPS_PAGE_SIZE=200,
and list_users/list_groups take limit: int | None = None. This slice builds on that, unchanged.

CALL SITES THIS SLICE TOUCHES (enumerated, not assumed):
- app/infrastructure/directory/google.py:17   -> import of execute_batch_request (REMOVED here)
- app/infrastructure/directory/google.py:559-629 -> get_group_members_batch (REBUILT here)
- app/infrastructure/directory/provider.py:184-205 -> get_group_members_batch protocol entry (untouched)
- app/infrastructure/directory/models.py -> gains 3 dataclasses
- app/integrations/google_workspace/client.py:170-199 -> execute_batch_request (NOT touched; left dead for TASK-25.1.6.11)
- app/packages/access/sync/desired_state.py:160 -> only consumer of get_group_members_batch (NOT touched)

STUB FACTS VERIFIED EMPIRICALLY WITH MYPY (not assumed; probe run and deleted 2026-09-03):
- DirectoryResource.new_batch_http_request is typed (googleapiclient-stubs _apis/admin/directory_v1/resources.pyi:877)
  and returns googleapiclient.http.BatchHttpRequest.
- STUB INACCURACY, MUST BE HANDLED: the stub declares the callback as
  Callable[[str, googleapiclient.http.HttpRequest, HttpError | None], Any] - the middle parameter is typed
  HttpRequest even though at runtime it is the DESERIALISED RESPONSE. Annotating the callback's response
  parameter as the Members TypedDict FAILS mypy with arg-type. The response parameter MUST be annotated
  Any (exactly as client.py:175 does today). Do not "fix" this; it is a stub bug, not a code bug.
- BatchHttpRequest.add(request, callback=None, request_id=None) and BatchHttpRequest.execute(http=None)
  type-check as used. NOTE: batch execute takes NO num_retries - the batch path has no SDK-native retry,
  unlike _paginate. Named delta, not fixed here.
- members_resource.list_next(previous_request, previous_response) is typed
  (MembersHttpRequest, Members) -> MembersHttpRequest | None. This is the paging mechanism to use; it
  returns None when the response carries no nextPageToken, so no manual token handling is needed.
- MembersHttpRequest.execute(num_retries=...) -> Members; Members["nextPageToken"] is str | None.
- googleapiclient/http.py:71 MAX_BATCH_LIMIT = 1000 and http.py:1440 raises BatchError past it.
  BatchError is NOT an HttpError, so classify_google_error re-raises it: an unchunked batch over a
  >1000-group domain would CRASH. Slice A made list_groups unbounded, so the new composition can reach
  that. Chunking is therefore required by this slice, not optional (HUMAN-APPROVED 2026-09-03).

HUMAN DECISIONS TAKEN DURING PLANNING (2026-09-03):
D1. Chunk batch rounds at _BATCH_MAX_REQUESTS = 100 (Google's Admin SDK batch guidance), well under
    MAX_BATCH_LIMIT. Forces the AC#4 wording amendment recorded in the comment on this task.
D2. get_group_members_batch stays all-or-nothing, but its failure status is now CLASSIFIED by
    classify_google_error (429/503 -> TRANSIENT_ERROR with retry_after, 404 -> NOT_FOUND) instead of the
    blanket PERMANENT_ERROR / "BATCH_ERRORS" that execute_batch_request hardcoded. That is the whole point
    of moving classification to the adapter per decisions/outbound-clients.md. No consumer impact today:
    desired_state.py:163 only reads is_success. Comment left on TASK-77.
D3. The batched members.list requests pass maxResults=_MEMBERS_PAGE_SIZE = 200, matching legacy
    google_directory.py:18. Human direction: fix things as they come while migrating toward
    decisions/layers.md, keeping siblings informed.
D4. Composition name, signature and dataclasses accepted as proposed (Step 1 / Step 5 below).
    Groups with ZERO members are INCLUDED. Legacy list_groups_with_members dropped them
    (integrations/google_workspace/google_directory.py:187-190) - that filtering is consumer business
    logic and belongs to TASK-25.1.6.5 per scope item (e). Comment left on .5.

---------------------------------------------------------------------------
STEP 1 - models.py: three frozen dataclasses for the composition [AC#4, AC#5]

Add to app/infrastructure/directory/models.py (and to __all__):

    @dataclass(frozen=True)
    class DirectoryGroupWithMembers:
        group: DirectoryGroup
        members: tuple[DirectoryMember, ...] = ()

    @dataclass(frozen=True)
    class DirectoryGroupFailure:
        group_email: str
        status: OperationStatus
        error_code: str | None
        message: str

    @dataclass(frozen=True)
    class DirectoryGroupsWithMembers:
        groups: tuple[DirectoryGroupWithMembers, ...] = ()
        failures: tuple[DirectoryGroupFailure, ...] = ()

Tuples, not lists, so frozen means frozen. This adds the file's first import:
`from infrastructure.operations.status import OperationStatus`. That is legal - decisions/layers.md
declares infrastructure/operations/ a shared kernel importable from any tier - and it is what
decisions/operation-result.md's closed status set forces: partial batch outcomes must be expressed in
the typed payload, never as a new OperationStatus member.
Per decisions/type-model-boundaries: frozen dataclasses, because these are canonical internal entities,
not I/O boundary models.

STEP 2 - google.py: _execute_batch_round, the chunked per-key batch primitive [AC#1, AC#8]

Add constants next to the existing page-size constants:
    _MEMBERS_PAGE_SIZE = 200      # matches legacy google_directory.py:18
    _BATCH_MAX_REQUESTS = 100     # googleapiclient MAX_BATCH_LIMIT is 1000; stay well under it

Add:

    def _execute_batch_round(
        self,
        service: AdminDirectoryResource,
        requests: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, HttpError]]:
        """Run one batch round, returning per-key responses and per-key errors.

        Chunked because BatchHttpRequest.add raises BatchError past MAX_BATCH_LIMIT.
        """
        responses: dict[str, Any] = {}
        errors: dict[str, HttpError] = {}

        def callback(request_id: str, response: Any, exception: HttpError | None) -> None:
            if exception is not None:
                errors[request_id] = exception
            else:
                responses[request_id] = response

        keys = list(requests)
        for start in range(0, len(keys), _BATCH_MAX_REQUESTS):
            batch = service.new_batch_http_request(callback=callback)
            for key in keys[start : start + _BATCH_MAX_REQUESTS]:
                batch.add(requests[key], request_id=key)
            batch.execute()
        return responses, errors

`response: Any` is MANDATORY - see the stub inaccuracy in GROUNDING. This helper does NOT return
OperationResult and does NOT classify: it hands raw responses and raw HttpErrors back so each caller
picks its own failure policy (AC#1). That is the behaviour execute_batch_request could not express.

STEP 3 - google.py: _batch_list_members, paginated across batch rounds [AC#2, AC#9]

    def _batch_list_members(
        self,
        service: AdminDirectoryResource,
        group_keys: list[str],
    ) -> tuple[dict[str, list[dict[str, Any]]], dict[str, HttpError]]:
        """Fetch every member page for each group, re-batching only unfinished groups."""
        members_resource = service.members()
        raw_members: dict[str, list[dict[str, Any]]] = {key: [] for key in group_keys}
        errors: dict[str, HttpError] = {}
        pending: dict[str, Any] = {
            key: members_resource.list(groupKey=key, maxResults=_MEMBERS_PAGE_SIZE)
            for key in group_keys
        }
        while pending:
            responses, round_errors = self._execute_batch_round(service, pending)
            errors.update(round_errors)
            next_pending: dict[str, Any] = {}
            for key, response in responses.items():
                raw_members[key].extend(response.get("members", []) or [])
                next_request = members_resource.list_next(pending[key], response)
                if next_request is not None:
                    next_pending[key] = next_request
            pending = next_pending
        return raw_members, errors

Termination: a key leaves `pending` when it errored (absent from responses) or when list_next returns
None. Same mechanic as the existing _paginate (google.py:78-101); no extra round cap is added, to stay
consistent with it. This closes the silent-truncation defect (fact 2 in the description) which today
also affects packages/access/sync/desired_state.py:160.

STEP 4 - google.py: rebuild get_group_members_batch on the new helpers [AC#1, AC#2, AC#3, AC#9]

Add two small private helpers, used by Step 4 and Step 5 (two call sites justify them):

    def _normalize_member_types(self, include_member_types: set[str] | None) -> OperationResult[set[str] | None]
        -> returns success(None) when the argument is None; success(set) otherwise; and
           permanent_error("include_member_types must contain at least one type",
           "DIRECTORY_MEMBER_TYPES_INVALID") when the normalised set is empty. Same message and error
           code as today - no new error codes are introduced anywhere in this slice.

    def _map_members(self, items: list[dict[str, Any]], allowed: set[str] | None) -> list[DirectoryMember]
        -> the existing type-filter + _build_directory_member loop from google.py:614-627, extracted verbatim.

Rewrite get_group_members_batch's body (signature and return type UNCHANGED):
  1. empty group_keys -> success({}) (unchanged; keeps test_returns_empty_dict_for_empty_input green).
  2. validate include_member_types via _normalize_member_types BEFORE issuing any request. Today the
     validation runs AFTER the batch call (google.py:605-612), so an invalid argument burns a round-trip.
     Same returned result, no wasted call. Named as a deliberate ordering change.
  3. normalise keys, build the service with the CURRENT scope
     "https://www.googleapis.com/auth/admin.directory.group.readonly" (google.py:583) - unchanged, see
     RESIDUALS.
  4. raw_members, errors = self._batch_list_members(service, normalized_keys)
  5. if errors: classify the FIRST error via self._map_sdk_exception(first_error, "get_group_members_batch")
     and return it through _typed_error. All-or-nothing preserved (AC#3); status fidelity gained (D2).
  6. otherwise success({key: self._map_members(raw, allowed) for key, raw in raw_members.items()}).
Delete the `from integrations.google_workspace.client import ... execute_batch_request` half of the
import at google.py:17, keeping classify_google_error.

STEP 5 - provider.py + google.py: the groups-with-members composition [AC#4, AC#5, AC#6, AC#7]

provider.py - add to the DirectoryProvider Protocol, after list_groups:

    def list_groups_with_members(
        self,
        query: str = "",
        limit: int | None = None,
        include_member_types: set[str] | None = None,
    ) -> OperationResult[DirectoryGroupsWithMembers]: ...

Docstring states: implementors SHOULD use a provider-native batch API; groups whose members could not be
fetched are returned in `failures`, not as an error status, because decisions/operation-result.md's status
set is closed; groups with zero members ARE included.

google.py - implement:
  1. groups_result = self.list_groups(query=query, limit=limit); on failure return _typed_error.
     This deliberately reuses Slice A's generic/managed branch (empty query -> _build_group,
     non-empty -> _build_managed_group) rather than duplicating mapping.
  2. empty group list -> success(DirectoryGroupsWithMembers()) WITHOUT building a service or a batch.
  3. _normalize_member_types(include_member_types); on failure return _typed_error.
  4. group_by_email = {group.group_email: group for group in groups}  (dict keying collapses duplicate
     emails; the Directory API cannot return two groups with the same primary email, and the managed
     mapper already canonicalises aliases - noted, not defended against).
  5. service = self._get_service(["https://www.googleapis.com/auth/admin.directory.group.member.readonly"])
     - the same least-privilege scope get_group_members uses (google.py:521).
  6. raw_members, errors = self._batch_list_members(service, list(group_by_email))
  7. groups tuple = one DirectoryGroupWithMembers per email NOT in errors, members mapped via _map_members.
     failures tuple = one DirectoryGroupFailure per errored email, built by a small
     _build_group_failure(group_email, exc) that calls classify_google_error(exc) for status/error_code
     and str(exc) for message.
  8. emit `directory_groups_with_members_listed` with returned/failed counts, matching the observability
     shape Slice A added to list_groups.
NOTE (deliberate, per decisions/outbound-clients.md): classify_google_error RE-RAISES unmapped HttpError
statuses (client.py:145). A per-group 400 therefore propagates out of the composition rather than becoming
a DirectoryGroupFailure. That is correct - an unexpected status is a bug, not an outcome - and it is
covered by a test.
NOTE (AC#7): no groups_filters, no user-record merging, no dataframe conversion. Verified by reading
integrations/google_workspace/google_directory.py:135-200: the legacy behaviours this slice does NOT
reproduce are (a) filters.filter_by_condition over raw dicts, (b) get_members_details merging whole user
records into members, (c) dropping zero-member groups, (d) the fields= projection to
{id, email, name, directMembersCount, description}. All four are TASK-25.1.6.5's.

---------------------------------------------------------------------------
VALIDATION: cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' && uv run ruff check . &&
uv run pytest tests --ignore=tests/smoke. Run after Step 4 and after Step 5.
Plus: grep -rn "execute_batch_request" app/infrastructure app/packages -> expect zero.
Plus: git diff --name-only -> expect only app/infrastructure/directory/{models,provider,google}.py and
app/tests/unit/infrastructure/directory/test_google.py.

AC TRACEABILITY
AC#1 provider owns batch orchestration, per-key responses + exceptions -> Steps 2,4 ->
     TestGetGroupMembersBatch::test_vendor_batch_helper_is_not_imported +
     ::test_surfaces_per_key_response_and_error
AC#2 paginates across rounds, re-batches only unfinished groups -> Step 3 ->
     ::test_paginates_members_across_batch_rounds + ::test_second_round_rebatches_only_unfinished_groups
AC#3 signature + all-or-nothing preserved, packages/access untouched -> Step 4 ->
     ::test_signature_is_unchanged + ::test_one_failing_group_fails_the_whole_batch +
     the 5 existing TestGetGroupMembersBatch tests + tests/unit/packages/access/** green unmodified
AC#4 composition exists, batched, typed dataclasses -> Steps 1,5 ->
     TestListGroupsWithMembers::test_returns_typed_groups_with_members +
     ::test_issues_one_batched_round_trip_per_page_depth
AC#5 per-group failures inside the success payload, no new status -> Steps 1,5 ->
     ::test_failed_group_is_carried_in_failures_with_classified_status
AC#6 composition test coverage -> Step 5 -> the five named TestListGroupsWithMembers cases below
AC#7 no consumer business logic, diff scope -> Step 5 -> ::test_zero_member_group_is_included +
     ::test_members_are_not_merged_with_user_records + git diff --name-only
AC#8 chunking -> Step 2 -> ::test_chunks_batch_rounds_at_the_request_limit
AC#9 maxResults on batched members.list -> Steps 3,4 -> ::test_batched_list_requests_page_size

TEST MATRIX
All in app/tests/unit/infrastructure/directory/test_google.py (existing file, existing feature-prefixed
name; unit layer per decisions/testing.md - no network, no real time, MagicMock only for the Admin SDK
Resource, which is never the subject under test).

HARNESS WORK FIRST: the current _install_fake_batch (test_google.py:51-76) maps request_id -> a single
response and ignores request identity, so it cannot express pagination. Replace it with
_install_paged_batch(service, pages_by_key, errors_by_key=None) which:
  - wires service.members().list(groupKey=key, maxResults=...) to return a distinct per-key page-0 request,
  - wires service.members().list_next(prev_request, response) to return the next page request for that key
    or None when exhausted,
  - wires service.new_batch_http_request(callback) to a batch double that records added request_ids and,
    on execute(), invokes callback(request_id, page_payload, None) or callback(request_id, None, HttpError)
    for keys in errors_by_key,
  - records the added-request_id list PER new_batch_http_request call so tests can assert chunking and
    re-batching.
The five existing TestGetGroupMembersBatch tests are migrated onto it; only
test_normalises_group_keys_to_lowercase (test_google.py:1370) changes assertion, gaining
maxResults=_MEMBERS_PAGE_SIZE (AC#9), and test_propagates_batch_failure becomes
test_one_failing_group_fails_the_whole_batch asserting a CLASSIFIED status (D2).

Happy path:
  - multi-group batch returns every group's members (existing, migrated)
  - composition returns one DirectoryGroupWithMembers per group with mapped DirectoryMember tuples
Boundary:
  - group with a second page: both pages' members present, in order
  - two groups, one needing a second page: round 2's batch contains ONLY that group's request_id
  - 150 group keys: new_batch_http_request called twice for round 1 and all 150 results merged
  - empty group_keys / empty group list: success, new_batch_http_request never called
  - group with zero members: present in `groups` with an empty members tuple
  - include_member_types={"USER"} filters GROUP members out (existing, migrated)
  - include_member_types=set(): DIRECTORY_MEMBER_TYPES_INVALID and NO API call issued
Failure:
  - one group's batch item returns HttpError(429): get_group_members_batch -> TRANSIENT_ERROR
    (all-or-nothing); composition -> success with that group in `failures`, status TRANSIENT_ERROR,
    error_code "429", and the other group still in `groups`
  - list_groups fails: composition returns the typed error and issues no batch
  - one group's batch item returns HttpError(400) (unmapped): the exception propagates out of the
    composition rather than being swallowed
Regression:
  - tests/unit/packages/access/** and tests/integration/packages/access/** pass unmodified (AC#3 proof)
  - the partial DirectoryProvider fakes at tests/integration/packages/access/sync/conftest.py:156 and
    tests/unit/packages/access/sync/test_application.py:275 keep working: Protocol growth is structural,
    pyproject.toml excludes ^tests/ from mypy, and the only isinstance(..., DirectoryProvider) checks
    (tests/unit/infrastructure/directory/test_factory.py:43,:93) target GoogleDirectoryProvider, which
    will implement the new method.

ASSUMPTIONS AND DOUBTS
1. VERIFIED, not assumed: execute_batch_request has exactly one consumer repo-wide (google.py:17, :585).
   Re-verify with `grep -rn execute_batch_request app/` before merge; expect only client.py after this PR.
2. VERIFIED, not assumed: the stub types every surface used here, and the callback response parameter must
   be Any (mypy probe, see GROUNDING). No Any-laundering beyond that one stub-forced annotation and the
   raw-payload dicts, which are the same shape _paginate already returns.
3. ASSUMED: no deployed environment has a Google group whose members exceed one page today, so the
   pagination fix cannot regress packages/access - it can only ever return MORE members. Verify by reading
   the desired_state sync logs for member counts equal to a page boundary before merge; if one is found it
   is a live bug this PR fixes, worth calling out in the PR description.
4. ASSUMED: the service account's domain-wide delegation already grants
   admin.directory.group.member.readonly. VERIFIED indirectly - get_group_members (google.py:521) uses it
   in production today. The composition uses the same scope, so no delegation change is required.
5. ASSUMED: BatchHttpRequest invokes the callback synchronously during execute(). VERIFIED by reading
   googleapiclient/http.py:1455-1528 (_execute walks the response order and calls the callback inline).
   The helpers therefore need no async handling and the provider stays sync, matching every other method.
6. NOT ASSUMED, stated: the batch path has no SDK-native retry, because BatchHttpRequest.execute takes no
   num_retries. decisions/outbound-clients.md forbids hand-rolled retry, so none is added. This is a
   known gap in the SDK, recorded here rather than worked around.

RESIDUALS RECORDED (deliberately NOT fixed here, siblings updated)
R1. get_group_members (google.py:499-557) keeps its own inline member-type filter and mapping loop rather
    than using _normalize_member_types/_map_members. Extracting it too would mix a mechanical refactor of
    an out-of-scope method into a behaviour PR (size-gate trigger #3). Comment left on TASK-25.1.6.11.
R2. get_group_members_batch keeps scope admin.directory.group.readonly while get_group_members and the new
    composition use admin.directory.group.member.readonly. Converging them changes an OAuth scope on a
    live path, which AC#3 forbids in this PR. Comment left on TASK-25.1.6.11.
R3. execute_batch_request (client.py:170-199) is left in place with zero consumers; TASK-25.1.6.11 deletes
    it. Not deleted here so this PR touches app/infrastructure/directory/** only (AC#7).

BLAST RADIUS AND ROLLBACK
Runtime blast radius is packages/access/sync/desired_state.py:160, the only consumer of the only changed
live method. Its behaviour changes in exactly two ways, both strictly better: groups past the first member
page stop being silently truncated, and a batch failure now carries a classified status instead of a
blanket PERMANENT_ERROR (the consumer only reads is_success, so no branch changes). The composition and
the three dataclasses are net-new with zero production callers until TASK-25.1.6.5, so they cannot regress
anything. No config prerequisite, no deploy ordering constraint, no data migration, no OAuth scope change.
A single git revert fully restores prior behaviour; the only thing lost on revert is the truncation fix.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-03 20:08
---
AC SET AMENDED 2026-09-03 (task-planner, human-approved during planning). Recorded explicitly per the backlog-task-workflow rule against silently reshaping ACs. Seven criteria became nine.

MAPPING: #1 unchanged. #2 unchanged. #3 AMENDED - still all-or-nothing, but the phrase 'gains ONLY the pagination fix' is no longer true: the human approved classifying the per-item HttpError via classify_google_error instead of reproducing execute_batch_request's blanket PERMANENT_ERROR/BATCH_ERRORS, because moving classification to the adapter IS decisions/outbound-clients.md. #4 AMENDED - 'one batched round-trip per page depth' became 'one batched round-trip per chunk of at most _BATCH_MAX_REQUESTS groups per page depth', forced by the new #8. #5 unchanged. #6 AMENDED - gained the chunked-batch case. #7 AMENDED - gained the explicit 'zero-member groups are returned rather than dropped' clause, which the legacy path did drop. #8 NEW (chunking). #9 NEW (maxResults=200).

WHY #8 IS NOT SCOPE CREEP: googleapiclient/http.py:71 sets MAX_BATCH_LIMIT=1000 and http.py:1440 raises BatchError past it. BatchError is not an HttpError, so classify_google_error re-raises it and it escapes as an unhandled crash. TASK-25.1.6.3 (Slice A) made list_groups unbounded, so this task's composition - which feeds list_groups output straight into a batch - is the first code path in the repo that can reach that limit. The crash would be introduced BY this task, so it is fixed IN this task.

WHY #9: human direction 2026-09-03 - fix things as they come while migrating toward decisions/layers.md, keeping siblings informed. maxResults=200 matches integrations/google_workspace/google_directory.py:18, the module TASK-25.1.6.5 deletes, so the surviving path reaches parity rather than inheriting an unstated default.

SIZE GATE: FITS ONE PR. ~200 production LOC across 3 files (models.py +30, provider.py +25, google.py ~145 changed), one subsystem (app/infrastructure/directory/), no terraform, no CI, no config. Under the ~400 LOC / ~10 file threshold. No decomposition required.
---

author: @task-planner
created: 2026-09-03 20:09
---
DESCRIPTION CORRECTION 2026-09-03. The scope section above states that 'googleapiclient-stubs types ... the (request_id, response, HttpError | None) callback, so no Any-laundering is needed.' HALF OF THAT IS WRONG and would cost the implementer time.

VERIFIED BY RUNNING MYPY, not by reading: the stub declares the callback as Callable[[str, googleapiclient.http.HttpRequest, HttpError | None], Any] - the MIDDLE parameter is typed HttpRequest even though at runtime it receives the deserialised response. Annotating that parameter with the Members TypedDict produces:

  error: Argument 'callback' to 'new_batch_http_request' of 'DirectoryResource' has incompatible type
  'Callable[[str, Members, HttpError | None], None]'; expected
  'Callable[[str, HttpRequest, HttpError | None], Any] | None'  [arg-type]

So the callback's response parameter MUST be annotated Any, exactly as integrations/google_workspace/client.py:175 already does. This is an upstream stub bug, not a code smell - do not try to 'fix' it, and do not let a reviewer flag it. decisions/sdk-typing.md's own Consequences section anticipates exactly this: the Google stubs are community-maintained and 'gaps/lag ... are expected'.

EVERYTHING ELSE IN THAT SENTENCE IS CORRECT and re-verified: new_batch_http_request is typed on DirectoryResource (stubs _apis/admin/directory_v1/resources.pyi:877), BatchHttpRequest.add(request, request_id=...) and .execute() type-check as used, and members_resource.list_next(previous_request, previous_response) is fully typed as (MembersHttpRequest, Members) -> MembersHttpRequest | None - which is the paging mechanism the plan uses, so no manual nextPageToken handling is needed anywhere.

ONE MORE STUB/SDK FACT WORTH KNOWING: BatchHttpRequest.execute() takes NO num_retries, unlike MembersHttpRequest.execute(num_retries=...). The batch path therefore has no SDK-native retry. decisions/outbound-clients.md forbids hand-rolling one, so none is added; this is recorded as a named gap in the plan rather than worked around.
---
<!-- COMMENTS:END -->

---
id: TASK-25.1.6.3
title: >-
  Make DirectoryProvider list-all generic and unbounded, and close the mapping
  gaps blocking the legacy consumers
status: Done
assignee:
  - '@me'
created_date: '2026-09-02 15:00'
updated_date: '2026-09-03 20:22'
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
DECISION RECORDED (2026-09-02, human-directed): infrastructure/directory/{provider,google,factory}.py::DirectoryProvider / GoogleDirectoryProvider IS THE WAY FORWARD. It survives; app/integrations/google_workspace/google_directory.py is deleted; the four legacy app/modules/* consumers move onto the DirectoryProvider Protocol. This settles TASK-25.1.6's AC#5 for the Directory surface - no further 'which side wins' analysis is needed, only migration.

SLICE A of two (split 2026-09-03, human-approved; see comment #1). Capability parity ONLY - no consumer moves here. It exists because a straight repoint would silently change behaviour: the Protocol as written today cannot express what two of the four legacy call sites need. SLICE B is TASK-25.1.6.3.1 (batch rearchitecture + groups-with-members composition).

GUIDING PRINCIPLE FOR THIS SLICE (human, 2026-09-03): an infrastructure service method must be GENERIC. Early bespoke conveniences on this Protocol were naive attempts to improve developer experience and introduced antipatterns. Where feature-specific behaviour is required, the feature owns it. Each task moves us closer to decisions/outbound-clients.md and decisions/sdk-typing.md; interim shims are acceptable only to keep production working, never as a destination.

GAPS THIS SLICE CLOSES (verified 2026-09-03 against the code and the installed googleapiclient-stubs).

1. list_users cannot express 'the whole domain', and its limit does not do what it claims. Legacy google_directory.list_users() paginates to exhaustion and returns every user, which is what modules/provisioning/users.py relies on for a full-directory sync. DirectoryProvider.list_users(query='', limit=100) defaults to 100 - but the truncation is worse than the task originally described: google.py:402 _paginate walks EVERY page to exhaustion and only then applies result.data[:limit] (google.py:418). So today limit is a post-hoc slice, not an API-layer bound: modules/dev/google.py:82's list_users(limit=3) pulls the entire directory and discards all but three. Both halves are fixed here.

2. list_groups requires a query and rewrites bare strings. Legacy google_directory.list_groups() takes NO argument and lists every group. DirectoryProvider.list_groups(query: str) is required-argument, translates a bare string into email:{query}* and, when _managed_group_query_prefix matches, switches to an unfiltered list plus a client-side managed-prefix filter. modules/reports/google_groups.py:69 calls list_groups() with no arguments and expects all groups. Note the empty string is NOT usable as-is today: '' has no ':' or '=', so it becomes the query email:*.

3. Managed-group policy is feature logic sitting in an infrastructure service. _extract_managed_group_email prefers sg-prefixed aliases, _managed_group_query_prefix switches strategy, and _build_directory_group returns DIRECTORY_GROUP_DOMAIN_MISMATCH for any group outside DIRECTORY_MANAGED_GROUP_DOMAIN. That is packages/access policy. A 'list every group in the domain' capability routed through it is a latent hard failure: DIRECTORY_MANAGED_GROUP_DOMAIN and DIRECTORY_MANAGED_GROUP_PREFIX are unset everywhere today (grep-confirmed: no terraform, pyproject or Makefile entry), so there is no live impact - but the day that setting is populated, the reports consumer breaks. This slice splits the mapper in two and confines the managed policy to the paths that actually want it. FULL relocation of that policy into packages/access is deliberately NOT here - it touches packages/access and settings, mixing subsystems - and is tracked by its own follow-up task.

4. Silent group dropping. _build_directory_group can return success(None) - when the group has no resolvable email AND DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL is false - and list_groups then omits that group with no error. Impact, since the human asked for it concretely: packages/access/catalog silently omits an entitlement group (indistinguishable from 'not configured'), and modules/reports/google_groups.py silently ships an incomplete report. Under the generic mapper the only unmappable group is one missing email or provider id, i.e. a genuine provider data defect. Decision: skip it, log at warning with the provider group id, and count the drops on the completion log line. Never silent, and no feature policy added to infrastructure.

5. DirectoryUser cannot carry the names the migration needs. Legacy list_groups_with_members merged whole user records into member dicts via get_members_details, which is how modules/aws/identity_center.py:145-149 and :316-321 obtain name.givenName / name.familyName to create AWS users. DirectoryUser has only display_name. The stubs confirm the source shape exists and is typed (googleapiclient-stubs UserName TypedDict: givenName, familyName, fullName, displayName), so given_name and family_name are added here as capability parity. The member-to-user JOIN stays with the consumer - it is business logic and does not belong in the provider.

EXPLICITLY OUT OF SCOPE, each owned elsewhere: the groups-with-members composition, the batch pagination defect and the execute_batch_request rearchitecture (TASK-25.1.6.3.1); repointing any consumer (TASK-25.1.6.4 and .5); relocating managed-group policy into packages/access (its own follow-up task); modifying integrations/google_workspace/** or packages/access/**.

NOTE ON DATA SHAPE: the legacy functions return raw list[dict]; the provider returns DirectoryUser/DirectoryGroup/DirectoryMember frozen dataclasses. That translation is the point (decisions/sdk-typing.md item 3), not an obstacle - but the consuming slices need field-by-field mapping, so AC#7 requires the field inventory be recorded here rather than discovered mid-migration.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 DirectoryProvider can express 'every user in the domain' without a caller-supplied magic limit, GoogleDirectoryProvider implements it by paginating to exhaustion, and a test proves a multi-page result set is returned in full
- [x] #2 list_users stops paginating once an explicit limit is satisfied instead of walking every page and slicing the result, proven by a test asserting the number of pages fetched
- [x] #3 DirectoryProvider can express 'every group in the domain' without a query and without routing through the managed-group-prefix path; a test proves it against a multi-page groups payload
- [x] #4 Group mapping is split into a generic mapper (email + provider id only) used by the unfiltered list paths and a managed mapper (alias preference plus domain enforcement) used by get_group, get_user_groups and the query path; existing packages/access behaviour is unchanged and its tests pass untouched
- [x] #5 A group entry that cannot be mapped is never silently dropped: it is logged at warning with its provider group id and counted on the completion log line, with a test covering an unmappable entry
- [x] #6 DirectoryUser carries given_name and family_name, populated from the Google name.givenName / name.familyName payload, so TASK-25.1.6.5 can perform the member-to-user join that legacy get_members_details did
- [x] #7 Every legacy google_directory.py response field the canonical dataclasses cannot carry is enumerated in the task notes, so TASK-25.1.6.4/.5 do not discover it mid-migration
- [x] #8 No consumer is repointed in this task, integrations/google_workspace/** is not modified, and git diff touches app/infrastructure/directory/** and its tests only
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PRECONDITION: TASK-25.1.6.1's characterization tests are Done (this task's declared dependency). Nothing in this slice touches the files those tests cover, but TASK-25.1.6.4 consumes both, so the gate stays.

FILES TOUCHED (3 production files, ~130 production LOC):
- app/infrastructure/directory/models.py
- app/infrastructure/directory/provider.py
- app/infrastructure/directory/google.py
Tests: app/tests/unit/infrastructure/directory/test_google.py (extend; 985 lines today, conventions already established: _request(payload) MagicMock helper, google_service fixture with list_next defaulting to None, mock_directory_settings with managed_group_domain='example.com' / managed_group_prefix='sg-').

STEP 1 - models.py: add given_name and family_name to DirectoryUser [AC#6]
Add two optional fields to the frozen DirectoryUser dataclass:
    given_name: str | None = None
    family_name: str | None = None
Both default to None, so every existing construction site keeps compiling. Placed after display_name, before is_active, keeping positional construction in google.py the only caller (all keyword). No other model changes in this slice - the groups-with-members dataclasses belong to TASK-25.1.6.3.1.
Test: test_google.py::TestListUsers asserts given_name/family_name populated from a name={'givenName','familyName'} payload and None when the name block is absent or is a bare string.

STEP 2 - google.py: extract name parts alongside the existing display name [AC#6]
_extract_display_name (google.py:198-227) already walks the name dict; add a sibling helper that returns the (given, family) pair from name.givenName / name.familyName, returning (None, None) when name is absent or is a str. Do NOT change _extract_display_name's precedence order (fullName, then displayName, then givenName+familyName, then str, then top-level displayName/fullName) - packages/access does not read display_name today but TASK-25.1.6.4 will diff report output, and changing it here would be an unrelated behaviour change.
Wire both into _build_directory_user (google.py:232-267).
Grounding: googleapiclient-stubs _apis/admin/directory_v1/schemas.pyi:947 UserName TypedDict = {displayName, familyName, fullName, givenName}. No stub gap.

STEP 3 - google.py: split group mapping into generic and managed mappers [AC#4]
Today _build_directory_group (google.py:269-311) does three things at once: managed-alias preference (_extract_managed_group_email), managed-domain enforcement, and canonical mapping. Split:
  _build_group(item) -> OperationResult[DirectoryGroup] - GENERIC. Requires email (via _extract_email(item, 'email', 'groupEmail')) and provider id (id or groupId). group_slug = local part. name/description passthrough. NO alias preference, NO domain check. Returns DIRECTORY_GROUP_EMAIL_REQUIRED / DIRECTORY_GROUP_ID_REQUIRED on missing fields - existing error codes, no new registry entries.
  _build_managed_group(item) -> OperationResult[DirectoryGroup | None] - resolves the canonical email via _extract_managed_group_email, applies enforce_managed_group_email and the managed-domain check, then delegates the remaining mapping to _build_group. Byte-for-byte the same outcomes as today's _build_directory_group.
Callers: get_group (google.py:565), get_user_groups (google.py:857), and list_groups WHEN a query is supplied -> _build_managed_group (unchanged behaviour). The new unfiltered list path -> _build_group.
_build_directory_group is renamed, not kept as a shim: it has no callers outside this module (grep-confirmed).
This is the minimum that satisfies the human's 'infrastructure methods must be generic' direction without dragging packages/access into the PR. Full relocation of the managed policy is the F1 follow-up task.
Tests: TestListGroups gains cases proving the unfiltered path returns a group whose email is outside managed_group_domain (which the managed path rejects with DIRECTORY_GROUP_DOMAIN_MISMATCH), and that the managed path's existing assertions are untouched.

STEP 4 - google.py + provider.py: limit-aware, unbounded-capable pagination [AC#1, AC#2]
_paginate (google.py:78-101) currently walks to exhaustion unconditionally. Add an optional limit parameter: after extending items from each page, stop when limit is not None and len(items) >= limit; trim to limit before returning. limit=None means walk to exhaustion.
Protocol signature (provider.py:53): list_users(query: str = '', limit: int | None = None). None (the new default) means 'every user in the domain'; an int caps the result. Docstring states the sentinel explicitly.
google.py list_users (google.py:394-436):
  - drop the limit <= 0 early return in favour of: limit is not None and limit <= 0 -> success([]).
  - page size becomes a module constant (_USERS_PAGE_SIZE = 500, the Admin SDK maximum, matching legacy google_directory._USERS_PAGE_SIZE) instead of maxResults=limit; when limit is smaller than the page size, pass min(limit, _USERS_PAGE_SIZE) so a small explicit limit still costs one small page.
  - remove the result.data[:limit] post-slice (now handled inside _paginate).
Only production caller of list_users is modules/dev/google.py:82 (list_users(limit=3)), which keeps working and stops pulling the whole directory.
Tests: TestListUsers - (a) limit=None returns all entries across three pages; (b) limit=2 with a 5-entry first page returns 2 and asserts list_next was never called; (c) limit spanning a page boundary stops at the second page, asserting the page count; (d) limit=0 returns [] with no request issued.

STEP 5 - google.py + provider.py: unfiltered group listing [AC#3, AC#5]
Protocol signature (provider.py:149): list_groups(query: str = '', limit: int | None = None). Empty query means 'every group in the domain'.
google.py list_groups (google.py:739-806): branch on query.strip() being empty FIRST, before _managed_group_query_prefix is consulted, and in that branch call groups_resource.list(customer=self._customer_id, maxResults=_GROUPS_PAGE_SIZE) with NO query kwarg (today an empty string would become the query email:*, which is not 'all groups'). Map that branch's items with _build_group; keep both existing branches mapping with _build_managed_group.
Observable drops [AC#5]: in the mapping loop, count entries where the mapper yields data None, log warning directory_group_skipped with the item's id, and emit the count on a completion log line (directory_groups_listed with returned/skipped counts). Applies to both branches. Result contents are unchanged - this only makes an existing silent path visible.
_GROUPS_PAGE_SIZE = 200 as a module constant (matches legacy google_directory._GROUPS_PAGE_SIZE).
Note deliberately NOT done: legacy passed orderBy='email'. Not replicated - utils/filters.compare_lists sorts internally (utils/filters.py:91-92), so no consumer depends on provider ordering. Recorded in notes as a named delta.
Tests: TestListGroups - (a) query='' returns every group across two pages and asserts groups().list was called without a query kwarg; (b) query='' does not apply the managed-prefix filter even when managed_group_prefix is set; (c) an entry the mapper cannot map is skipped, logged, and the remaining groups are returned; (d) existing query-path assertions unchanged.

STEP 6 - record the field inventory in the task notes [AC#7]
Write the enumeration below into Implementation Notes via --append-notes at implementation time (it is already drafted in this plan's Assumptions section so TASK-25.1.6.4/.5 can read it before this slice merges).

VALIDATION: cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)' && uv run ruff check . && uv run pytest tests --ignore=tests/smoke. Run after steps 3 and 5.

AC TRACEABILITY
AC#1 unbounded users -> Step 4 -> TestListUsers::test_limit_none_returns_all_pages
AC#2 limit stops pagination -> Step 4 -> TestListUsers::test_limit_stops_before_next_page
AC#3 unfiltered groups -> Step 5 -> TestListGroups::test_empty_query_returns_all_pages
AC#4 mapper split -> Step 3 -> TestListGroups::test_unfiltered_path_accepts_group_outside_managed_domain + existing managed-path tests unchanged
AC#5 observable drops -> Step 5 -> TestListGroups::test_unmappable_group_is_logged_and_counted
AC#6 name fields -> Steps 1-2 -> TestListUsers::test_user_carries_given_and_family_name
AC#7 field inventory -> Step 6 -> notes (no test)
AC#8 no consumer repointed -> whole plan -> verified by git diff --name-only

TEST MATRIX (app/tests/unit/infrastructure/directory/test_google.py, per decisions/testing.md: unit layer, Protocol-shaped fakes, no network, MagicMock only for the SDK Resource which is not the subject under test)
Happy: limit=None all users; query='' all groups; user with full name block; group outside managed domain via the generic path.
Boundary: limit=0; limit exactly equal to page size; limit spanning a page boundary; single empty page; group payload with an empty groups key.
Failure: HttpError on the first page classified into an error result (existing pattern); users payload not a list; a users entry that is not a dict; an unmappable group entry.
Regression: every existing TestListGroups/TestListUsers/TestGetGroup/TestGetUserGroups assertion passes unchanged, plus the packages/access suites (tests/unit/packages/access/**) untouched and green - that is the AC#4 'behaviour unchanged' proof.

ASSUMPTIONS AND DOUBTS
1. ASSUMED: no production consumer depends on list_users' current default of 100. VERIFIED by grep - the only production caller is modules/dev/google.py:82, which passes an explicit limit=3. If a caller appears before merge, re-grep.
2. ASSUMED: no production consumer passes an empty query to list_groups today. VERIFIED - packages/access/catalog/service.py:144 and packages/access/sync/desired_state.py:199 both pass a non-empty prefix; modules/dev/google.py:127 passes email={...}. So redefining '' is a change to an untriggered path.
3. ASSUMED: growing the Protocol will not break the partial DirectoryProvider fakes in packages/access tests. VERIFIED - pyproject.toml:83 sets mypy exclude = ['^tests/'], and the only isinstance(..., DirectoryProvider) checks (tests/unit/infrastructure/directory/test_factory.py:43 and :93) target GoogleDirectoryProvider, which implements everything. Also, this slice adds no new Protocol METHODS - only optional parameters - so runtime_checkable membership is unaffected either way.
4. ASSUMED: DIRECTORY_MANAGED_GROUP_DOMAIN and DIRECTORY_MANAGED_GROUP_PREFIX are unset in every deployed environment. VERIFIED by grep across terraform/, app/pyproject.toml and Makefile - zero hits; both default to '' (infrastructure/configuration/infrastructure/directory.py:59,64). Consequence: the mapper split has NO behavioural effect in production today; it prevents a future one. Re-verify with the same grep before merge.
5. ASSUMED: provider result ordering is not depended on. VERIFIED - utils/filters.compare_lists sorts both sides in match mode (utils/filters.py:91-92) and uses dict keying in sync mode. Recorded as a named delta rather than replicated.
6. STUB COVERAGE VERIFIED, not assumed: googleapiclient-stubs is installed and types every surface this plan uses - UsersResource.list/list_next, GroupsResource.list (customer, maxResults, orderBy Literal['email'], pageToken, query) / list_next, and the Users/Groups TypedDicts with nextPageToken. No Any-laundering is introduced; the requests stay typed at their call sites, per decisions/sdk-typing.md item 3.

FIELD INVENTORY [AC#7 content, to be written into notes at implementation time]
Fields the legacy raw dicts carried that the canonical dataclasses do NOT, with the verdict for TASK-25.1.6.4/.5:
- name.givenName / name.familyName (user) -> ADDED to DirectoryUser here as given_name/family_name. Consumed by modules/aws/identity_center.py:145-149 (sync_users preformatting) and :316-321 (provision_aws_users). Without this the AWS user-creation path cannot be migrated.
- primaryEmail (user) -> COVERED. DirectoryUser.email is populated from primaryEmail first (_extract_email(item,'primaryEmail','email')). Consumers comparing on primaryEmail (identity_center.py:137, :243, :253) map to .email.
- suspended (user) -> COVERED as DirectoryUser.is_active (inverted). No legacy consumer reads it.
- directMembersCount (group) -> NOT CARRIED. Legacy list_groups_with_members requested it in its fields projection and kept it in filtered_groups. Grep-confirmed ZERO downstream reads. Verdict: drop; do not add a field for it.
- member status (member) -> NOT CARRIED. Legacy requested members(email, role, type, status). Grep-confirmed ZERO downstream reads of a member's status. Verdict: drop. Note the stub does expose Member.status if a consumer is later found.
- group aliases / nonEditableAliases -> NOT CARRIED on DirectoryGroup; used internally by the managed mapper only. No legacy consumer reads them.
- merged user record on each member (legacy get_members_details) -> NOT CARRIED and deliberately not added. DirectoryMember stays a membership record. TASK-25.1.6.5 performs the join itself using list_users + given_name/family_name. This is business logic and decisions/outbound-clients.md keeps it out of the provider.
- DirectoryMember.provider_user_id is hardcoded to None (google.py:257) even though the Google member payload carries id, which is instead mapped to membership_id. Not changed here (no consumer needs it); flagged so .4/.5 do not read it expecting a value.

BLAST RADIUS AND ROLLBACK
Runtime blast radius is limited to modules/dev/google.py's smoke helpers and packages/access, whose call sites all pass explicit arguments and are covered by existing tests. The mapper split is a no-op in every deployed environment (assumption 4). The riskiest change is the list_users default moving from 100 to unbounded: a future caller omitting limit would fetch the whole directory - mitigated because it now matches the method name's promise and the docstring states it, and because the only current caller is explicit. Single git revert fully restores prior behaviour; there is no data migration, no config prerequisite and no deploy ordering constraint. Nothing downstream depends on this slice until TASK-25.1.6.4 merges.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
FIELD INVENTORY (AC#7)
Legacy google_directory.py response fields vs canonical dataclass fields:
- name.givenName / name.familyName (user) -> ADDED to DirectoryUser as given_name and family_name. Consumed by modules/aws/identity_center.py for AWS user creation.
- primaryEmail (user) -> COVERED by DirectoryUser.email (populated from primaryEmail first).
- suspended (user) -> COVERED as DirectoryUser.is_active (inverted).
- directMembersCount (group) -> NOT CARRIED on DirectoryGroup. Grep confirmed zero downstream reads. Verdict: dropped.
- member status (member) -> NOT CARRIED on DirectoryMember. Grep confirmed zero downstream reads. Verdict: dropped.
- group aliases / nonEditableAliases -> NOT CARRIED on DirectoryGroup; used internally by managed mapper only.
- merged user record on member (legacy get_members_details) -> NOT CARRIED. Member-to-user join stays in consumer logic per decisions/outbound-clients.md.
- DirectoryMember.provider_user_id is hardcoded to None in Google provider (payload member id is mapped to membership_id).

CHANGE SUMMARY & TEST EVIDENCE
- Added given_name and family_name fields to DirectoryUser model in app/infrastructure/directory/models.py.
- Updated GoogleDirectoryProvider in app/infrastructure/directory/google.py to extract given and family names.
- Updated list_users signature in DirectoryProvider Protocol and GoogleDirectoryProvider with limit: int | None = None default. GoogleDirectoryProvider paginates to exhaustion when limit is None, uses _USERS_PAGE_SIZE = 500, and halts early when explicit limit is met.
- Updated list_groups signature with query: str = '', limit: int | None = None default. When query is empty, calls API without query filter and uses generic _build_group mapper.
- Split group mapping in GoogleDirectoryProvider into generic _build_group (email + provider group ID mapping) and _build_managed_group (alias preference and domain enforcement).
- Unmappable group entries in list_groups log warning directory_group_skipped with provider_group_id and increment skipped_count on directory_groups_listed completion log line instead of dropping silently.
- Verified test suite: 65 passed in tests/unit/infrastructure/directory/test_google.py, 273 passed in tests/unit/packages/access/, 282 passed across total pytest suite.
- mypy and ruff check quality gates passed with zero errors.

DoD Items for Human Verification:
1. Verify PR review touches only app/infrastructure/directory/**, its unit tests, and task metadata.
2. Verify task status transition to Done after human review.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-03 17:58
---
RE-SCOPED AND RETITLED 2026-09-03 (task-planner, human-approved during planning). Split under the implementation-planning size gate: the original scope mixed a mechanical mapping/pagination change (reviewed for completeness) with a behavioural rearchitecture of the Google batch surface (reviewed for correctness) - gate trigger #3. Estimated combined diff was ~295 production LOC across 3 files, under the 400 LOC threshold, so the split is a deliberate reviewability choice rather than a hard-gate requirement.

THIS TASK IS NOW SLICE A: list-all semantics, the generic/managed group-mapping split, observable drops, the DirectoryUser name fields, and the field inventory. It unblocks TASK-25.1.6.4 on its own.

SLICE B IS THE NEW TASK-25.1.6.3.1: batch orchestration moved out of integrations/google_workspace/client.py::execute_batch_request into GoogleDirectoryProvider, batch pagination, and the groups-with-members composition. Only TASK-25.1.6.5 needs it, and TASK-25.1.6.5's dependency has been repointed accordingly.

AC REPLACEMENT RECORDED EXPLICITLY (per the backlog-task-workflow rule against silently reshaping ACs). The previous six criteria were REPLACED with eight. Mapping: old #1 (unbounded users) survives as new #1 and gains new #2; old #2 (unbounded groups) survives as new #3; old #3 (silent drop) survives as new #5 and gains new #4, which is the mechanism the human asked for after reviewing the drop-impact analysis; old #4 (groups-with-members composition) MOVED WHOLESALE to TASK-25.1.6.3.1 AC#4-#7 and is no longer this task's responsibility; old #5 (field inventory) survives as new #7; old #6 (no consumer repointed) survives as new #8. New #6 (DirectoryUser given_name/family_name) is added scope, human-approved, because without it TASK-25.1.6.5 cannot map identity_center's name.givenName / name.familyName AWS user-creation preformatting.
---
<!-- COMMENTS:END -->

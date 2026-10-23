---
id: TASK-76.3
title: 'Cut access catalog, sync and request onto the generic DirectoryProvider path'
status: Done
assignee:
  - '@me'
created_date: '2026-09-04 14:18'
updated_date: '2026-09-04 17:30'
labels:
  - layering
milestone: m-3
dependencies:
  - TASK-76.2
parent_task_id: TASK-76
priority: medium
ordinal: 150000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 3 of TASK-76 (see the coordinator plan, decisions D1, D2, D5). The behaviour-bearing slice. Feature-only: after it, packages/access no longer relies on any managed-group behaviour from the provider, but the provider still carries that behaviour unused until TASK-76.4 deletes it. That is what keeps this PR green on its own without a shim.

CALL SITES to move (plan fact F5), each through ManagedGroupPolicy from TASK-76.2:
- app/packages/access/catalog/service.py:144 - list_groups(query=prefix) becomes a generic listing plus policy.matches_prefix filtering, with policy.canonical_slug driving the slug the entitlement derivation uses (service.py:157 onward). Note the prefix query path is inert today (plan fact F2) so the server-side-query-to-client-filter change is not a regression.
- app/packages/access/sync/desired_state.py:221 discover_group_slugs - same treatment. Careful: TASK-78 recently changed this method to return OperationResult and propagate list_groups failures. Preserve that contract exactly; do not reintroduce an empty-set fallback.
- app/packages/access/sync/desired_state.py:130 and :155 - get_group(slug) becomes get_group(policy.group_key(slug)).
- app/packages/access/request/service.py:187 - same get_group key composition.
- app/packages/access/request/policies.py:93 and :102 - get_group_members already passes a full group_email at :93; the fallback_slug at :102 must be composed through policy.group_key.
- get_user_groups: the provider currently filters results to the managed domain via _build_managed_group (google.py:1097). That filter moves to the access consumer through policy.is_managed. Identify every access-side consumer of get_user_groups before changing it and cover each.

DECISION TO MAKE AND RECORD IN NOTES: whether an out-of-domain group is an ERROR or an OMISSION at each feature call site. The provider today returns DIRECTORY_GROUP_DOMAIN_MISMATCH (a hard error) from the mapper, which for a LIST operation means one stray group fails the whole listing. Parent AC#5 explicitly allows either rejected or ignored. Recommended and to be confirmed during implementation: OMIT with a warning log for list-shaped operations (discovery must not be taken down by one unrelated group), ERROR for get-shaped operations (an explicitly requested group being out of domain is a real fault). State the choice and rationale in the notes.

PERFORMANCE. Generic listing plus client-side filtering fetches every group and filters locally. This is not a regression: the managed path already did exactly that (full unfiltered list plus _matches_managed_group_prefix), and per plan fact F2 the server-side query path is the one in use today. If the unfiltered listing is judged too costly for catalog and sync, raise it as a follow-up rather than reintroducing provider-side policy.

NOT IN SCOPE. Deleting anything under app/infrastructure/ (TASK-76.4). Touching app/modules/provisioning, which is frozen under decisions/migration.md rule 1.

TESTING (decisions/testing.md). Protocol-conformant fakes for DirectoryProvider - not MagicMock - returning DirectoryGroup values including aliases and out-of-domain entries. Assertions at the feature boundary: catalog entitlement listing, sync discovery and platform state, request submission. Keep the existing access suites green; where an existing test asserted provider-side managed behaviour, move that assertion to the feature boundary rather than deleting it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 catalog, sync and request obtain canonical group email, slug, prefix matching and group keys exclusively through ManagedGroupPolicy; no access-side call passes a bare slug to DirectoryProvider
- [x] #2 sync discover_group_slugs keeps the OperationResult failure-propagation contract introduced by TASK-78, with a test proving an IDP failure still propagates rather than yielding an empty set
- [x] #3 The error-versus-omission decision for out-of-domain groups is made per call-site shape, implemented, and recorded with its rationale in the task notes
- [x] #4 Every access-side consumer of get_user_groups applies the managed-domain filter feature-side, covered by tests
- [x] #5 The existing access catalog, sync and request suites pass, with any provider-side managed assertions relocated to the feature boundary rather than dropped
- [x] #6 No file under app/infrastructure/ and no file under app/modules/ is modified by this slice
- [ ] #7 mypy, ruff and the full non-smoke pytest run are green
- [x] #8 The single-user authn membership check in DirectoryMembershipBuilder._check_group_membership (desired_state.py) also composes its get_group call through policy.group_key and applies the same get-shaped domain-mismatch handling as build_platform_state_from_effective (found during planning; not named in the task description's enumerated call-site list)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SLICE 3 of TASK-76 (coordinator decisions D1, D2, D5). Planned 2026-09-04. Behaviour-bearing slice: after this, packages/access no longer relies on any managed-group behaviour from the provider, but nothing under app/infrastructure/ or app/modules/ is touched — the provider keeps _build_managed_group unused-by-the-feature until TASK-76.4 deletes it.

## Human decisions taken during planning (2026-09-04) — see task comment for full rationale

D-a. Every downstream read of a fetched DirectoryGroup's group_email is routed through policy.canonical_email(), not only the literal call sites the task description names.
D-b. Error-vs-omission split confirmed: OMIT+warn for list-shaped ops (catalog list_entitlements, discover_group_slugs, get_user_groups); ERROR (propagate) for every get-shaped op (get_group call sites, including the per-rule loop and the single-user authn check).
D-c. Policy is constructor-injected (policy: ManagedGroupPolicy) into CatalogService, DirectoryMembershipBuilder and AccessRequestService, built once per subdomain's providers.py via ManagedGroupPolicy.from_config(get_access_runtime_config()) — not derived internally from the runtime_config each service already holds.
D-d. New AC#8 folds in a call site found during planning (_check_group_membership in desired_state.py) that passes a bare slug to get_group but was not named in the task text.

## Grounding facts verified 2026-09-04

F1. list_groups(query="") already resolves to the generic _build_group mapper in the CURRENT provider (google.py: `if not query_str: map_fn = self._build_group; managed_prefix = None`), returning aliases and no domain filtering, regardless of DirectorySettings' managed_group_prefix/domain. Switching catalog/service.py and desired_state.py's discover_group_slugs from list_groups(query=prefix) to list_groups() therefore needs ZERO infrastructure change in this slice — verified by reading google.py directly, not assumed from the coordinator plan's F2.

F2. Only ONE access-side consumer of get_user_groups exists: DirectoryMembershipBuilder.build_user_state_from_effective (desired_state.py). Grep-confirmed across app/packages/access/**. Satisfies the task's "identify every consumer" instruction.

F3. Every existing test fixture already builds DirectoryGroup with group_email=f"{slug}@{domain}" where domain equals the runtime config's dir_domain ("example.com" everywhere) and no aliases — so canonical_email/canonical_slug/is_managed are no-ops against every EXISTING fixture (is_managed is always True, canonical_slug always equals group_slug). This means most existing assertions keep passing unchanged; only fixtures/dicts that are literally keyed or shaped around the OLD query-based server-side filtering need restructuring (F4), and NEW tests are needed to actually exercise alias-preference, prefix-mismatch and domain-mismatch (nothing today constructs an out-of-domain or alias-bearing DirectoryGroup on the access side).

F4. catalog/test_access_catalog_service.py's `_FakeDirectory.list_groups(self, query: str)` keys a `groups_by_prefix: dict[str, OperationResult]` by the exact query string (e.g. "sg-aws-"). Since production will call list_groups() with no query, every one of that file's ~15 call sites configuring `groups_by_prefix={"sg-aws-": ...}` will silently start returning the default empty list unless the fake is restructured. test_access_mode_override_contract.py's `_FakeDirectory` and sync's FakeDirectory doubles (test_application.py, integration conftest.py) already IGNORE query when filtering client-side themselves or return the configured set unconditionally, so they need no such restructuring — only their DirectoryMembershipBuilder(...) constructor call sites need the new policy= argument (F5).

F5. DirectoryMembershipBuilder(...) is constructed directly (not via providers.py) at 6 test call sites: tests/unit/packages/access/sync/test_application.py:342,413; tests/integration/packages/access/sync/conftest.py:488; tests/integration/packages/access/sync/test_desired_state.py:89,335,485. All are positional (`DirectoryMembershipBuilder(directory)` or `DirectoryMembershipBuilder(directory_provider)`) — each needs a second positional/keyword policy argument.

F6. request/service.py's existing add_group_member/remove_group_member call-arg assertions (test_service.py:450,958,1000) already assert the CANONICAL email form ("sg-aws-admins@example.com"), identical to what policy.canonical_email() will compute for that fixture (no aliases, domain matches) — these assertions need NO change. request/service.py uses a MagicMock() directory by default in tests, so argument-shape changes (bare slug -> policy.group_key(slug)) are invisible to it except where a test asserts exact call args on get_group/get_group_members with a bare slug — none found (grep-confirmed; only add/remove_group_member call-arg assertions exist, and those already use the full email).

F7. discover_group_slugs' OperationResult failure-propagation contract (TASK-78, merged) is unchanged by this slice: the `if not list_result.is_success: return OperationResult.error(...)` branch is untouched; only the success-path mapping loop changes.

F8. AccessGroupNaming.managed_prefix (policy's own prefix field) is ORG-WIDE ("sg-"), while every prefix argument passed to policy.matches_prefix() in this slice is the PLATFORM-SCOPED config.group_prefix(platform) ("sg-aws-") — confirmed against TASK-76.2's advisory #2 point 3. Do not conflate the two.

## Production changes, by file

### 1. packages/access/catalog/service.py
- Import `from packages.access.common.group_policy import ManagedGroupPolicy` (module import, runtime use).
- `__init__` gains `policy: ManagedGroupPolicy` (positional, after `directory`); store as `self._policy`.
- `list_entitlements`: replace `self._directory.list_groups(query=prefix)` with `self._directory.list_groups()`. In the loop over `groups`: skip (continue, no log) when `not self._policy.matches_prefix(group, prefix)`; skip with a warning log (`catalog_group_outside_managed_domain`, list-shaped -> omit, D-b) when `not self._policy.is_managed(group)`; derive `slug = self._policy.canonical_slug(group)` (drop the old `.strip().lower()` — the policy already normalizes); keep the existing `slug == authn_slug.lower()` and `slug.startswith(prefix.lower())` guards unchanged, operating on the canonical slug; set `group_email=self._policy.canonical_email(group)` on the built `EntitlementEntry` (was `group.group_email`).

### 2. packages/access/catalog/providers.py
- `get_catalog_service()`: construct `policy = ManagedGroupPolicy.from_config(runtime_config)` and pass `policy=policy` into `CatalogService(...)`.

### 3. packages/access/sync/desired_state.py
- Import `ManagedGroupPolicy` (runtime use, not TYPE_CHECKING).
- `DirectoryMembershipBuilder.__init__(self, directory: DirectoryProvider, policy: ManagedGroupPolicy)`; store `self._policy`.
- `build_user_state_from_effective`: after `get_user_groups`, replace the `user_group_slugs` set comprehension with a loop that, per returned group, warns+skips (`user_group_outside_managed_domain`, list-shaped -> omit) when `not self._policy.is_managed(group)`, else adds `self._policy.canonical_slug(group)`.
- `build_platform_state_from_effective`: `authn_group_result = self._directory.get_group(self._policy.group_key(effective.authn_group_slug))`; after success, if `not self._policy.is_managed(authn_group_result.data)` return `OperationResult.error(OperationStatus.PERMANENT_ERROR, message=f"Authn group outside managed domain: {effective.authn_group_slug}", error_code="DIRECTORY_GROUP_DOMAIN_MISMATCH")` (get-shaped -> error, D-b); `authn_email = self._policy.canonical_email(authn_group_result.data)` (was `.group_email`). In the per-rule loop: `group_result = self._directory.get_group(self._policy.group_key(rule.group_slug))`; keep the existing NOT_FOUND-skip and other-error-propagate branches; after a successful, present result, if `not self._policy.is_managed(group_result.data)` return the same DIRECTORY_GROUP_DOMAIN_MISMATCH error (get-shaped, per-rule is still an explicit configured fault per D-b) — do not silently `continue`; else `email_to_rule[self._policy.canonical_email(group_result.data)] = rule` (was `.group_email`).
- `discover_group_slugs`: replace `self._directory.list_groups(query=prefix)` with `self._directory.list_groups()`; in the mapping comprehension, first filter to `self._policy.matches_prefix(group, prefix)` (silent skip — different platform, expected), then warn+skip when `not self._policy.is_managed(group)` (list-shaped -> omit), then add `self._policy.canonical_slug(group)` to `discovered`.
- `_check_group_membership` (AC#8, found during planning): `group_result = self._directory.get_group(self._policy.group_key(group_slug))`; after the existing not-found guard, add: if `not self._policy.is_managed(group)` return `OperationResult.error(OperationStatus.PERMANENT_ERROR, message=f"Group outside managed domain: {group_slug}", error_code="DIRECTORY_GROUP_DOMAIN_MISMATCH")` (get-shaped -> error); `membership_result = self._directory.check_membership(self._policy.canonical_email(group), user_email)` (was `group.group_email`).

### 4. packages/access/sync/providers.py
- `get_access_sync_coordinator()`: construct `policy = ManagedGroupPolicy.from_config(config)` (config already fetched via `get_access_runtime_config()`) and pass `policy=policy` into `DirectoryMembershipBuilder(directory=get_directory_provider(), policy=policy)`.

### 5. packages/access/request/service.py
- Import `ManagedGroupPolicy` (runtime use).
- `__init__` gains `policy: ManagedGroupPolicy` (after `runtime_config`); store `self._policy`.
- `submit_request`: `group_result = self._directory.get_group(self._policy.group_key(group_slug))`; keep the existing NOT_FOUND handling; after `directory_group = group_result.data`, add a domain check — if `not self._policy.is_managed(directory_group)` return `OperationResult.error(OperationStatus.PERMANENT_ERROR, message=f"Group outside managed domain: {group_slug}", error_code="DIRECTORY_GROUP_DOMAIN_MISMATCH")` (get-shaped -> error); compute `canonical_email = self._policy.canonical_email(directory_group)` once, and use it in place of every subsequent `directory_group.group_email` read: the `check_membership` call, the delegated-actor `get_group_members` call, the `AccessRequest(... group_email=canonical_email ...)` construction, and both `add_group_member`/`remove_group_member` calls (D-a). Keep the existing `if not directory_group.group_email:` provider-invariant guard unchanged (it is a data-presence check, not a policy decision) — it runs before `canonical_email` is computed. Do NOT touch the later `request.group_email` reads (lines ~545,547,808,810) — those read the value already persisted on the `AccessRequest` domain object from a prior `submit_request` call, which is already canonical by construction; they are untouched.
- `resolve_approver_candidates(...)` call: pass `policy=self._policy` (new argument, see file 7).

### 6. packages/access/request/providers.py
- `get_access_request_service()`: construct `policy = ManagedGroupPolicy.from_config(get_access_runtime_config())` and pass `policy=policy` into `AccessRequestService(...)`.

### 7. packages/access/request/policies.py
- Import `ManagedGroupPolicy` (runtime use, not TYPE_CHECKING — it is called, not just typed).
- `resolve_approver_candidates(directory_group: DirectoryGroup, fallback_slug: str, directory: DirectoryProvider, policy: ManagedGroupPolicy) -> list[str]`: replace `group_key=directory_group.group_email` with `group_key=policy.canonical_email(directory_group)`; replace `group_key=fallback_slug` with `group_key=policy.group_key(fallback_slug)` (D-a covers the first; the second is the slug->key composition already named in the task text).

No file under app/infrastructure/ or app/modules/ is touched by any of the above (AC#6).

## Test changes

NEW app/tests/unit/packages/access/sync/test_desired_state.py — DirectoryMembershipBuilder currently has NO unit-level test file (only integration coverage plus indirect coverage via test_application.py). Add focused unit tests using a Protocol-conformant fake DirectoryProvider (not MagicMock) and a hand-built ManagedGroupPolicy(prefix="sg-", domain="example.com"):
| # | Case |
| 1 | build_user_state_from_effective omits an out-of-domain group from get_user_groups results (warning logged, no error) and still returns the in-domain entitlements |
| 2 | build_user_state_from_effective uses an alias-preferred canonical slug (alias in managed domain/prefix) to match against effective.sync_managed_rules(), not the raw group_slug |
| 3 | build_platform_state_from_effective returns DIRECTORY_GROUP_DOMAIN_MISMATCH when the authn group is out of domain |
| 4 | build_platform_state_from_effective returns DIRECTORY_GROUP_DOMAIN_MISMATCH when a per-rule entitlement group is out of domain (not silently skipped) |
| 5 | build_platform_state_from_effective still skips (not errors) a per-rule NOT_FOUND group, unchanged from today |
| 6 | discover_group_slugs excludes a foreign-platform group via matches_prefix even though list_groups now returns everything |
| 7 | discover_group_slugs omits (warns, does not error) an out-of-domain group that happens to match the prefix syntactically |
| 8 | discover_group_slugs still propagates an IDP failure as an error (TASK-78 contract), proven against the new no-query call |
| 9 | _check_group_membership (via build_user_state_from_effective's authn path) returns DIRECTORY_GROUP_DOMAIN_MISMATCH when the authn group is out of domain (AC#8) |
| 10 | get_group/get_group calls are asserted to receive the fully-qualified key composed by policy.group_key, never a bare slug (AC#1) |

UPDATED app/tests/unit/packages/access/catalog/test_access_catalog_service.py — restructure `_FakeDirectory`: drop `groups_by_prefix` dict-by-query, replace with a single `groups_result: OperationResult = OperationResult.success(data=[])` field returned regardless of query/limit args; mechanically update all ~15 call sites (`groups_by_prefix={"sg-aws-": X}` -> `groups_result=X`); update `make_service`/`make_group` call sites to pass `policy=ManagedGroupPolicy(prefix="sg-", domain="example.com")` (or `ManagedGroupPolicy.from_config(cfg)`). ADD new cases: canonical email/slug used in output when a group carries a managed-prefix alias; a prefix-non-matching group is excluded; an out-of-domain group is omitted with a warning (not an error) and does not fail the whole listing.

UPDATED app/tests/unit/packages/access/common/test_access_mode_override_contract.py — add `policy=` to the `CatalogService(...)` construction in `_catalog_mode`; no other change (its `_FakeDirectory.list_groups` already ignores `query`).

UPDATED app/tests/unit/packages/access/sync/test_application.py — add `policy=` to both `DirectoryMembershipBuilder(directory_provider)` call sites (lines 342, 413).

UPDATED app/tests/integration/packages/access/sync/conftest.py and test_desired_state.py — add `policy=` to all 4 `DirectoryMembershipBuilder(...)` call sites (F5); add one new integration scenario asserting the C1 "foreign-platform group excluded" case still holds now that list_groups is called with no query (client-side matches_prefix does the exclusion instead of the fake's own query-based filter); add one new scenario for get-shaped domain-mismatch propagation (mirrors unit cases 3/4 at the integration layer, per decisions/testing.md's integration-layer role).

UPDATED app/tests/unit/packages/access/request/test_service.py and test_policies.py — add `policy=` to `AccessRequestService(...)` and `resolve_approver_candidates(...)` call sites; verify (do not need to change, per F6) the existing `add_group_member`/`remove_group_member` call-arg assertions still pass. ADD one new case in test_service.py: `submit_request` returns `DIRECTORY_GROUP_DOMAIN_MISMATCH` when the resolved group is out of the configured managed domain. ADD one new case in test_policies.py: `resolve_approver_candidates` resolves owners via `policy.canonical_email` when the target group carries a managed alias, and composes `fallback_slug` through `policy.group_key`.

Keep every existing assertion that currently pins provider-side managed behaviour (there is none on the access side per TASK-76.2's F4 correction — that finding was about the INFRASTRUCTURE test suite, not packages/access) — so AC#5's "relocated rather than dropped" is satisfied by these new access-boundary tests standing alongside the unchanged existing suites, not by moving anything out of test_google.py (that relocation is TASK-76.4's job).

## AC traceability

AC#1 -> production section (group_key/policy usage in all 5 files) -> test_desired_state.py case 10, catalog new cases, request new cases.
AC#2 -> desired_state.py discover_group_slugs (F7, untouched failure branch) -> test_desired_state.py case 8.
AC#3 -> D-b applied file-by-file above -> test_desired_state.py cases 1,3,4,7; catalog omit case; request error case.
AC#4 -> F2 (single consumer), build_user_state_from_effective change -> test_desired_state.py cases 1,2.
AC#5 -> all UPDATED test files -> full suite green.
AC#6 -> git status check at merge.
AC#7 -> mypy/ruff/pytest run.
AC#8 -> _check_group_membership change -> test_desired_state.py case 9.

## Assumptions and how they were verified

A1. list_groups(query="") needs no infrastructure change today -> F1, read directly from google.py, not inferred.
A2. get_user_groups has exactly one access-side consumer -> F2, grep-verified.
A3. Existing fixtures are domain-neutral to this change (is_managed always True today) -> F3, read every fixture's DirectoryGroup construction.
A4. MagicMock-based request/service.py tests are not broken by the argument-shape change -> F6, grep for call-arg assertions found none keyed on a bare slug.
A5. Re-verify F1 before merge: if any environment or test has since configured DirectorySettings.managed_group_prefix/domain (still zero per TASK-76 coordinator's re-run instruction), list_groups(query="") could route through a different mapper than assumed. Re-run the coordinator's F2 grep at merge time.

## Blast radius and rollback

Production: 7 files across catalog/sync/request (service + providers + policies), ~110-160 LOC, one subsystem (packages/access), zero files under app/infrastructure/ or app/modules/. Runtime impact is nil while access remains disabled in every environment (coordinator F6); the only observable-if-enabled behaviour changes are the new domain-mismatch error surfaces (previously either silently passed through as if managed, since every environment's provider-level managed config is empty) and the switch from a server-side query to a full list_groups() call (F1 shows this hits the same generic mapper either way, so no data shape change — only potentially more rows fetched per call, already true of the managed path per TASK-76 coordinator's performance note). Test churn: ~10 files, mechanical for ~8 of them (constructor/call-site argument additions), substantive new coverage in 3 (new test_desired_state.py, extended test_access_catalog_service.py, extended test_service.py/test_policies.py). Single git revert restores everything; depends only on TASK-76.2 (merged).

## Size gate

~110-160 production LOC across 7 files in one subsystem (packages/access), no cross-subsystem spread, no infrastructure/modules touch. Test changes are wider (~10 files) but shallow-mechanical in most of them, matching the precedent already accepted for TASK-76.2. Comfortably inside the single-PR gate; no further decomposition.

## Alignment with the wider programme

- decisions/layers.md / feature-packages.md: no change to app/infrastructure/ or app/modules/; the feature-owned adapters boundary (packages/<feature>/adapters/) is not implicated since DirectoryProvider is a Path A portable capability, not a Path B adapter.
- decisions/migration.md: app/modules/ untouched; no overlap with TASK-25.1.6.5 (modules/provisioning/groups.py, google_directory.py deletion) — confirmed by reading that task, which touches only app/modules/ and app/integrations/google_workspace/, never packages/access.
- decisions/testing.md: new unit tests use a Protocol-conformant DirectoryProvider fake, not MagicMock, for the new DirectoryMembershipBuilder suite; existing MagicMock use in request/service.py tests is pre-existing and not introduced by this slice.
- TASK-78: discover_group_slugs' OperationResult propagation contract is read, not modified (F7).
- TASK-76.4 (next slice): this slice's is_managed/canonical_email/canonical_slug/group_key calls are exactly what stays correct once the provider stops doing any of this itself — no call site here assumes the provider will keep applying managed policy.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTED 2026-09-04. Plan followed with no deviations. 7 production files, all under app/packages/access; zero files under app/infrastructure/ or app/modules/ touched (AC#6, verified via git status).

PRODUCTION
- catalog/service.py: CatalogService gains `policy: ManagedGroupPolicy`; list_groups() is now a generic listing, with matches_prefix / is_managed / canonical_slug / canonical_email applied feature-side; EntitlementEntry carries the canonical email.
- catalog/providers.py, sync/providers.py, request/providers.py: policy built once per subdomain via ManagedGroupPolicy.from_config(runtime_config).
- sync/desired_state.py: DirectoryMembershipBuilder gains `policy`; get_group calls compose policy.group_key(slug) in build_platform_state_from_effective (authn + per-rule) and in _check_group_membership (AC#8); get_user_groups results filtered feature-side; discover_group_slugs lists generically and filters client-side; check_membership / get_group_members / get_group_members_batch keyed by canonical_email.
- request/service.py: AccessRequestService gains `policy`; get_group composed through group_key; a single canonical_email drives check_membership, the delegated-actor owner check, the persisted AccessRequest.group_email, and add/remove_group_member.
- request/policies.py: resolve_approver_candidates takes `policy`; owners resolved via canonical_email, fallback via group_key.

AC#3 DECISION (error vs omission), as planned and now implemented:
- OMIT + warning log for list-shaped operations: catalog list_entitlements (catalog_group_outside_managed_domain), sync discover_group_slugs (discover_groups_outside_managed_domain), get_user_groups (user_group_outside_managed_domain). Rationale: one stray or foreign group must never take down a whole listing or silently disable entitlement enforcement by failing discovery.
- ERROR (PERMANENT_ERROR / DIRECTORY_GROUP_DOMAIN_MISMATCH) for every get-shaped operation: build_platform_state_from_effective authn group and per-rule group, _check_group_membership, request submit_request. Rationale: an explicitly configured or explicitly requested group sitting outside the managed domain is a real configuration fault, consistent with the non-NOT_FOUND propagation already in that file.
Prefix-mismatch (a foreign-platform group) is a silent skip everywhere - it is expected, not anomalous.

AC#2: discover_group_slugs' TASK-78 failure-propagation branch is untouched; proven by test_discover_group_slugs_should_propagate_directory_failure against the new no-query call.
AC#4: get_user_groups has exactly one access-side consumer (build_user_state_from_effective); it now applies is_managed feature-side, covered by two unit tests.

TESTS
- New app/tests/unit/packages/access/sync/test_desired_state.py (pre-authored) passes: Protocol-conformant DirectoryProvider fake, alias preference, domain mismatch, composed group keys, discovery filtering and failure propagation.
- Pre-authored catalog / request / policies cases pass unchanged.
- Mechanically updated existing suites: catalog _FakeDirectory restructured from groups_by_prefix (keyed by the now-absent query) to a single groups_result; policy= added at CatalogService / DirectoryMembershipBuilder / AccessRequestService / resolve_approver_candidates call sites (unit + integration); sync fakes' get_group now accepts a fully-qualified key.
- Added one integration scenario (B5) asserting a per-rule out-of-domain group propagates DIRECTORY_GROUP_DOMAIN_MISMATCH.

EVIDENCE: `make test` green (human-run). `make lint` / `uv run ruff check .` clean. Access suites: 386 passed.

AC#7 LEFT UNCHECKED FOR HUMAN VERIFICATION: ruff and the full non-smoke pytest run are green. mypy reports one error in a touched file - packages/access/catalog/service.py `"object" has no attribute "warning"` on the pre-existing `log: object` parameter of _check_membership - confirmed PRE-EXISTING by running mypy on the stashed base revision (same error at the pre-change line number). No new mypy error is introduced by this slice; fixing that annotation is out of scope here.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-04 14:43
---
ADVISORY from TASK-76.1 planning (2026-09-04). Coordinator plan fact F4 is inaccurate (correction posted on TASK-76): the managed-group provider behaviour IS already pinned by app/tests/unit/infrastructure/directory/test_google.py, whose mock_directory_settings fixture (lines 135-142) runs the provider with managed_group_prefix='sg-' and managed_group_domain='example.com'. Managed-alias preference (line 1075), managed-domain mismatch (line 1119) and the alias-aware discovery skip (line 1108) are the exact behaviours your cut-over must reproduce at the feature boundary - read them as the specification instead of deriving one from scratch. What genuinely has no coverage is the packages/access side, so AC#4's 'existing test suites' still proves little there and your slice must add those tests.

Enabler note: DirectoryGroup.aliases (TASK-76.1) is a tuple of IDP-reported secondary addresses, strip+lower normalized, empty when the IDP has no such concept - so any feature-side alias handling must tolerate () rather than requiring a non-empty tuple.
---

author: @task-planner
created: 2026-09-04 15:32
---
ADVISORY from TASK-76.2 planning (2026-09-04). The API you cut over to is now frozen - write your call sites against exactly this.

app/packages/access/common/group_policy.py, frozen dataclass ManagedGroupPolicy(prefix, domain):
  ManagedGroupPolicy.from_config(config: AccessRuntimeConfig) -> ManagedGroupPolicy
  canonical_email(group: DirectoryGroup) -> str
  canonical_slug(group: DirectoryGroup) -> str
  is_managed(group: DirectoryGroup) -> bool
  matches_prefix(group: DirectoryGroup, prefix: str) -> bool
  group_key(slug: str) -> str
Not re-exported from packages.access.common.__init__ (which is deliberately export-free) - import the module path, as the code already does for common.naming.

FOUR THINGS THAT AFFECT YOUR SLICE:

1. is_managed and canonical_slug are evaluated on canonical_email(group), NOT on group.group_email, because that is the value the provider's domain check ran against (google.py:466-471 operates on _extract_managed_group_email's output). Do not re-derive slugs from group_email at your call sites.

2. matches_prefix DELIBERATELY DOES NOT reproduce _matches_managed_group_prefix's 'no candidates -> True' branch (google.py:311). That branch kept a group with no resolvable email in the listing; feature-side it is unreachable because both provider mappers already reject an email-less group (DIRECTORY_GROUP_EMAIL_REQUIRED, google.py:427-431). If your cut-over relocates the existing provider test for that branch, relocate it as 'a group with no email never reaches the feature', not as a policy behaviour.

3. THE PREFIX YOU PASS TO matches_prefix IS THE PLATFORM-SCOPED ONE. The policy's own prefix field is the ORG-WIDE 'sg-' (used only for alias preference); config.group_prefix(platform) is 'sg-aws-' and remains what catalog/service.py:140 and desired_state.py:219 pass as the match argument. The two are different values - coordinator D3 conflated them and has been corrected on TASK-76.

4. CONFIG IS NOW STRICT, WHICH CHANGES YOUR TEST SETUP. AccessRuntimeConfig gains a required non-empty dir_domain and rejects a blank dir_prefix or dir_domain at construction, and BundleConfigLoader now returns PERMANENT_ERROR CONFIG_NOT_CONFIGURED instead of an empty 'waiting mode' config. Any test of yours that leaned on the hollow bundle must construct a config explicitly. TASK-76.2 adds a dir_domain parameter to both make_runtime_config (tests/unit/packages/access/sync/conftest.py) and make_sync_config (tests/integration/packages/access/sync/conftest.py), defaulting to example.com - use those factories rather than hand-rolling.

Unchanged: your error-versus-omission decision (AC#3) is still yours to make and record; the policy returns a plain bool from is_managed precisely so each call site can choose.
---

created: 2026-09-04 16:46
---
PLANNING findings and human decisions (2026-09-04), recorded before the plan below.

HUMAN DECISION 1 (canonical_email scope). Every downstream read of a fetched DirectoryGroup's .group_email — not only the call sites the task text enumerates — is routed through policy.canonical_email(). This reaches request/service.py's check_membership call, the delegated-actor get_group_members owner check, event-dispatch metadata, add_group_member/remove_group_member, and the AccessRequest.group_email persisted to the store, plus request/policies.py's resolve_approver_candidates (which gains a policy: ManagedGroupPolicy parameter). Chosen for forward-safety: today (F2/F6, TASK-76 coordinator) the provider's own alias-preference is inert everywhere so this is behaviourally a no-op, but TASK-76.4 makes the provider return only the raw primary email, at which point these reads would silently stop being canonical if left unwrapped.

HUMAN DECISION 2 (error-vs-omission split, AC#3). Confirmed: OMIT with a warning log for list-shaped operations (catalog list_entitlements, sync discover_group_slugs, get_user_groups) — one stray/foreign/out-of-domain group must not take down a listing. ERROR (propagate, do not skip) for get-shaped operations — every get_group call site, including the per-rule loop inside build_platform_state_from_effective and the single-group fetch inside _check_group_membership, since each is an explicitly configured or explicitly requested group and a domain mismatch there is a real configuration fault, consistent with the existing non-NOT_FOUND propagation already in that method and with the reliability posture TASK-77/TASK-78 established in this same file.

GAP FOUND DURING PLANNING (now AC#8). DirectoryMembershipBuilder._check_group_membership (desired_state.py, used only by build_user_state_from_effective's authn check) calls self._directory.get_group(group_slug) with a bare slug — the same defect class as the enumerated call sites, but not named in the task description. Folded into this slice's scope since it is the same file/subdomain; not spun out to a sibling task.

DESIGN DECISION (constructor injection). CatalogService, DirectoryMembershipBuilder and AccessRequestService each receive policy: ManagedGroupPolicy as an explicit constructor parameter, built once per subdomain's providers.py via ManagedGroupPolicy.from_config(get_access_runtime_config()) — not derived internally from the runtime_config each service already holds. Chosen for parity: DirectoryMembershipBuilder has no runtime_config field today (only discover_group_slugs receives config per-call), so it must receive the policy directly; the same pattern is applied to all three for one consistent construction story and easier test substitution.

VERIFIED SAFE: list_groups(query="") already resolves to the generic _build_group mapper in the current provider (google.py list_groups: `if not query_str: map_fn = self._build_group`), so switching catalog/sync discovery to an empty-query call requires zero infrastructure change in this slice — confirmed by reading app/infrastructure/directory/google.py directly, not assumed from the coordinator plan.
---
<!-- COMMENTS:END -->

---
id: TASK-76.4
title: Strip managed-group policy and settings out of infrastructure directory
status: In Progress
assignee:
  - '@me'
created_date: '2026-09-04 14:19'
updated_date: '2026-09-04 18:47'
labels:
  - layering
milestone: m-3
dependencies:
  - TASK-76.3
parent_task_id: TASK-76
priority: medium
ordinal: 151000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 4 of TASK-76, the subtractive cleanup that satisfies parent AC#1 and AC#2 (see the coordinator plan, decisions D2, D3). Infrastructure-only; safe because TASK-76.3 already moved every access consumer off this behaviour.

DELETE from app/infrastructure/directory/google.py:
- _extract_managed_group_email (269-285), _managed_group_query_prefix (286-305), _matches_managed_group_prefix (306-313), _build_managed_group (453-493).
- The _managed_group_domain and _managed_group_prefix instance attributes (constructor, 67-68).
- The strategy switch in list_groups (885-948): the method passes the caller's query straight through to the vendor and always maps with _build_group. The client-side post-filter block disappears with it.
- get_group (697-738), get_user_groups (1050-1129) and get_group_members switch to _build_group. Their docstrings must stop referring to managed groups and to DIRECTORY_MANAGED_GROUP_DOMAIN.
- The domain-completion half of _normalize_email (211-220) per D2: it strips and lowercases only, and callers pass fully-qualified keys. Check all eleven call sites (523, 614, 686, 708, 751-752, 803-804, 834-835, 1064).
- The DIRECTORY_GROUP_DOMAIN_MISMATCH error code, if nothing else emits it.

DELETE from app/infrastructure/configuration/infrastructure/directory.py: managed_group_domain, managed_group_prefix and enforce_managed_group_email, plus their docstring lines (21-22, 59-73). Update tests/unit/infrastructure/configuration/test_directory_settings.py, which asserts on all three (lines 27-28 and the defaults test).

RELOCATE the residual DirectorySettings (provider, require_startup_warmup, startup_preload_groups, cache_ttl_seconds, startup_warmup_timeout_seconds) plus get_directory_settings from app/infrastructure/configuration/infrastructure/directory.py to app/infrastructure/directory/settings.py, deleting the old home and updating importers including app/infrastructure/directory/factory.py and the settings test. decisions/configuration.md requires this migration to ride with work that already touches the domain rather than waiting for TASK-24, and forbids adding the slice to the legacy Settings aggregator. Verify before editing whether the aggregator file still exists and whether it references DirectorySettings. If this relocation turns out to pull in more importers than expected and pushes the PR past the size gate, split it into TASK-76.5 rather than shipping an oversized diff.

PROTOCOL DOCS. app/infrastructure/directory/provider.py's get_group docstring promises a canonical MANAGED group and accepts a managed-group slug. Reword to the generic contract: a fully-qualified group key. The method SET is unchanged, per the parent task's boundary.

VERIFY BEFORE MERGE. Re-run the plan's fact F2 grep (DIRECTORY_MANAGED, DIRECTORY_ENFORCE, MANAGED_GROUP across terraform/, Makefile, app/Makefile, app/pyproject.toml). If any environment has since set one of these, stop and re-assess.

TESTING. Provider unit tests asserting the generic contract: list_groups passes the query through and never full-lists as a side effect of the query shape; a group outside any particular domain maps successfully and unchanged (parent AC#5's provider half); a group with no email is a hard error with no silent success-None path; _normalize_email leaves a bare value bare. Existing access suites from TASK-76.3 must stay green untouched - that is the proof the seam moved rather than the behaviour.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 grep for _managed_group_prefix, _managed_group_domain, _managed_group_query_prefix, _matches_managed_group_prefix, _extract_managed_group_email and _build_managed_group returns zero hits under app/infrastructure/ (parent AC#1)
- [x] #2 _normalize_email no longer completes a bare value with any domain, and every internal call site is confirmed to receive fully-qualified keys
- [x] #3 list_groups applies no query-shape strategy switch and no client-side filtering; get_group, get_group_members and get_user_groups all map through the generic builder
- [x] #4 DIRECTORY_MANAGED_GROUP_DOMAIN, DIRECTORY_MANAGED_GROUP_PREFIX and DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL are deleted from DirectorySettings and from its tests, with no replacement setting created in infrastructure (parent AC#2)
- [x] #5 The residual DirectorySettings lives at app/infrastructure/directory/settings.py, the infrastructure/configuration/infrastructure/directory.py home is deleted, importers are updated, and no slice is added to the legacy Settings aggregator
- [x] #6 The DirectoryProvider Protocol docstrings describe a generic, vendor-neutral contract with no managed-group language, and its method set is unchanged
- [x] #7 The fact F2 grep across terraform, Makefile and app config is re-run at merge time and still returns zero hits
- [x] #8 Provider unit tests cover query pass-through, successful mapping of an out-of-domain group, a missing-email group as a hard error with no silent drop, and bare-value pass-through in email normalization
- [x] #9 The access suites from TASK-76.3 pass unmodified, and mypy, ruff and the full non-smoke pytest run are green
- [x] #10 The four live app/modules/ DirectoryProvider consumers enumerated in the parent plan's fact F7 (permissions/handler.py:40, reports/google_groups.py:100, dev/google.py:170-171, provisioning/users.py) are re-verified at merge time to pass fully-qualified keys, so removing the email-completion branch is a no-op for them; the verification is recorded in the task notes
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SLICE 4 of TASK-76 (coordinator decisions D2, D3, D5). Planned 2026-09-04. Subtractive/cleanup slice, infrastructure-only: TASK-76.1/76.2/76.3 are all Done and merged (commits 0db7da7a, dd578aeb, 5f79cc87 on main), so packages/access no longer relies on any managed-group behaviour from the provider (verified by direct grep below, not assumed). This slice deletes the now-unused behaviour and relocates DirectorySettings to its final home.

## Grounding verified 2026-09-04 (read directly, not inferred from the coordinator plan)

G1. All three dependency slices are Status: Done on main; this branch (feat/migrate_group_policy_settings) is even with main. app/packages/access/** call sites all pass `self._policy.group_key(slug)` into get_group and canonical_email/policy-derived values into check_membership/add_group_member/remove_group_member (grep-verified across catalog/service.py, sync/desired_state.py, request/service.py, request/policies.py) — zero bare-slug calls remain.

G2. Exact current line numbers in app/infrastructure/directory/google.py (re-grepped, supersedes the stale ranges in the task description written before 76.1-76.3 landed):
  __init__: 50-71 (constructor attrs at 67-68: self._managed_group_domain, self._managed_group_prefix)
  _normalize_email: 211-220
  _extract_managed_group_email: 269-285
  _managed_group_query_prefix: 286-305
  _matches_managed_group_prefix: 306-313
  _build_group (generic, KEPT): 420-451
  _build_managed_group (DELETE): 454-493
  get_group_members: 600-660 (uses _build_directory_member, not managed — no change needed beyond _normalize_email at 616)
  get_group: 699-731 (calls _build_managed_group at 725 — becomes _build_group)
  add_group_member: 737-790, remove_group_member: 791-821, check_membership: 822-866 (no managed logic — only _normalize_email call sites at 753-754/805-806/836-837)
  list_groups: 867-980 (the strategy-switch block, managed_prefix branch and _matches_managed_group_prefix client-filter live in 894-951)
  list_groups_with_members: 981-1046 (delegates to list_groups(query=query) at line ~1002 — no direct change, inherits the simplification automatically)
  get_user_groups: 1047-1101 (calls _build_managed_group at line ~1099 — becomes _build_group)

G3. All 14 call sites of self._normalize_email: lines 229, 242, 264 (internal, inside _extract_email/_extract_group_aliases — used for BOTH user emails and group/alias values), 525 (get_user), 616 (get_group_members), 688 (get_group_members_batch), 710 (get_group), 753-754 (add_group_member), 805-806 (remove_group_member), 836-837 (check_membership), 1066 (get_user_groups). None of these need call-site changes — only _normalize_email's own body loses the completion branch (D2). This is a strict behaviour subset (fewer inputs accepted as valid shorthand), not a call-site rewrite.

G4. DirectorySettings' current home is app/infrastructure/configuration/infrastructure/directory.py, re-exported from that package's __init__.py barrel (infrastructure/configuration/infrastructure/__init__.py) alongside DevSettings/ServerSettings/PlatformsSettings/RetrySettings. That barrel is NOT the "legacy Settings aggregator" the task description warned about — grepped the whole tree for `class Settings\b`: only `AppSettings` (infrastructure/configuration/app.py) exists; no monolithic aggregator class remains, and no `Settings().directory`-style delegation exists anywhere. The warning is moot; nothing blocks the move.

G5. PRECEDENT for the relocation target: three infrastructure services already own a co-located `settings.py` exporting their own `Get*Settings`/`get_*_settings` from their OWN package `__init__.py` rather than the configuration barrel — infrastructure/idempotency/settings.py, infrastructure/logging/settings.py (both extend InfrastructureSettings/BaseSettings and are exported from their own __init__.py), and infrastructure/slack/settings.py (SlackTransportSettings, not re-exported anywhere — imported by module path). Following the majority (idempotency/logging) shape: new file app/infrastructure/directory/settings.py, exported from app/infrastructure/directory/__init__.py (which already exports get_directory_provider, models and the Protocol — the natural place to add it), not from the configuration barrel.

G6. FULL IMPORTER LIST for infrastructure.configuration.infrastructure.directory / the barrel's DirectorySettings export (grepped exhaustively, supersedes the task description's partial list):
  Production: infrastructure/configuration/infrastructure/__init__.py (the barrel export itself — remove the two lines), infrastructure/configuration/infrastructure/directory.py (self, deleted), infrastructure/directory/factory.py (get_directory_settings at module level, DirectorySettings under TYPE_CHECKING via the barrel), infrastructure/directory/google.py (DirectorySettings via the barrel), server/lifespan.py (both DirectorySettings and get_directory_settings from the dotted module path, not the barrel).
  Tests: tests/unit/infrastructure/configuration/test_directory_settings.py (whole file, relocates), tests/unit/infrastructure/configuration/test_infra_settings_singletons.py (TestDirectorySettingsSingleton class + its import), tests/unit/infrastructure/configuration/test_settings_delegation.py (imports get_directory_settings from the barrel solely to cache_clear() it in an autouse fixture — this file has NO actual test bodies, only the fixture; a mechanical import-path fix, not a deletion). tests/unit/infrastructure/configuration/test_settings_structure.py does NOT reference Directory anything — no change needed there.

G7. app/infrastructure/directory/provider.py's "managed-group" language is NOT confined to get_group's docstring as the task description implies — grepped the whole file: 14 occurrences across get_group_members, get_group, add_group_member, remove_group_member, check_membership and get_user_groups's docstring. AC#6 already says "docstrings" (plural) and "no managed-group language", so this slice rewords all of them, not just get_group. app/infrastructure/directory/models.py:45 (DirectoryGroup's class docstring, "Canonical managed group returned by all directory providers") carries the same leftover language and is included for consistency even though no AC names it explicitly — it is the same defect class AC#6 targets.

G8. DIRECTORY_GROUP_DOMAIN_MISMATCH is NOT solely an infrastructure error code any more. TASK-76.3 landed packages/access emitting this exact string itself, feature-side, at sync/desired_state.py:153,192,308 and request/service.py:226 (grep-verified) — the feature now owns this error code as its own defect classification, independent of the infrastructure string. The task description's "delete the error code, if nothing else emits it" is therefore already answered: something else (packages/access) DOES emit it now. Only the infrastructure emission sites (google.py's _build_managed_group and the list_groups query-branch check) are removed; the string itself is not "deleted" anywhere — it continues to exist as a feature-owned error code with its own test coverage in app/tests/unit/packages/access/**, untouched by this slice.

G9. NO SIBLING-TASK CONFLICT. TASK-25.1.6.5 (To Do, depends on TASK-25.1.6.4+TASK-25.1.6.3.1, both Done) will repoint modules/provisioning/groups.py onto list_groups_with_members/get_group_members_batch. Read directly: list_groups_with_members(query=...) delegates to list_groups(query=query) (google.py ~line 1002), which after this slice always uses the generic _build_group mapper regardless of query shape. This SIMPLIFIES what TASK-25.1.6.5 will consume (one mapper, no strategy switch) rather than conflicting with it — no advisory needed beyond noting it here, since 25.1.6.5 has not started and will simply see the post-76.4 shape.

G10. F2's re-verification (zero DIRECTORY_MANAGED/DIRECTORY_ENFORCE/MANAGED_GROUP hits across terraform/, Makefile, app/Makefile, app/pyproject.toml) re-run 2026-09-04: still zero hits. F7's four app/modules/ consumers re-verified by reading the files directly: permissions/handler.py:40 get_group_members(group_key) where group_key comes from AWS_ADMIN_GROUPS (infrastructure/configuration/features/aws_ops.py:28, default ["sre-ifs@cds-snc.ca"], still no terraform/Makefile override — grep-confirmed) — a full email. reports/google_groups.py:100 get_group_members(group.group_email) — provider-returned, fully qualified. dev/google.py:170-171 get_group_members/check_membership on resolved_group_email = first_group.group_email (dev/google.py:143, from a list_groups result) — fully qualified. provisioning/users.py calls list_users() with no group key at all. All four confirmed safe for D2's strict-normalize cut; re-run this exact grep again immediately before merge (AC#7/#10).

G11. test_google.py's existing managed-path tests, read in full (supersedes both prior advisories' partial descriptions): TestListGroups has test_prefers_managed_alias_when_primary_email_uses_old_pattern (~1137, non-empty query "sg-aws-" triggering alias-aware client-filter), test_skips_groups_when_email_is_missing_for_alias_aware_discovery (~1148), test_returns_error_when_managed_group_domain_mismatches (~1182, non-empty query "name:Admins" triggering the server-side-query branch with the domain check), test_empty_query_does_not_apply_the_managed_prefix_filter (~1240), test_empty_query_accepts_a_group_outside_the_managed_domain (~1263), test_empty_query_ignores_managed_alias_preference (~1287), test_empty_query_returns_group_aliases (~1310ish), test_managed_path_skip_is_logged_and_counted (~1389, constructs its own provider with enforce_managed_group_email=False to exercise the success(None) silent-drop path). TestGetGroup (747-857) has NO managed-specific assertions — get_group's existing tests (canonical group, alias merging, malformed alias payloads) are domain-agnostic already and need no change. get_user_groups (1047-1101) has ZERO existing test coverage in this file (grep-confirmed: no "get_user_groups" or "TestGetUserGroups" anywhere in test_google.py) — its behaviour is pinned only indirectly, if at all, through packages/access's own DirectoryMembershipBuilder tests (TASK-76.3), which use a Protocol-fake DirectoryProvider, not the real GoogleDirectoryProvider. This slice must add the missing provider-level mapping tests for get_user_groups since nothing else covers the Google mapping seam for that method.

## Decisions for this slice

D-76.4-a. RELOCATION TARGET: app/infrastructure/directory/settings.py (module-local, per G5), exported from app/infrastructure/directory/__init__.py alongside the existing exports. The class keeps the name DirectorySettings and its remaining fields' env aliases (DIRECTORY_PROVIDER, DIRECTORY_REQUIRE_STARTUP_WARMUP, DIRECTORY_CACHE_TTL_SECONDS, DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS) unchanged — only managed_group_domain, managed_group_prefix and enforce_managed_group_email are dropped, per parent AC#2/D3. get_directory_settings keeps its @lru_cache(maxsize=1) singleton shape.

D-76.4-b. google.py's constructor stops taking anything managed-specific from directory_settings; it now only reads directory_settings.provider-independent fields it already needs elsewhere (none, currently — the constructor's only per-managed reads were the two deleted attrs). The `directory_settings: DirectorySettings` parameter stays (still needed nowhere else internally today, but keeping it preserves the factory's existing signature and DI shape per the infrastructure-python instructions' constructor-injection rule — removing an unused-looking parameter that the DI wiring already threads through is out of scope and would be a gratuitous signature change).

D-76.4-c. list_groups collapses to ONE mapping strategy for every query shape: always paginate with the existing bare-vs-field-operator query translation (email:{query}* heuristic, UNCHANGED — that heuristic is generic query syntax sugar, not managed-group policy) and always map with _build_group. The managed_prefix local variable, the alias-aware full-list branch, and the post-fetch _matches_managed_group_prefix filter are deleted in full. The DIRECTORY_GROUP_DOMAIN_MISMATCH early-return inside the per-item mapping loop (line ~951, `if group_result.error_code == "DIRECTORY_GROUP_DOMAIN_MISMATCH": return self._typed_error(...)`) is deleted along with it — _build_group never produces that error code, so the branch becomes dead code the moment _build_managed_group is gone.

D-76.4-d. get_group, get_user_groups switch their mapper call from _build_managed_group(...) to _build_group(...). get_group's success(None) branch (permanent_error DIRECTORY_GROUP_EMAIL_REQUIRED when group_result.data is None) is deleted along with it — _build_group's OperationResult[DirectoryGroup] never carries a None payload on success, so the `if group_result.data is None:` guard after the call becomes unreachable and is removed, not merely left in as dead code.

D-76.4-e. _normalize_email becomes strip+lower only (D2, already human-approved in the coordinator plan). Its docstring stops describing slug-to-email completion. No call site changes (G3) — this is a body-only edit.

D-76.4-f. Docstrings across google.py (list_groups, get_group, get_user_groups), provider.py (all 14 occurrences per G7) and models.py:45 are reworded to describe a generic, vendor-neutral contract: "group_key" as "a canonical group email" (no more "managed-group email" / "managed-group slug" language), matching parent AC#6. The Protocol's method SET is unchanged (NOT IN SCOPE per parent task).

## Ordered steps

STEP 1 (AC#5, #7) — new app/infrastructure/directory/settings.py. Move DirectorySettings (dropping the 3 managed fields and their alias/docstring lines) and get_directory_settings verbatim otherwise, per D-76.4-a. Update the class's "Environment Variables" docstring list to remove the two deleted DIRECTORY_MANAGED_GROUP_DOMAIN / DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL lines and the module-level Example's import path. Delete app/infrastructure/configuration/infrastructure/directory.py.

STEP 2 (AC#5) — app/infrastructure/configuration/infrastructure/__init__.py: remove the DirectorySettings/get_directory_settings import and __all__ entries (G6). app/infrastructure/directory/__init__.py: add DirectorySettings, get_directory_settings to its imports and __all__ (G5).

STEP 3 (AC#5) — update the 4 remaining importers per G6: infrastructure/directory/factory.py (both the module-level get_directory_settings import and the TYPE_CHECKING DirectorySettings import switch to infrastructure.directory.settings), infrastructure/directory/google.py (DirectorySettings import switches to infrastructure.directory.settings — note this becomes an intra-package import, google.py and settings.py are siblings under infrastructure/directory/), server/lifespan.py (both DirectorySettings and get_directory_settings switch to infrastructure.directory.settings; verify no other infrastructure.configuration.infrastructure.directory import remains via a repo-wide grep before moving to STEP 4).

STEP 4 (AC#1, #2, #3) — app/infrastructure/directory/google.py, in this order to keep each intermediate state compilable: (a) delete _extract_managed_group_email (269-285), _managed_group_query_prefix (286-305), _matches_managed_group_prefix (306-313); (b) delete _build_managed_group (454-493); (c) collapse list_groups' strategy switch per D-76.4-c; (d) switch get_group (~725) and get_user_groups (~1099) to _build_group and delete get_group's now-unreachable `data is None` branch per D-76.4-d; (e) delete the two constructor attributes (67-68) and the directory_settings-derived reads they came from; (f) strip _normalize_email's completion branch per D-76.4-e; (g) reword docstrings per D-76.4-f (google.py's own list_groups/get_group/get_user_groups docstrings only — provider.py and models.py are STEP 5).

STEP 5 (AC#6) — app/infrastructure/directory/provider.py (all 14 occurrences, G7) and app/infrastructure/directory/models.py:45 (DirectoryGroup class docstring): reword to generic "canonical group"/"group email" language. Method signatures unchanged.

STEP 6 (AC#5) — tests/unit/infrastructure/configuration/test_directory_settings.py relocates to tests/unit/infrastructure/directory/test_settings.py (matching the logging-settings precedent at tests/unit/infrastructure/logging/test_settings.py), dropping the 3 managed-field assertions from both existing test methods and updating the import path. tests/unit/infrastructure/configuration/test_infra_settings_singletons.py: delete the TestDirectorySettingsSingleton class and its now-unused import (the two other classes in that import block, PlatformsSettings/get_platforms_settings etc., stay). tests/unit/infrastructure/configuration/test_settings_delegation.py: fix the get_directory_settings import path to infrastructure.directory.settings (mechanical, the fixture behaviour is unchanged).

STEP 7 (AC#8) — app/tests/unit/infrastructure/directory/test_google.py:
  (a) mock_directory_settings fixture (135-141): drop the managed_group_domain/managed_group_prefix/enforce_managed_group_email attribute assignments — the MagicMock no longer needs them since nothing reads them.
  (b) DELETE outright (no relocation — equivalent behaviour is now pinned at the feature boundary by TASK-76.2's test_access_group_policy.py and TASK-76.3's test_desired_state.py, per the TASK-76.1 advisory already posted on this task): test_prefers_managed_alias_when_primary_email_uses_old_pattern, test_returns_error_when_managed_group_domain_mismatches, test_managed_path_skip_is_logged_and_counted.
  (c) FOLD test_skips_groups_when_email_is_missing_for_alias_aware_discovery into the existing test_unmappable_group_is_logged_and_counted case (both now exercise the identical generic path — an emailless group is skipped-and-logged regardless of query) rather than keeping a query-shaped duplicate; delete the former.
  (d) RENAME (drop "empty_query_" framing, since there is only one query-independent behaviour now) test_empty_query_does_not_apply_the_managed_prefix_filter, test_empty_query_accepts_a_group_outside_the_managed_domain, test_empty_query_ignores_managed_alias_preference, test_empty_query_returns_group_aliases to drop the "empty_query" qualifier from their names and docstrings (they now describe list_groups's only behaviour, not a query-shaped special case).
  (e) ADD new cases per AC#8's four required assertions: (i) list_groups called with a non-empty query (e.g. "sg-") that would have matched the old managed prefix asserts the SAME single-request call shape as any other non-empty query (customer/maxResults/query kwargs), proving no full-list-then-filter branch remains — pair this with an existing-shape assertion so the "no strategy switch" claim is a diff-visible regression test, not just an absence-of-behaviour claim; (ii) an out-of-domain-shaped group (any domain, since there is no domain concept left) maps successfully via get_group with unchanged fields — extend TestGetGroup rather than duplicating TestListGroups coverage, since G11 shows TestGetGroup already has no managed assumptions to remove; (iii) get_group / get_group_members returns DIRECTORY_GROUP_EMAIL_REQUIRED (not a silent success(None)) when the payload has no resolvable email, exercised via get_group since that is where the deleted branch lived; (iv) _normalize_email leaves a bare (no "@") value stripped-and-lowercased rather than completed — add directly as a class-level unit test of _normalize_email (it is a private method but already has no public seam; test it as the smallest reproducible unit per decisions/testing.md's unit-layer intent) AND as an integration-shaped assertion that get_group_members("SG-Team") is passed through to the API call as "sg-team" (not "sg-team@anything").
  (f) ADD new TestGetUserGroups class (currently absent, G11) with at minimum: returns every group the user belongs to via the generic mapper regardless of any domain shape (no filtering — the feature filters, not the provider); propagates an IDP failure; skips (with a warning, matching the existing skip/log pattern in list_groups) a group missing its provider group ID the same way _build_group already handles it elsewhere.

STEP 8 (AC#9) — run, in order: `cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'`, `uv run ruff check .`, `uv run pytest tests --ignore=tests/smoke`. Confirm `git status` shows no file outside app/infrastructure/directory/**, app/infrastructure/configuration/infrastructure/**, app/server/lifespan.py and the four listed test files (plus the new tests/unit/infrastructure/directory/test_settings.py). Confirm the access suites (tests/unit/packages/access/**, tests/integration/packages/access/**) pass unmodified.

STEP 9 (AC#7, #10) — re-run G10's grep (DIRECTORY_MANAGED, DIRECTORY_ENFORCE, MANAGED_GROUP across terraform/, Makefile, app/Makefile, app/pyproject.toml) and the four app/modules/ consumer re-verification; record the result in the Implementation Notes (not just "assumed safe").

## AC traceability

AC#1 -> STEP 4(a,b) -> grep check in STEP 8.
AC#2 -> STEP 4(e), STEP 4(f)'s docstring text -> STEP 7(a) fixture change; grep check in STEP 8.
AC#3 -> STEP 4(c,d) -> STEP 7(e)(i) new pass-through test.
AC#4 -> STEP 1, STEP 6 -> new test_settings.py assertions (defaults + env-var test drop the 3 fields).
AC#5 -> STEPS 1,2,3,6 -> STEP 8's git-status scope check.
AC#6 -> STEP 5 -> reviewed by reading provider.py/models.py after the edit (no test asserts docstring text; this is a review-verified AC).
AC#7 -> G10 -> STEP 9.
AC#8 -> STEP 7(e) -> the four new/modified cases enumerated there.
AC#9 -> STEP 8.
AC#10 -> STEP 9.

## Test matrix (decisions/testing.md — unit layer throughout; no network, Protocol-conformant where a double is needed, MagicMock only for the pre-existing google_service/mock_directory_settings fakes already in this file)

app/tests/unit/infrastructure/directory/test_settings.py (renamed from test_directory_settings.py):
| # | Case |
| 1 | defaults: provider/require_startup_warmup/startup_preload_groups/cache_ttl_seconds/startup_warmup_timeout_seconds only — no managed_group_* or enforce_managed_group_email attributes exist |
| 2 | env-var overrides for the 4 remaining fields load correctly |

app/tests/unit/infrastructure/configuration/test_infra_settings_singletons.py: TestDirectorySettingsSingleton class removed entirely; the other 4 singleton test classes untouched.

app/tests/unit/infrastructure/directory/test_google.py (deltas from G11/STEP 7):
| # | Case |
| 3 | list_groups with a non-empty query issues exactly one groups().list(...) call with the query translated the same way regardless of whether that query happens to start with a would-have-been-managed prefix (replaces the deleted alias-preference test; proves no strategy switch) |
| 4 | list_groups with an empty query behaves identically in shape to case 3 (renamed from the empty_query_* tests, now framed as "the only behaviour" rather than a special case) |
| 5 | get_group returns a canonical group whose email domain is unconstrained (no DIRECTORY_GROUP_DOMAIN_MISMATCH branch exists to reject it) |
| 6 | get_group / get_group_members / list_groups all propagate DIRECTORY_GROUP_EMAIL_REQUIRED for an email-less payload — never a silent success(None) |
| 7 | _normalize_email leaves a bare (no "@") value stripped+lowercased, not completed into an email |
| 8 | get_group_members passed a bare, unqualified group key forwards it to the API call stripped+lowercased, unchanged otherwise |
| 9 (new TestGetUserGroups) | returns every mapped group from a paginated groups.list(userKey=...) response with no domain-based exclusion |
| 10 (new TestGetUserGroups) | propagates an IDP failure |
| 11 (new TestGetUserGroups) | skips (warns, does not fail the whole call) a group missing its provider group ID, matching list_groups' existing skip/log behaviour |

Docstrings in all new/modified test methods describe observable behaviour only (decisions/testing.md + the tests-python instructions) — no reference to TASK-76, AC numbers, or "managed group" as a removed concept; a reader with no project history must be able to understand each test from its body alone.

## Assumptions and how they were verified

A1. Removing the constructor's two managed attributes is safe because nothing else in google.py reads self._managed_group_domain/self._managed_group_prefix outside the deleted methods — verified by grep across the whole file (G2/G3 enumerate every reference).
A2. D-76.4-b's decision to keep the unused-per-se directory_settings constructor parameter is deliberate, not an oversight — flagged for reviewer challenge: if the reviewer would rather narrow the constructor's dependency now that it needs none of DirectorySettings' remaining fields either, that is a larger signature change touching factory.py and every provider-construction test and is better left to a future slice; this task does not widen its diff to do it.
A3. G9's "no conflict with TASK-25.1.6.5" holds only as long as that task's implementation, when it starts, reads the post-76.4 google.py rather than an assumption carried over from planning-time — restate this in TASK-25.1.6.5 only if its implementation begins before this task closes (currently both are To Do/planned, so no advisory is posted; TASK-25.1.6.5 depends on different tasks entirely and its own plan already reads google.py directly per its notes).
A4. G10's grep and F7 module re-verification are point-in-time (2026-09-04); STEP 9 re-runs them at actual merge time, not relying on this planning-time result.

## Blast radius and rollback

Bounded to app/infrastructure/directory/** (google.py, settings.py new, provider.py docstrings, models.py one docstring line, __init__.py export), app/infrastructure/configuration/infrastructure/directory.py (deleted) and its __init__.py (export removed), app/server/lifespan.py (import path only), and 5 test files (1 relocated, 1 trimmed, 1 import-fixed, 1 substantially edited, 1 new-class-added-to-existing-file). One subsystem (infrastructure/directory + its settings), zero files under app/packages/ or app/modules/ touched. Runtime impact: nil in every environment today, because F2/G10 confirm the managed settings are unset everywhere, so _build_managed_group has been behaviourally identical to _build_group in production since before this slice existed — this change makes that equivalence permanent and explicit rather than incidental. Single git revert restores everything; depends only on TASK-76.3 (merged to main).

## Size gate

Production: ~180-220 LOC removed across google.py (four helper methods, one constructor block, one strategy-switch block, one dead branch) plus ~90 LOC relocated verbatim (settings.py) plus docstring-only edits in provider.py/models.py. One subsystem. Test changes: 1 file relocated (~35 LOC), 1 file trimmed (~15 LOC), 1 file one-line import fix, 1 file (test_google.py) with ~150-200 LOC of deletions/renames/new cases. Comfortably a subtractive, single-subsystem PR — smaller in net production LOC than any of the three preceding slices. No further decomposition.

## Alignment with the wider programme

- decisions/layers.md / decisions/feature-packages.md: completes the portable-capability split — DirectoryProvider becomes unconditionally generic (Path A, vendor-neutral), all managed-group POLICY now lives exclusively in packages/access/common (Path A consumer), matching feature-packages.md's "common/ admits types with 2+ consumers and no I/O" for ManagedGroupPolicy and layers.md's "a portable capability's Protocol is capability-shaped and vendor-neutral".
- decisions/migration.md: no app/modules/ file touched; the four live consumers (F7/G10) keep working unchanged because they already pass fully-qualified keys — this is exactly the coexistence rule 2 guarantee ("packages/ and infrastructure/ never import from modules/", and here the inverse holds: modules/ keeps consuming infrastructure/ without needing any modules/ change).
- decisions/configuration.md: DirectorySettings' relocation to infrastructure/directory/settings.py (not a central aggregator) matches "settings live with the code they configure"; managed_group_prefix/domain/enforce_managed_group_email are deleted outright per D3, not re-homed, avoiding the second-home duplication the record forbids.
- decisions/testing.md: new/modified tests use the unit layer, no network, MagicMock only for the pre-existing Google SDK double (the sanctioned substitute at this specific adapter seam per testing.md's doubles-preference-order — a Protocol fake is not applicable here since this IS the concrete adapter under test).
- decisions/outbound-clients.md / decisions/sdk-typing.md: untouched by this slice — no client-construction or classification-function change; the adapter (GoogleDirectoryProvider) keeps calling the stubbed discovery Resource directly and classifying via classify_google_error, unaffected by the mapper simplification.
- TASK-76 parent: closes AC#1, AC#2 in full; contributes the provider half of AC#4/#5 (packages/access's own suites, proven unmodified); AC#6 (all five subtasks Done) becomes satisfiable once this task and TASK-76.5 both close.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
IMPLEMENTED 2026-09-04. Task stays In Progress for human DoD verification.

WHAT CHANGED (production)
- infrastructure/directory/settings.py (NEW, git-detected as a rename of infrastructure/configuration/infrastructure/directory.py): residual DirectorySettings (provider, require_startup_warmup, startup_preload_groups, cache_ttl_seconds, startup_warmup_timeout_seconds) + get_directory_settings @lru_cache singleton. managed_group_domain/managed_group_prefix/enforce_managed_group_email deleted outright, no replacement. Docstring env-var list and Example import path updated. Old home deleted.
- infrastructure/configuration/infrastructure/__init__.py: DirectorySettings/get_directory_settings import + __all__ entries removed. infrastructure/directory/__init__.py: both now exported there (idempotency/logging precedent).
- Importers repointed: infrastructure/directory/factory.py (module-level + TYPE_CHECKING), infrastructure/directory/google.py (now an intra-package import), server/lifespan.py (via the infrastructure.directory barrel). Repo-wide grep for 'configuration.infrastructure.directory' returns zero hits.
- google.py: deleted _extract_managed_group_email, _managed_group_query_prefix, _matches_managed_group_prefix, _build_managed_group, and the two constructor attributes. list_groups now builds ONE request (empty query -> no query kwarg; non-empty -> the unchanged bare-vs-field-operator email:{q}* translation) and always maps with _build_group; the alias-aware full-list branch, the client-side prefix post-filter and the DIRECTORY_GROUP_DOMAIN_MISMATCH early-return are gone. get_group and get_user_groups map through _build_group; get_group's unreachable 'data is None' branch removed. get_user_groups now skips+warns an unmappable group (matching list_groups) instead of failing the whole lookup. _normalize_email is strip+lower only.
- DEVIATION FROM PLAN (reviewer note): the skip branches in list_groups/get_user_groups are written as 'if not group_result.is_success or group_result.data is None:' rather than dropping the None check entirely. OperationResult[T].data is typed T | None, so mypy rejects appending it without narrowing; the None arm is unreachable at runtime but required for type-safety. No behaviour difference.
- D-76.4-b honoured: the directory_settings constructor parameter is kept (now unread) to avoid a signature change rippling into factory.py and every construction test. Flagged for reviewer challenge.
- provider.py: all managed-group docstring language reworded to 'fully-qualified group email'; the sg-* note on get_user_groups dropped. Method SET unchanged. models.py DirectoryGroup docstring reworded. Zero 'managed' hits remain under app/infrastructure/directory/.

WHAT CHANGED (tests)
- tests/unit/infrastructure/directory/test_settings.py: pre-authored on this branch; TestDirectorySettingsSingleton (identity + model_config) MOVED here from tests/unit/infrastructure/configuration/test_infra_settings_singletons.py rather than deleted as STEP 6 said, so singleton coverage is preserved rather than lost. tests/unit/infrastructure/configuration/test_directory_settings.py deleted.
- test_infra_settings_singletons.py: TestDirectorySettingsSingleton + its import removed; other 4 classes untouched. test_settings_delegation.py: get_directory_settings import repointed to infrastructure.directory.settings.
- test_google.py: mock_directory_settings fixture no longer sets managed attributes. DELETED test_prefers_managed_alias_when_primary_email_uses_old_pattern, test_skips_groups_when_email_is_missing_for_alias_aware_discovery, test_returns_error_when_managed_group_domain_mismatches, test_managed_path_skip_is_logged_and_counted. RENAMED the four empty_query_* cases to drop the query-shaped framing. Two pre-existing cases (test_returns_canonical_groups_for_query, test_uses_group_alias_fields_when_standard_keys_are_missing) asserted the old full-list call shape for 'sg-'/'email:sg-*' queries; their assertions now expect the query kwarg — this is the diff-visible proof the strategy switch is gone.

TEST EVIDENCE
- cd app && uv run pytest tests --ignore=tests/smoke: green (run by the human via 'make test', exit 0). Access suites (tests/unit/packages/access/**, tests/integration/packages/access/**) pass UNMODIFIED — no access file is in the diff.
- cd app && uv run ruff check .: All checks passed.
- cd app && uv run mypy .: 96 pre-existing errors, all under app/modules/ + packages/access/sync/interactions/slack.py + infrastructure/configuration/docs_generator.py; zero in any file this task touched (verified by filtering mypy output to infrastructure/directory, server/lifespan, tests/unit/infrastructure).

AC#7 / AC#10 RE-VERIFICATION (re-run at implementation time, not carried over from planning)
- grep DIRECTORY_MANAGED|DIRECTORY_ENFORCE|MANAGED_GROUP across terraform/, Makefile, app/Makefile, app/pyproject.toml: ZERO hits.
- grep for the six deleted symbols + DIRECTORY_GROUP_DOMAIN_MISMATCH under app/infrastructure/: ZERO hits.
- The four app/modules/ consumers re-read directly: permissions/handler.py:40 get_group_members(group_key) from AWS_ADMIN_GROUPS (default ['sre-ifs@cds-snc.ca'], no terraform/Makefile override) — full email; reports/google_groups.py:100 get_group_members(group.group_email) — provider-returned; dev/google.py:170-171 operate on resolved_group_email taken from a list_groups result — provider-returned; provisioning/users.py calls list_users() with no group key. Removing the email-completion branch is a no-op for all four.

SCOPE
git status shows only: infrastructure/directory/** (google, provider, models, __init__, settings new), infrastructure/configuration/infrastructure/__init__.py (+ directory.py deleted), server/lifespan.py, and 5 test files. Nothing under app/packages/ or app/modules/.

LEFT FOR HUMAN VERIFICATION
- AC#6 is review-verified (no test asserts docstring text) — please read provider.py/models.py.
- The D-76.4-b decision to keep the now-unread directory_settings constructor parameter.
- Moving the singleton test class instead of deleting it (deviation from STEP 6).
- Task moved to Done only by a human after DoD sign-off.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-04 14:43
---
ADVISORY from TASK-76.1 planning (2026-09-04). Two items for your scope.

1. EXISTING PROVIDER TESTS TO RELOCATE, NOT RE-AUTHOR. Coordinator plan fact F4 is wrong (correction posted on TASK-76): app/tests/unit/infrastructure/directory/test_google.py already pins the managed path, because its mock_directory_settings fixture (lines 135-142) sets managed_group_prefix='sg-' and managed_group_domain='example.com'. The assertions you must move to the feature boundary or delete with the code are: managed-alias preference (line 1075), managed-domain mismatch -> DIRECTORY_GROUP_DOMAIN_MISMATCH (line 1119), alias-aware discovery skipping an email-less group (line 1108), and the empty-query generic-mapping cases (lines 1200+, which stay and become the only behaviour). The fixture's managed settings themselves must go with the settings.

2. ALIAS NORMALIZATION CHANGES UNDER YOUR D2 CUT. TASK-76.1 populates DirectoryGroup.aliases via _extract_group_aliases, which routes each alias through _normalize_email - including the bare-local-part -> {slug}@{domain} completion that D2 deletes. So removing that branch also changes how ALIASES are normalized, not just group/user keys. It is a no-op while the managed domain is empty (F2(iv)), but state it in the PR and cover it with a test: after the cut, an alias value is strip+lower only, and a bare local part stays bare. Re-run the F2 grep (DIRECTORY_MANAGED / DIRECTORY_ENFORCE / MANAGED_GROUP across terraform, Makefiles, pyproject) before merge - if any environment has set the domain, this stops being a no-op.
---

created: 2026-09-04 18:03
---
PLANNED 2026-09-04. Plan written; task stays To Do pending human review.

KEY GROUNDING CORRECTIONS made while planning (full detail in the plan's Grounding section, G1-G11):
- The task description's "verify whether the legacy Settings aggregator still exists" concern is moot: grepped the whole tree, no monolithic Settings aggregator class exists (only AppSettings, unrelated). DirectorySettings relocates to app/infrastructure/directory/settings.py, following the idempotency/logging precedent (own settings.py, exported from the service's own __init__.py), not the configuration barrel.
- DIRECTORY_GROUP_DOMAIN_MISMATCH is not solely an infrastructure error code to "delete if nothing else emits it" - TASK-76.3 already made packages/access emit this exact string itself, feature-side, as its own defect classification. Only the infrastructure emission sites are removed; the string itself continues to exist as a feature-owned error code, untouched by this slice.
- provider.py's "managed-group" docstring language is not confined to get_group as the task description implied - it appears 14 times across the Protocol file plus once on DirectoryGroup in models.py. AC#6 already says "docstrings" (plural), so the plan rewords all of them, not just get_group's.
- get_user_groups has ZERO existing test coverage in test_google.py today (grep-confirmed) - it is not a relocation target, it needs net-new provider-level tests.
- No conflict with TASK-25.1.6.5 (To Do): it consumes list_groups_with_members, which delegates to list_groups and inherits this slice's simplification automatically - no advisory needed, no shared file touched.
- Re-ran the coordinator's F2 grep (DIRECTORY_MANAGED/DIRECTORY_ENFORCE/MANAGED_GROUP across terraform/, Makefile, app/pyproject.toml) and the F7 four-consumer re-verification: both still hold as of 2026-09-04. STEP 9 re-runs both at actual merge time per AC#7/#10.

No AC changes were needed - all ten existing ACs already match the grounded scope; the plan implements them with exact line numbers and an ordered, compilable-at-each-step sequence.
---
<!-- COMMENTS:END -->

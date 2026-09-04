---
id: TASK-76.3
title: 'Cut access catalog, sync and request onto the generic DirectoryProvider path'
status: To Do
assignee: []
created_date: '2026-09-04 14:18'
updated_date: '2026-09-04 15:32'
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
- [ ] #1 catalog, sync and request obtain canonical group email, slug, prefix matching and group keys exclusively through ManagedGroupPolicy; no access-side call passes a bare slug to DirectoryProvider
- [ ] #2 sync discover_group_slugs keeps the OperationResult failure-propagation contract introduced by TASK-78, with a test proving an IDP failure still propagates rather than yielding an empty set
- [ ] #3 The error-versus-omission decision for out-of-domain groups is made per call-site shape, implemented, and recorded with its rationale in the task notes
- [ ] #4 Every access-side consumer of get_user_groups applies the managed-domain filter feature-side, covered by tests
- [ ] #5 The existing access catalog, sync and request suites pass, with any provider-side managed assertions relocated to the feature boundary rather than dropped
- [ ] #6 No file under app/infrastructure/ and no file under app/modules/ is modified by this slice
- [ ] #7 mypy, ruff and the full non-smoke pytest run are green
<!-- AC:END -->

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
<!-- COMMENTS:END -->

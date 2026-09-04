---
id: TASK-76.1
title: Expose IDP-reported group aliases on the canonical DirectoryGroup model
status: To Do
assignee: []
created_date: '2026-09-04 14:17'
updated_date: '2026-09-04 14:42'
labels:
  - layering
milestone: m-3
dependencies: []
parent_task_id: TASK-76
priority: medium
ordinal: 148000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of TASK-76 (see the coordinator plan, decision D1). Infrastructure-only, purely additive, no behaviour change.

WHY. packages/access cannot own managed-group policy while the only alias information the IDP returns is consumed and discarded inside GoogleDirectoryProvider. _extract_managed_group_email (app/infrastructure/directory/google.py:269-285) picks a canonical email by preferring an alias with the managed prefix, and _matches_managed_group_prefix (google.py:306-313) filters on aliases - both read _extract_group_aliases (google.py:~255-266) and neither surfaces the aliases to the caller. DirectoryGroup (app/infrastructure/directory/models.py) has no aliases field, so a feature-side policy is impossible to write without this slice.

FACT vs POLICY. The aliases a directory reports for a group are a vendor-neutral FACT about the group, in the same class as name and description, and belong on the canonical model. Which alias is canonical, which prefix is managed and which domain is authoritative are POLICY and are NOT part of this slice - they stay where they are until TASK-76.3 cuts over and TASK-76.4 deletes them.

SCOPE.
- Add aliases: tuple[str, ...] = () to the frozen DirectoryGroup dataclass. Tuple, not list, to keep the dataclass hashable and immutable per the type-model boundary rules.
- Populate it in BOTH _build_group (google.py:420-451) and _build_managed_group (google.py:453-493), reusing the existing _extract_group_aliases helper. Normalization must match what the existing alias logic assumes (stripped, lowercased) so TASK-76.2's policy sees the same values the provider does today.
- Add the missing provider mapping unit tests (per TASK-76 plan fact F4 there are none today).

NOT IN SCOPE. Any change to DirectoryProvider's method set; any removal or relocation of managed-group policy or settings; any change in packages/access.

TESTING (decisions/testing.md). Unit tests over recorded Google group payload dicts at the mapper seam: a group with aliases populates them in order; a group with no aliases yields an empty tuple; existing group fields are unchanged. No network, no moto needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 DirectoryGroup carries aliases as an immutable tuple field defaulting to empty, and remains a frozen dataclass
- [ ] #2 Both _build_group and _build_managed_group populate aliases from the provider payload using the existing extraction helper, with identical normalization to the current alias logic
- [ ] #3 Unit tests at the mapper seam cover a group with aliases, a group without aliases, and confirm no other DirectoryGroup field changed
- [ ] #4 No managed-group policy or setting is added, removed or relocated by this slice, and no file under app/packages/ is modified
- [ ] #5 mypy, ruff and the full non-smoke pytest run are green
- [ ] #6 DirectoryGroup.aliases is documented as a vendor-neutral fact with its per-IDP source named (Google aliases[] + nonEditableAliases[]; Entra proxyAddresses minus the primary SMTP: entry; empty tuple when the IDP has no such concept) and stated never to repeat group_email, so a future entra_id provider inherits a stated obligation rather than a Google-shaped signature
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SLICE 1 of TASK-76 (coordinator decision D1). Planned 2026-09-04. Infrastructure-only, purely additive, no production behaviour change.

## R1 - Cross-IDP research (raised during planning: is "aliases" a Google-only signature?)

The objection was that a shared infrastructure capability must not adopt a single vendor's shape and then have business features build on it. Verified against vendor docs 2026-09-04:

- GOOGLE (Admin SDK Directory, Group resource): aliases[] - "Read-only. The list of a group's alias email addresses"; nonEditableAliases[] - "the group's non-editable alias email addresses that are outside of the account's primary domain or subdomains. These are functioning email addresses used by the group". Source: developers.google.com/workspace/admin/directory/reference/rest/v1/groups
- MICROSOFT ENTRA ID (Graph v1.0, group resource) - the DIRECTORY_PROVIDER='entra_id' branch already declared in DirectorySettings: proxyAddresses, String collection, "Email addresses for the group that direct to the same group mailbox. For example: [\"SMTP: bob@contoso.com\", \"smtp: bob@sales.contoso.com\"]". Returned by default, read-only, not nullable. Uppercase 'SMTP:' marks the primary (what the 'mail' property reports); lowercase 'smtp:' entries are the secondaries. Source: learn.microsoft.com/en-us/graph/api/resources/group

CONCLUSION: 'additional email addresses that route to this group' is a cross-vendor directory FACT, not a Google artefact, so a single vendor-neutral field on the canonical model is safe. Per-provider mapping obligation:
- Google -> aliases[] + nonEditableAliases[]
- Entra -> proxyAddresses, dropping the uppercase 'SMTP:' primary and stripping the scheme prefix
- An IDP with no such concept (Okta groups carry no mail aliases) -> the empty default

DOWNSTREAM IMPACT IF A PROVIDER CANNOT SUPPLY IT: the field defaults to (), and TASK-76.2's ManagedGroupPolicy then sees only the primary email - which is exactly the behaviour that provider would have had regardless. No consumer may treat a non-empty aliases tuple as required. That obligation is written into the model docstring rather than left to be inferred, so a future entra_id provider inherits a stated contract.

## Decisions for this slice

D-76.1-a. ONE MERGED FIELD, not two: aliases: tuple[str, ...] = (). Google's two lists are merged exactly as _extract_group_aliases already merges them. No consumer distinguishes them - TASK-76.2's policy filters by prefix AND domain, which already excludes the nonEditableAliases domain-mirrors - and Entra's proxyAddresses has no equivalent split. A separate non_editable_aliases field would be a Google-shaped field with zero consumers, i.e. precisely the coupling R1 was asked to avoid.

D-76.1-b. CONTRACT: aliases holds SECONDARY addresses only; group_email is never repeated in the tuple. True for Google by construction (aliases[] excludes the primary); stated explicitly so the Entra mapping knows to drop the uppercase SMTP: entry.

D-76.1-c. NORMALIZATION UNCHANGED (human-confirmed during planning). _extract_group_aliases keeps routing through _normalize_email, including its bare-local-part -> {slug}@{domain} completion that TASK-76.4/D2 deletes. Per coordinator fact F2(iv) that branch is dead code (managed domain is empty in every environment), so alias values are strip+lower in practice. Honours AC#2's 'identical normalization'.

D-76.1-d. Tuple, not list or frozenset: keeps DirectoryGroup frozen-hashable and preserves IDP-reported order, which TASK-76.2's alias-preference policy iterates deterministically.

## Grounding facts verified 2026-09-04

F-a. CORRECTION TO COORDINATOR FACT F4. TASK-76's plan states no existing tests cover the managed-group provider logic. That is wrong. app/tests/unit/infrastructure/directory/test_google.py (1755 lines) exercises it directly: the mock_directory_settings fixture (lines 135-142) sets managed_group_prefix='sg-' and managed_group_domain='example.com', and there are tests for managed-alias preference (line 1075), domain mismatch (line 1119), alias-aware discovery skips (line 1108) and generic empty-query mapping (line 1200+). Consequences: (i) this slice must UPDATE an existing assertion, not only add new ones; (ii) TASK-76.3/76.4 must RELOCATE these assertions to the feature boundary rather than author characterization tests from scratch. Correction posted as a comment on TASK-76.

F-b. FOUR MAPPER CALL SITES, all inside app/infrastructure/directory/google.py: get_group -> _build_managed_group (723); list_groups -> map_fn, which is _build_group on the empty-query path (895) and _build_managed_group otherwise (921), applied at 947; get_user_groups -> _build_managed_group (1097). Both mappers construct DirectoryGroup at 443 and 482 respectively. Populating both mappers therefore covers every path.

F-c. NO OTHER DirectoryGroup PRODUCER EXISTS. grep 'DirectoryGroup(' finds constructions only in google.py (2) and test files (9). infrastructure/directory/ contains no entra_id implementation yet (files: __init__.py, factory.py, google.py, models.py, provider.py). Nothing under app/packages/ or app/modules/ constructs one.

F-d. NO SERIALIZATION OR PERSISTENCE OF DirectoryGroup. No asdict/model_dump/store write of the dataclass exists, so an added field cannot break a stored shape or a cache key.

F-e. ALL TEST CONSTRUCTIONS USE KEYWORD ARGUMENTS, so an appended defaulted field breaks none of them. Only one test asserts full DirectoryGroup equality against a payload that carries aliases: test_google.py:1075 test_prefers_managed_alias_when_primary_email_uses_old_pattern. test_google.py:1224 uses the same alias payload but asserts only group_email/group_slug, so it is unaffected.

F-f. NO CONFLICT WITH THE OPEN 25.1.6 CHAIN. TASK-25.1.6.5 is the only sibling still To Do that touches Directory; its scope is modules/provisioning/groups.py, deletion of integrations/google_workspace/google_directory.py and retirement of integrations/utils/api.py::retry_request. It neither reads nor constructs DirectoryGroup mappers. Nothing in this slice affects decisions/sdk-typing.md convergence: the mappers already take dict[str, Any] from the stub-typed discovery Resource and this slice adds no vendor type to any signature.

## Ordered steps

STEP 1 (AC#1, AC#6) - app/infrastructure/directory/models.py, DirectoryGroup (line 44).
Add 'aliases: tuple[str, ...] = ()' as the last field so every existing keyword construction stays valid. Extend the class docstring with the vendor-neutral contract from R1/D-76.1-b: secondary routing addresses reported by the IDP, never including group_email, empty when the provider has no such concept, with the Google and Entra source properties named. Dataclass stays frozen.

STEP 2 (AC#2) - app/infrastructure/directory/google.py.
In _build_group (443) and _build_managed_group (482), pass aliases=tuple(self._extract_group_aliases(item)). Reuse _extract_group_aliases (253-266) untouched, so ordering, dedup and normalization are byte-identical to what the managed policy consumes today (D-76.1-c). No other line in either mapper changes; no settings are read that were not already read.

STEP 3 (AC#3) - app/tests/unit/infrastructure/directory/test_google.py:1075.
Update test_prefers_managed_alias_when_primary_email_uses_old_pattern's expected DirectoryGroup to carry aliases=('sg-aws-finops@example.com',). This is the F-e break and the proof the managed mapper now surfaces the fact it previously consumed and discarded.

STEP 4 (AC#3) - same file, new tests (matrix below). Both mappers get seam coverage: _build_managed_group through TestGetGroup, _build_group through TestListGroups' empty-query path.

STEP 5 (AC#4, AC#5) - validation and boundary check. Run the gates; confirm git status shows changes only under app/infrastructure/directory/ and app/tests/unit/infrastructure/directory/, with nothing under app/packages/ and no settings file touched.

## Test matrix (all in app/tests/unit/infrastructure/directory/test_google.py - unit layer, no network, MagicMock discovery service already in place per decisions/testing.md)

| Case | Test | Mapper | AC |
| Happy - both Google alias lists merged in order, deduped, lowercased | TestGetGroup::test_returns_merged_group_aliases_from_both_google_alias_fields | _build_managed_group | 2,3 |
| Happy - generic path surfaces aliases too, asserted by full DirectoryGroup equality so no other field changed | TestListGroups::test_empty_query_returns_group_aliases | _build_group | 2,3 |
| Boundary - payload with no alias keys yields the empty tuple | TestGetGroup::test_returns_empty_aliases_when_payload_has_no_alias_fields | _build_managed_group | 1,3 |
| Boundary - non-list alias value and non-string entries are ignored rather than raising | TestGetGroup::test_ignores_malformed_alias_payload_values | _build_managed_group | 2,3 |
| Regression - managed alias preference still resolves canonical email AND now reports the alias | existing test at line 1075, updated | _build_managed_group | 2,3 |

No new test file is created: test_google.py is the feature-prefixed home for this seam and already carries the fixtures.

## Assumptions and how they were verified

A1. No consumer constructs DirectoryGroup positionally or relies on its field count -> grep 'DirectoryGroup(' across app/ (F-c, F-e). Re-run before merge.
A2. No stored/serialized representation of DirectoryGroup exists -> F-d. Re-run before merge.
A3. Adding a field to a model does not affect the runtime_checkable DirectoryProvider Protocol, which constrains methods, not model fields.
A4. COORDINATOR-MANDATED PRE-MERGE CHECK (TASK-76 F2): grep terraform/, app/pyproject.toml, Makefile and app/Makefile for DIRECTORY_MANAGED / DIRECTORY_ENFORCE / MANAGED_GROUP and confirm zero hits. If any environment has since set one, stop and re-assess: the managed path would no longer be inert and _extract_group_aliases' domain completion would start firing.

## Blast radius and rollback

Additive, defaulted field plus one keyword argument in two mapper call sites. No new settings, no env vars, no terraform, no CI change, no ordering constraint with any other PR. Worst case is a mis-mapped alias tuple that nothing reads yet, since the first consumer lands in TASK-76.2. A single git revert fully restores prior behaviour. Blast radius is bounded to app/infrastructure/directory/ plus one test file.

## Size gate

Approximately 6 production LOC across 2 files (models.py, google.py); roughly 70 test LOC in 1 existing test file. One subsystem, purely additive, no refactor mixed with behaviour. Comfortably inside the single-PR gate; no further decomposition needed.

## Sibling impacts (advisories posted)

- TASK-76 - F4 correction (F-a above).
- TASK-76.2 - consumes the field; contract and Entra mapping obligation recorded here.
- TASK-76.4 - must relocate the existing managed-path assertions listed in F-a to the feature boundary, and its D2 removal of _normalize_email's completion branch also changes how aliases are normalized (a no-op while the managed domain is empty).
- TASK-25.1.6.5 - no impact (F-f); no advisory needed.
<!-- SECTION:PLAN:END -->

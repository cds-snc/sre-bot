---
id: TASK-76.2
title: Introduce ManagedGroupPolicy and dir_domain in packages/access/common
status: To Do
assignee: []
created_date: '2026-09-04 14:17'
updated_date: '2026-09-04 15:47'
labels:
  - layering
milestone: m-3
dependencies:
  - TASK-76.1
parent_task_id: TASK-76
priority: medium
ordinal: 149000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of TASK-76 (see the coordinator plan, decisions D1, D3, D5). Feature-only, additive; the new policy is not yet wired into the services - TASK-76.3 does that.

WHY. Per D1 the DirectoryProvider becomes unconditionally generic and packages/access owns the managed-group policy. This slice builds that owner and its configuration so the cutover slice is a pure call-site change.

SCOPE.

1. New app/packages/access/common/group_policy.py holding a frozen dataclass ManagedGroupPolicy - a pure value object, no I/O, no infrastructure imports beyond the DirectoryGroup model. It belongs in common/ because catalog, sync and request all consume it (decisions/feature-packages.md: common/ admits types with two or more subdomain consumers and no I/O). Responsibilities, each replacing one piece of provider logic:
   - canonical_email(group) - alias preference, replacing _extract_managed_group_email (google.py:269-285). Prefers an alias whose local part starts with the managed prefix AND whose domain is the managed domain; falls back to the group's primary email.
   - canonical_slug(group) - the local part of the canonical email, replacing the slug derivation currently baked into the mappers.
   - is_managed(group) - domain enforcement, replacing the DIRECTORY_GROUP_DOMAIN_MISMATCH branch in _build_managed_group (google.py:466-471). Returns a boolean; the feature decides whether a non-match is an error or an omission (see AC below).
   - matches_prefix(group, prefix) - alias-aware prefix matching, replacing _matches_managed_group_prefix (google.py:306-313).
   - group_key(slug) - slug-to-email composition, replacing the group half of _normalize_email (google.py:211-220) per D2.
   Construct it from AccessRuntimeConfig so the prefix comes from the existing AccessGroupNaming path (dir_prefix + dir_separator) and is NOT duplicated as its own setting (D3).

2. AccessRuntimeConfig (app/packages/access/common/config/settings.py) gains dir_domain alongside dir_prefix and dir_separator, plus whatever loader/bundle schema and fixtures carry the document. Per D5 it is REQUIRED and validated non-empty at load: an empty domain is what makes group_key produce an unusable bare slug today, and access is unreleased (plan fact F6) so there is no compatibility burden in tightening this. Failing loudly at config load beats failing opaquely at the IDP call.

3. Do NOT add an AccessSettings env var for the domain, and do NOT re-home managed_group_prefix or enforce_managed_group_email - D3 deletes both. Nothing in this slice may create a second home for a value that already exists (decisions/configuration.md).

NOT IN SCOPE. Wiring the policy into catalog/sync/request (TASK-76.3). Any change under app/infrastructure/ (TASK-76.4).

TESTING (decisions/testing.md). Pure unit tests, no doubles needed for a value object. Cover: alias preference wins over primary email; alias with the right prefix but wrong domain is not preferred; no matching alias falls back to primary; is_managed rejects an out-of-domain group (this is the AC#5 feature-boundary test the parent task requires); matches_prefix hits on an alias as well as on the primary email; group_key composes slug plus domain; AccessRuntimeConfig with a missing or blank dir_domain fails validation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ManagedGroupPolicy exists in app/packages/access/common as a frozen dataclass with no I/O and no imports from app/integrations, exposing canonical email, canonical slug, managed-domain check, alias-aware prefix match and slug-to-key composition
- [ ] #2 The managed prefix is derived from the existing AccessRuntimeConfig naming (dir_prefix plus dir_separator, exposed as AccessGroupNaming.managed_prefix) and is not introduced as a new setting anywhere
- [ ] #3 AccessRuntimeConfig carries dir_domain as a required non-empty field, with loader, bundle, dev-fixture and README plumbing updated; no AccessSettings feature env var and no infrastructure setting is added for it - the only new env name is the document-assembly ACCESS_CONFIG_ENV_DIR_DOMAIN, mirroring the existing ACCESS_CONFIG_ENV_DIR_PREFIX
- [ ] #4 A DirectoryGroup whose canonical email is outside the managed domain is rejected by ManagedGroupPolicy, proven by a unit test at the feature boundary (parent AC#5)
- [ ] #5 Unit tests cover alias preference including the wrong-domain-alias case, primary-email fallback on an empty alias tuple, alias-based prefix matching, key composition, and blank prefix or domain failing validation
- [ ] #6 No file under app/infrastructure/ is modified by this slice
- [ ] #7 mypy, ruff and the full non-smoke pytest run are green
- [ ] #8 AccessRuntimeConfig rejects a blank dir_prefix or dir_domain at construction, and BundleConfigLoader returns a PERMANENT_ERROR CONFIG_NOT_CONFIGURED instead of fabricating an empty waiting-mode config, each covered by a test
- [ ] #9 The two deliberate non-ports are implemented and their rationale recorded in the notes: matches_prefix drops the provider's unreachable no-candidates-means-match branch, and group_key can never emit a bare slug
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
SLICE 2 of TASK-76 (coordinator decisions D1, D3, D5). Planned 2026-09-04. Feature-only; nothing under app/infrastructure/ is touched. The policy is built and configured here but not yet wired into catalog/sync/request - TASK-76.3 does that.

## Human decisions taken during planning (2026-09-04)

H1. ENFORCE THE REQUIREMENT IN THE TYPE, do not model "not configured" as a hollow config. Human: "if we state that for the feature to work, we need prefix, then we need the code to reflect the requirement... the feature is currently disabled, so it's best to fix as we make changes." AccessRuntimeConfig therefore validates its own invariants and an invalid instance becomes unconstructible, rather than validation living only in the JSON document model.

H2. BundleConfigLoader returns a PERMANENT_ERROR (CONFIG_NOT_CONFIGURED) instead of fabricating AccessRuntimeConfig(dir_prefix="", platforms={}). Chosen over deleting the "bundle" source outright; on review the source is KEPT permanently (see R2).

H3. AccessGroupNaming gains a derived org-wide prefix helper; coordinator D3's claim that group_prefix already yields the managed prefix is factually wrong and is corrected on TASK-76 (see F2).

H4. Single required dir_domain with strict matching. Human: "if there's a gap in the code versus the intended logic, then we fix now. we will have to take time to reassess the whole logic of the access business feature before enabling it." Multi-domain/owned-domain discovery is a NEW CAPABILITY owned by TASK-79, not a gap between code and intent, so it is not pulled in here. Recorded as assumption A3 for reviewer challenge.

H5 (review, 2026-09-04). THE CONTRACT IN ONE LINE: enabling the access feature means its required settings must be present; disabling it means the rest of the app runs without prejudice. Both halves are already load-bearing in this design - F3 proves the disabled half, and H1/H2 deliver the enabled half as a clean startup error rather than a late, opaque IDP failure.

H6 (review, 2026-09-04). NO ORGANIZATION-SPECIFIC DEFAULTS. The app is being made agnostic of the organization running it, so dir_domain gets NO default value anywhere in code, settings or schema - absent means startup error, exactly like any other required setting. Illustrative values are permitted in DOCUMENTATION (the READMEs may use cds-snc.ca as an example), but the committed dev fixture uses the neutral example.com placeholder rather than baking one organization's domain into a shipped file.

## Grounding facts verified 2026-09-04

F1. TASK-76.1 HAS LANDED. DirectoryGroup carries aliases: tuple[str, ...] = () (infrastructure/directory/models.py:44-66), populated by both _build_group (google.py:449) and _build_managed_group (google.py:490). The enabler this slice consumes exists.

F2. COORDINATOR D3 IS INACCURATE. AccessGroupNaming.group_prefix(platform) returns the PLATFORM-SCOPED prefix "sg-aws-" (naming.py:18-23), while DIRECTORY_MANAGED_GROUP_PREFIX is the ORG-WIDE "sg-" that _extract_managed_group_email applies across all platforms (google.py:277). The org-wide value has no existing accessor, so it must be derived - dir_prefix + dir_separator - not merely referenced. Still no new setting, so AC#2 holds. Correction posted on TASK-76.

F3. RUNTIME CONFIG IS ONLY LOADED BEHIND THE ENABLED GATE, which is what makes H1/H2/H5 safe for every environment. get_access_runtime_config() (common/providers.py:24) raises RuntimeError on load failure, and every caller sits behind a disabled-feature early return: sync/__init__.py:74-81, catalog/__init__.py:40, request/__init__.py:68, plus the lazily-built providers (sync/providers.py:32,63; catalog/providers.py:36,64; request/providers.py:45). jobs/scheduled_tasks.py:186 reconcile_access_sync is defined but registered nowhere - the live registration is register_background_jobs (sync/__init__.py:96), itself gated on enabled. With every ACCESS_*_ENABLED false (coordinator F6), no environment loads this config at all, so a missing dir_domain cannot affect an app that has access turned off.

F4. NO DEPLOYMENT SURFACE. grep of terraform/, Makefile and app/Makefile for ACCESS_CONFIG returns zero hits, so no SSM parameter, task definition or CI variable carries the config source, ref or any ACCESS_CONFIG_ENV_* value. Adding a required document field costs no environment migration. RE-RUN BEFORE MERGE.

F5. AccessRuntimeConfig CONSTRUCTION SITES: 8 total. Production - loaders.py:150 (_build_runtime_config) and loaders.py:204 (BundleConfigLoader). Tests - tests/unit/packages/access/sync/conftest.py:122, sync/test_application.py:320 and :403, request/test_service.py:34, request/test_policies.py:33, common/test_access_mode_override_contract.py:39. Plus the catalog and integration suites which construct through the same class under the alias AccessSyncRuntimeConfig (catalog/test_access_catalog_service.py:66,112,213,446; sync/test_providers.py:18,56) and the integration factory (tests/integration/packages/access/sync/conftest.py make_sync_config). EVERY ONE USES KEYWORD ARGUMENTS, so inserting dir_domain as a second non-defaulted field breaks no call syntactically - only the missing-value errors surface, which is the intent.

F6. DOCUMENT-SHAPED TEST PAYLOADS also need the new key: catalog/test_access_catalog_providers.py:14, catalog/test_access_catalog_service.py:163, common/test_access_runtime_config_extensions.py:10 and :41, sync/test_config.py:101 and :125 all feed dicts through the loaders.

F7. THE DEV FIXTURE AND DOCS carry the document shape: packages/access/access.local.json (referenced by packages/access/README.md:66-71 and packages/access/sync/README.md:79) and the RuntimeConfigJsonModel docstring example (loaders.py:88-107). All three must gain dir_domain or local dev breaks on the first load.

F8. PROVIDER LOGIC BEING REPRODUCED (the specification for this slice, per the TASK-76.1 advisory that the managed path IS already pinned by tests/unit/infrastructure/directory/test_google.py):
  - _extract_managed_group_email (google.py:269-285): first alias whose LOCAL PART starts with the managed prefix AND whose domain equals the managed domain; otherwise the primary email. Iterates alias order as reported.
  - _matches_managed_group_prefix (google.py:306-313): primary email or any alias starts with the prefix; returns True when there are no candidates at all.
  - _build_managed_group domain check (google.py:466-471): exact equality of the canonical email's domain against the managed domain.
  - _normalize_email group half (google.py:211-220): strip+lower, and compose {slug}@{domain} when the value has no "@".

F9 (review, 2026-09-04). ORGANIZATION-SPECIFIC DEFAULTS EXIST ELSEWHERE AND ARE OUT OF SCOPE HERE. Found while confirming H6: AccessRequestsSettings.manager_group_slug = "sg-managers" and fallback_approver_slug = "sg-org-admins" (packages/access/common/settings.py:83-84, duplicated as a default argument at request/service.py:131) bake both an organization's group names AND a literal copy of the "sg-" prefix convention into code defaults; outside access, AWS_ADMIN_GROUPS defaults to ["sre-ifs@cds-snc.ca"] (infrastructure/configuration/features/aws_ops.py:28). These are the same class of problem H6 describes but belong to no acceptance criterion here. Flagged to the human for a follow-up task rather than folded in.

## Decisions for this slice

D-76.2-a. HOME AND SHAPE. New app/packages/access/common/group_policy.py holding a frozen dataclass ManagedGroupPolicy(prefix: str, domain: str) - a pure value object: no I/O, no app.integrations import, and its only infrastructure import is the DirectoryGroup model (packages -> infrastructure is downward, decisions/layers.md). It lives in common/ because catalog, sync and request all consume it (decisions/feature-packages.md: common/ admits types with two or more subdomain consumers and no I/O). It is NOT re-exported from packages/access/common/__init__.py, which is deliberately export-free; consumers import the module path, exactly as they already do for common.naming.AccessGroupNaming.

D-76.2-b. API, fixed here because TASK-76.3 is written against it:
  from_config(config: AccessRuntimeConfig) -> ManagedGroupPolicy   # prefix = AccessGroupNaming(...).managed_prefix, domain = config.dir_domain
  canonical_email(group: DirectoryGroup) -> str
  canonical_slug(group: DirectoryGroup) -> str
  is_managed(group: DirectoryGroup) -> bool
  matches_prefix(group: DirectoryGroup, prefix: str) -> bool
  group_key(slug: str) -> str
Semantics port F8 exactly, with the deliberate exceptions in D-76.2-c. is_managed and canonical_slug are evaluated on canonical_email(group), not on group.group_email, because that is the value the provider's domain check ran against.

D-76.2-c. TWO DELIBERATE NON-PORTS, both defect corrections under coordinator D5:
  (i) matches_prefix does NOT reproduce _matches_managed_group_prefix's "no candidates -> True" branch. That branch let a group with no resolvable email survive discovery; feature-side it is unreachable, since both provider mappers already reject a group with no email (DIRECTORY_GROUP_EMAIL_REQUIRED, google.py:427-431), so every DirectoryGroup reaching the feature has a group_email. Porting it would add an unreachable branch.
  (ii) group_key never emits a bare slug. The provider's completion branch silently produced an unusable key when the domain was empty; here a blank domain is impossible by construction (D-76.2-e).

D-76.2-d. PREFIX DERIVATION (H3). AccessGroupNaming gains managed_prefix - a property returning f"{dir_prefix}{dir_separator}" (for example "sg-"), documented as the org-wide managed-group prefix as distinct from the platform-scoped group_prefix(platform). Pure derivation from existing fields; no setting is introduced anywhere, so AC#2 is satisfied by construction.

D-76.2-e. INVARIANTS LIVE IN THE TYPES (H1):
  - AccessRuntimeConfig gains dir_domain: str as a required (non-defaulted) field placed immediately after dir_prefix, and a __post_init__ that raises ValueError when dir_prefix or dir_domain is blank after stripping. Validating dir_prefix too is the explicit ask in H1 and is what turns today's hollow bundle into a compile-time-visible contradiction rather than a runtime surprise. This is boundary validation - the object is built from an external document - not defensive coding.
  - ManagedGroupPolicy.__post_init__ strips+lowercases both fields (via object.__setattr__, the standard frozen-dataclass normalization) and raises ValueError when either is blank. A blank prefix is not merely useless: "".startswith checks succeed for every alias, so an unvalidated blank would make every alias look managed.

D-76.2-f. LOADER PLUMBING:
  - RuntimeConfigJsonModel gains dir_domain: str = Field(min_length=1); the docstring example gains the key. inline_json and file_json therefore fail with CONFIG_INVALID_SHAPE when it is absent.
  - EnvConfigLoader._EnvModel gains dir_domain aliased to ACCESS_CONFIG_ENV_DIR_DOMAIN, with an explicit missing-value check mirroring the existing dir_prefix check (loaders.py:251-257) so the failure names the variable. This is a document-ASSEMBLY variable of the same class as ACCESS_CONFIG_ENV_DIR_PREFIX, not a feature setting on AccessSettings; AC#3's blanket wording is amended accordingly (see AC changes).
  - BundleConfigLoader.load returns OperationResult.error(PERMANENT_ERROR, error_code="CONFIG_NOT_CONFIGURED") naming ACCESS_CONFIG_SOURCE/ACCESS_CONFIG_REF in the message (H2). Per F3 this is only reachable when a sub-feature is enabled, so the practical meaning is "access enabled but never configured", which must fail loudly.

D-76.2-g. SINGLE DOMAIN, strict, case-insensitive equality; no subdomain matching, no domain list (H4). TASK-79 replaces this with an IDP-authoritative capability.

D-76.2-h (review). NO DEFAULT FOR dir_domain ANYWHERE (H6). Not on AccessRuntimeConfig, not on RuntimeConfigJsonModel, not on the env loader model - absent means a named startup error. packages/access/access.local.json uses "example.com"; the READMEs may show a real organization domain as an illustrative example. Any reviewer who sees a default value creep in for this field should reject it: a default here would silently route one organization's group lookups at another's directory.

## Ordered steps

STEP 1 (AC#2) - app/packages/access/common/naming.py. Add the managed_prefix property per D-76.2-d, with a one-line docstring distinguishing it from group_prefix(platform). ~5 LOC.

STEP 2 (AC#3) - app/packages/access/common/config/settings.py. Add dir_domain: str immediately after dir_prefix on AccessRuntimeConfig and the __post_init__ invariant from D-76.2-e. Update the class docstring to say the domain is the authoritative managed-group email domain and is required with no default. ~10 LOC.

STEP 3 (AC#3) - app/packages/access/common/config/loaders.py. Apply D-76.2-f: RuntimeConfigJsonModel field + docstring example, _build_runtime_config signature and pass-through, _validate_runtime_config_payload wiring, EnvConfigLoader model/check/docstring, BundleConfigLoader error return and docstring. ~30 LOC.

STEP 4 (AC#1, AC#4) - NEW app/packages/access/common/group_policy.py. Implement ManagedGroupPolicy per D-76.2-a/b/c/e. ~60 LOC including docstrings. Module docstring states that this is the feature-side owner of managed-group policy that the DirectoryProvider deliberately no longer carries - that is the one thing the code cannot show on its own.

STEP 5 (AC#3) - fixtures and docs (F7, H6). Add dir_domain to packages/access/access.local.json using example.com, to the RuntimeConfigJsonModel docstring example, and to the config samples in packages/access/README.md and packages/access/sync/README.md; note in the README source list that bundle now reports "not configured" rather than yielding an empty config, and that dir_domain is required with no default.

STEP 6 (AC#5) - new tests, per the matrix below.

STEP 7 (AC#7) - mechanical test updates: the two runtime-config factories (tests/unit/packages/access/sync/conftest.py:115, tests/integration/packages/access/sync/conftest.py make_sync_config) gain a dir_domain: str = "example.com" parameter, which covers most call sites; then the direct constructions in F5 and the document payloads in F6 get the key. Any test asserting bundle waiting-mode success is rewritten against the new error contract rather than deleted.

STEP 8 (AC#6, AC#7) - validation: cd app && uv run mypy . --exclude '(?:^|/)\.venv(?:/|$)'; uv run ruff check .; uv run pytest tests --ignore=tests/smoke. Then git status to prove nothing under app/infrastructure/ changed, and re-run F4's ACCESS_CONFIG grep.

## Test matrix (decisions/testing.md - unit layer, pure value object so no doubles, no network, no time)

NEW app/tests/unit/packages/access/common/test_access_group_policy.py (feature-prefixed name per the access naming guard at tests/unit/packages/access/test_access_test_file_naming.py):
| # | Case | AC |
| 1 | canonical_email prefers a managed-prefix alias in the managed domain over the primary email | 5 |
| 2 | alias with the managed prefix but a FOREIGN domain is not preferred; primary wins (the nonEditableAliases guard from the TASK-76.1 advisory) | 5 |
| 3 | alias in the managed domain WITHOUT the managed prefix is not preferred | 5 |
| 4 | empty aliases tuple falls back to the primary email - () is legitimate, never an error | 5 |
| 5 | first matching alias wins, asserted on a two-matching-alias payload, pinning IDP order as the tie-break | 5 |
| 6 | canonical_slug returns the local part of the CANONICAL email, not of group_email, on a payload where they differ | 1 |
| 7 | is_managed is False for a group whose canonical email is outside the domain - THE FEATURE-BOUNDARY TEST for parent AC#5 | 4 |
| 8 | is_managed is True when the primary email is out-of-domain but a managed alias is in-domain (proves it runs on the canonical value) | 4 |
| 9 | matches_prefix matches on the primary email | 5 |
| 10 | matches_prefix matches on an alias when the primary does not | 5 |
| 11 | matches_prefix is False when neither primary nor alias matches | 5 |
| 12 | group_key composes a bare slug into slug@domain, and passes through / normalizes a value that already has "@" | 5 |
| 13 | ManagedGroupPolicy with a blank domain, and with a blank prefix, each raise ValueError | 5 |
| 14 | from_config derives "sg-" from dir_prefix="sg" + dir_separator="-" and takes the domain from dir_domain, normalizing mixed case and surrounding whitespace | 2,5 |

NEW app/tests/unit/packages/access/common/test_access_runtime_config_validation.py:
| 15 | AccessRuntimeConfig with a blank or whitespace dir_domain raises ValueError | 3,5 |
| 16 | AccessRuntimeConfig with a blank dir_prefix raises ValueError | 3 |
| 17 | a fully-specified config constructs and exposes dir_domain (guards against over-strict validation) | 3 |

UPDATED app/tests/unit/packages/access/sync/test_config.py (existing home of the loader suite):
| 18 | BundleConfigLoader.load returns PERMANENT_ERROR with CONFIG_NOT_CONFIGURED - replaces the current waiting-mode success assertion at ~line 90 | 3 |
| 19 | inline_json and file_json documents missing dir_domain fail with CONFIG_INVALID_SHAPE | 3 |
| 20 | a document carrying dir_domain loads it onto AccessRuntimeConfig | 3 |
| 21 | EnvConfigLoader without ACCESS_CONFIG_ENV_DIR_DOMAIN fails naming the variable; with it set (monkeypatch.setenv, never a pyproject env block) it loads | 3 |

## AC traceability

AC#1 -> STEP 4 -> tests 6,7,12. AC#2 -> STEP 1 -> test 14. AC#3 -> STEPS 2,3,5 -> tests 15-21. AC#4 -> STEP 4 -> tests 7,8. AC#5 -> STEP 6 -> tests 1-5,9-14. AC#6 -> STEP 8 (git status). AC#7 -> STEP 8. AC#8 (bundle) -> STEP 3 -> test 18. AC#9 (non-ports) -> STEP 4 -> tests 11,12.

## Assumptions and how they were verified

A1. Tightening the config cannot break a running environment because the load is gated on the enabled flag -> F3. Re-verify before merge that no new unguarded get_access_runtime_config() call site has appeared.
A2. Inserting a second non-defaulted field is safe because every construction is keyword-based -> F5. Re-run the grep before merge.
A3. H4 is read as "single required domain now, multi-domain is TASK-79's new capability rather than a gap". FLAGGED FOR REVIEWER: if the intent was instead that multi-domain is itself the gap, this slice grows a dir_domains tuple and test 7/8 change shape - say so at plan review, not during implementation.
A4. No deployment surface carries ACCESS_CONFIG_* -> F4. Re-run before merge.
A5. Access remains disabled in every environment (coordinator F6). If any ACCESS_*_ENABLED has since been set, H1/H2 stop being free and the bundle change needs a rollout note.

## Blast radius and rollback

Bounded to app/packages/access/common/ (4 production files, one of them new), one JSON dev fixture and two READMEs. Nothing under app/infrastructure/ or app/modules/. Runtime impact is nil while the feature is disabled; the only behaviour change reachable at all is BundleConfigLoader's error return, and only for an operator who enables access without configuring it - who is today served a hollow config that would fail later and more confusingly. Test churn is wide but shallow: two factories absorb most of it. Single git revert restores everything; no data, no migration, no ordering constraint against any other PR beyond TASK-76.1, which is already merged.

## Size gate

Roughly 105 production LOC across 4 Python files plus 1 JSON fixture and 2 markdown files; one subsystem (packages/access/common); additive apart from one deliberate loader behaviour change. Test changes are ~180 new LOC in 2 new files plus one-line edits in about 12 existing files. Comfortably inside the single-PR gate on production LOC and subsystem spread; the wide-but-shallow test churn is mechanical and reviewable in one pass. No further decomposition.

## Alignment with the wider programme

- decisions/layers.md: the policy sits in packages/, imports downward into infrastructure.directory.models only, and names no vendor type. It is the feature-side owner that lets TASK-76.4 make the provider unconditionally generic.
- decisions/configuration.md: one owning class per value. dir_domain gets exactly one home (AccessRuntimeConfig); managed_group_prefix gets none, because it is derived; enforce_managed_group_email is not re-homed at all.
- decisions/sdk-typing.md and outbound-clients.md: untouched. This slice adds no vendor type to any signature and no SDK call; it consumes the canonical DirectoryGroup dataclass, which is exactly the adapter-translated domain type those records prescribe.
- decisions/migration.md / feature-packages.md: no app/modules/ file is touched and no hookimpl or entry-point is added - common/ stays a namespace of types and values, not a plugin.
- TASK-25.1.6 chain: no overlap. The only open sibling touching Directory is TASK-25.1.6.5 (modules/provisioning/groups.py, deletion of integrations/google_workspace/google_directory.py, retry_request retirement); it neither reads AccessRuntimeConfig nor constructs DirectoryGroup policy.

## Review resolutions (2026-09-04)

R1 (was open question 1) - THE dir_domain VALUE IN THE FIXTURE. Resolved by H6: packages/access/access.local.json uses "example.com" (neutral placeholder in a committed file), the READMEs may illustrate with a real organization domain such as cds-snc.ca, and NO default exists in code. A developer running locally against a real directory overrides the fixture; a missing value is an ordinary startup error, not a silent fallback.

R2 (was open question 2) - THE "bundle" SOURCE IS KEPT, no follow-up task. The question was whether a loader that can now only return an error still earns its place. It does, and more than before: "bundle" is the DEFAULT value of ACCESS_CONFIG_SOURCE, so it is precisely the code path that turns "someone enabled access without configuring it" into one named, self-explaining CONFIG_NOT_CONFIGURED error. Deleting it would force the default to file_json against a ref that does not exist, degrading that clear message into a generic CONFIG_NOT_FOUND about a missing path. The alternative is strictly worse, so this is settled rather than deferred.
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-04 14:42
---
ADVISORY from TASK-76.1 planning (2026-09-04).

The enabler you depend on is now specified. DirectoryGroup gains 'aliases: tuple[str, ...] = ()' - IDP-reported SECONDARY routing addresses, never repeating group_email, normalized strip+lower, in IDP-reported order with duplicates removed. It is populated by BOTH the generic and managed Google mappers, so ManagedGroupPolicy sees the same alias values _extract_managed_group_email and _matches_managed_group_prefix consume inside the provider today.

THREE CONSTRAINTS FOR YOUR POLICY:
1. Treat an empty tuple as legitimate, never as an error: an IDP with no alias concept (Okta) or a provider that has not implemented the mapping returns (). The policy must then fall back to the primary email, which is what today's _extract_managed_group_email does anyway when no alias matches the prefix.
2. Alias ORDER is the IDP's, and Google's merge puts editable aliases[] before nonEditableAliases[]. If your alias-preference rule needs determinism beyond 'first match wins on the provider's order', state the ordering rule explicitly in the policy rather than relying on the tuple.
3. nonEditableAliases (domain-mirror addresses outside the primary domain, e.g. the *.test-google-a.com forms) are merged into the same tuple. Your prefix+domain filter is what excludes them - a prefix-only match would let them through, which the provider's current logic also guards against by checking the domain.

Also relevant to your dir_domain work: TASK-76.1's research confirmed both major IDPs expose group aliases (Google aliases[]/nonEditableAliases[]; Entra proxyAddresses), so the policy's alias handling is portable - but the OWNED-DOMAIN question remains hand-maintained configuration until TASK-79 lands, exactly as coordinator decision D4 records.
---

author: @task-planner
created: 2026-09-04 15:32
---
PLANNED 2026-09-04. Plan written; task stays To Do pending human review.

ACCEPTANCE CRITERIA CHANGED (all were unchecked; restated in place):
- AC#2 now names AccessGroupNaming.managed_prefix, because coordinator D3 was wrong that group_prefix already yields this value - it returns the platform-scoped 'sg-aws-', not the org-wide 'sg-'. Correction posted on TASK-76.
- AC#3 reworded. It previously forbade adding ANY ACCESS_ env var, which would leave the 'env' config source structurally unable to supply a now-required field. The intent (D3) is 'no standalone AccessSettings feature setting'; ACCESS_CONFIG_ENV_DIR_DOMAIN is a document-assembly variable of the same class as the existing ACCESS_CONFIG_ENV_DIR_PREFIX. Human-approved during planning.
- AC#4 now says 'canonical email' rather than 'email', matching the provider behaviour being reproduced (the domain check runs on the alias-preferred value).
- AC#5 now names the empty-alias-tuple fallback explicitly, per the TASK-76.1 advisory.
- NEW AC#8 and AC#9 carry the two human decisions taken during planning (see below).

TWO HUMAN DECISIONS taken during planning that widen this slice slightly beyond its original description:
1. AccessRuntimeConfig enforces its own invariants (non-empty dir_prefix AND dir_domain) rather than the JSON model alone, so an invalid config becomes unconstructible. Human: 'if we state that for the feature to work, we need prefix, then we need the code to reflect the requirement... the feature is currently disabled, so it's best to fix as we make changes.'
2. Consequently BundleConfigLoader can no longer fabricate AccessRuntimeConfig(dir_prefix='', platforms={}) as 'waiting mode' and instead returns PERMANENT_ERROR CONFIG_NOT_CONFIGURED. Verified safe: the runtime config is only loaded behind each sub-feature's enabled gate (sync/__init__.py:74-81, catalog/__init__.py:40, request/__init__.py:68), so the only reachable meaning is 'access enabled but never configured', which must fail loudly.

TWO OPEN QUESTIONS are recorded at the end of the plan: the dir_domain value for the local dev fixture and READMEs, and whether the 'bundle' source should be retired entirely as a follow-up now that it can only return an error.
---

author: @task-planner
created: 2026-09-04 15:42
---
BOTH OPEN QUESTIONS RESOLVED 2026-09-04 (human review). Plan updated in place; see H5, H6, D-76.2-h, R1 and R2.

R1 - NO ORGANIZATION-SPECIFIC DEFAULTS. dir_domain gets no default anywhere in code, settings or schema: absent means an ordinary named startup error, like any other required setting. The committed dev fixture packages/access/access.local.json uses the neutral example.com; the READMEs may illustrate with a real organization domain. A default here would be worse than absent - it would silently point one organization's group lookups at another's directory.

R2 - THE 'bundle' SOURCE IS KEPT, no follow-up task filed. My question was whether a loader that can now only return an error still earns its place. It does: 'bundle' is the DEFAULT ACCESS_CONFIG_SOURCE, so it is exactly the path that turns 'access was enabled but never configured' into one named CONFIG_NOT_CONFIGURED error. Deleting it would force the default to file_json against a nonexistent ref, degrading that clear message into a generic CONFIG_NOT_FOUND about a missing path.

CONTRACT CONFIRMED (H5): enabling access requires its settings to be present; disabling it leaves the rest of the app running without prejudice. Both halves already hold in this design - plan fact F3 proves the disabled half (the runtime config is only loaded behind each sub-feature's enabled gate), and H1/H2 deliver the enabled half as a clean startup error instead of a late, opaque IDP failure.

OUT-OF-SCOPE FINDING RAISED, NOT FOLDED IN (new plan fact F9). Confirming the org-agnostic rule surfaced three organization-specific defaults that this task's ACs do not cover: AccessRequestsSettings.manager_group_slug='sg-managers' and fallback_approver_slug='sg-org-admins' (packages/access/common/settings.py:83-84, duplicated as a default argument at request/service.py:131 - these bake in both an organization's group names and a literal second copy of the 'sg-' prefix convention), and AWS_ADMIN_GROUPS=['sre-ifs@cds-snc.ca'] (infrastructure/configuration/features/aws_ops.py:28). Awaiting a decision on whether to file a follow-up task; not actioned here.
---

author: @task-planner
created: 2026-09-04 15:47
---
FOLLOW-UP FILED 2026-09-04: the out-of-scope org-specific defaults recorded as plan fact F9 are now owned by TASK-76.5 (Remove organization-specific defaults from access settings), created as a sibling slice under TASK-76 with a dependency on this task. The access half (manager_group_slug, fallback_approver_slug and its duplicated constructor default) is in that task's scope; AWS_ADMIN_GROUPS is explicitly excluded there because it is a LIVE default with no terraform override, so removing it needs a provisioning step and touches a frozen module. Nothing in TASK-76.2's own scope or ACs changes.
---
<!-- COMMENTS:END -->

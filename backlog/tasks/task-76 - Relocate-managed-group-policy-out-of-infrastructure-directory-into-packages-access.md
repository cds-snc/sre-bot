---
id: TASK-76
title: >-
  Relocate managed-group policy out of infrastructure/directory into
  packages/access
status: To Do
assignee: []
created_date: '2026-09-03 18:02'
updated_date: '2026-09-04 23:06'
labels:
  - layering
milestone: m-3
dependencies:
  - TASK-25.1.6.3
references:
  - decisions/layers.md
  - decisions/feature-packages.md
  - decisions/configuration.md
  - app/infrastructure/directory/google.py
  - app/infrastructure/configuration/infrastructure/directory.py
  - app/packages/access/catalog/service.py
  - app/packages/access/sync/desired_state.py
priority: medium
ordinal: 145000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Raised 2026-09-03 (task-planner, human-directed) while planning TASK-25.1.6.3. NOT part of the Google vendor-mirror retirement - it is a layering correction that that work exposed.

THE PROBLEM. app/infrastructure/directory/google.py::GoogleDirectoryProvider embeds access-feature policy inside a shared infrastructure capability:
- _extract_managed_group_email (google.py:158-172) prefers aliases starting with DIRECTORY_MANAGED_GROUP_PREFIX when resolving a group's canonical email.
- _managed_group_query_prefix (google.py:174-193) inspects the caller's query and, when it looks like a managed-prefix search, silently switches strategy from a server-side query to a full unfiltered list plus a client-side alias filter.
- _matches_managed_group_prefix (google.py:195-201) implements that client-side filter.
- _build_directory_group (google.py:269-311) enforces DIRECTORY_MANAGED_GROUP_DOMAIN, returning DIRECTORY_GROUP_DOMAIN_MISMATCH for any group outside it, and gates on DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL.
- The three settings backing all of this live in infrastructure/configuration/infrastructure/directory.py:59-72.

The sole beneficiary is packages/access, which is the only consumer that has managed sg-* security groups: packages/access/catalog/service.py:144 and packages/access/sync/desired_state.py:199 both call list_groups(query=prefix). Human direction (2026-09-03): 'any method in an infrastructure service should be generic; if some business feature specific logic is required afterwards, they probably should own that logic.' This also matches decisions/layers.md - a portable capability's Protocol is capability-shaped and vendor-neutral - and decisions/configuration.md's preference for partitioned, package-owned settings over infrastructure aggregators.

WHY IT IS NOT DONE IN TASK-25.1.6.3. That slice needed a generic list-all path immediately, so it takes the cheap, contained step: split the mapper into a generic _build_group and a managed _build_managed_group, leaving the managed variant in place and byte-for-byte identical. That confines its diff to app/infrastructure/directory/** and keeps packages/access untouched. Completing the relocation touches packages/access, the DirectorySettings partition and their tests - a second subsystem and a behaviour-bearing move, which the implementation-planning size gate keeps out of that PR.

SCOPE. Move the managed-group prefix/domain/alias policy and its settings into packages/access (its own settings partition per decisions/settings-singleton and the packages-python instructions), leaving GoogleDirectoryProvider generic. Decide explicitly whether packages/access filters generic list_groups results itself or supplies the policy to the provider as an injected strategy - do not simply move the branching one layer up without deciding.

PRECONDITION: TASK-25.1.6.3 must have landed the _build_group / _build_managed_group split first, since it is the seam this task extracts along.

NOT IN SCOPE: any Google vendor-mirror work; changing the DirectoryProvider Protocol's method set.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GoogleDirectoryProvider contains no managed-group prefix, alias-preference or managed-domain logic; grep for _managed_group_prefix, _managed_group_domain, _managed_group_query_prefix, _matches_managed_group_prefix and _extract_managed_group_email returns zero hits under app/infrastructure/, and _normalize_email no longer completes bare values with a group domain
- [x] #2 DIRECTORY_MANAGED_GROUP_PREFIX, DIRECTORY_MANAGED_GROUP_DOMAIN and DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL no longer exist anywhere: per plan decision D3 the prefix is derived from AccessRuntimeConfig naming rather than re-homed, the domain is owned by packages/access as AccessRuntimeConfig.dir_domain, and enforce_managed_group_email is deleted outright - with no duplicate second home created for any of them
- [x] #3 The chosen mechanism - feature-side filtering of generic results, or an injected policy strategy - is stated in the task notes with its rationale, rather than the branching simply moving up one layer
- [x] #4 packages/access/catalog, packages/access/sync and packages/access/request retain their current observable behaviour, proven by their existing test suites plus the new characterization tests the slices add (the managed path has no existing coverage - see plan fact F4)
- [x] #5 A group outside the managed domain is returned unchanged by the generic provider and rejected (or ignored) by the feature, with a test at the feature boundary rather than the infrastructure one
- [x] #6 All five subtasks TASK-76.1 through TASK-76.5 are Done and the DIRECTORY_MANAGED / MANAGED_GROUP grep across terraform, Makefile and app config returns zero hits at close
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
COORDINATOR TASK. Planned 2026-09-04. No code lands on TASK-76 itself; it holds the decisions and the slice sequence. Implementation happens in TASK-76.1 through TASK-76.4.

## Decisions taken (human-approved 2026-09-04)

D1. MECHANISM (satisfies AC#3): FEATURE-SIDE FILTERING, not an injected policy strategy.
The DirectoryProvider is a portable capability meant to serve any business feature (decisions/layers.md: a portable capability's Protocol is capability-shaped and vendor-neutral). An injected strategy would leave the branching inside infrastructure and merely rename the coupling. Instead the provider becomes unconditionally generic and packages/access owns a ManagedGroupPolicy value object.
Enabler: DirectoryGroup currently carries no aliases, so the feature cannot reproduce either alias preference (_extract_managed_group_email) or client-side alias prefix matching (_matches_managed_group_prefix) from what the Protocol returns. The model therefore gains aliases as a plain vendor-neutral FACT (what the IDP reports), while all POLICY (which alias is canonical, which prefix is managed, which domain is authoritative) moves to the feature. Adding a field to a frozen dataclass is not a change to the DirectoryProvider Protocol method set, so this stays inside the task's NOT-IN-SCOPE boundary.

D2. BARE-EMAIL COMPLETION: option (a), the provider becomes STRICT.
_normalize_email (google.py:211-220) today completes a bare local-part into an email using the managed group domain, and is applied to USER emails as well as group keys (lines 523, 751-752, 803-804, 834-835, 1064) - a group-scoped policy silently applied to user identifiers. That is exactly the leak this task exists to remove. After the cut the provider only strips/lowercases; every caller passes a fully-qualified key. Slug-to-email composition becomes a ManagedGroupPolicy responsibility on the access side. Verified safe for every live caller - see F7.

D3. SETTINGS HOMES (satisfies AC#2), per decisions/configuration.md - one env var has exactly one owning class, settings live with the code they configure, no duplication:
  - managed_group_prefix: DELETED, not moved. AccessRuntimeConfig.dir_prefix + dir_separator already produce this exact value through AccessGroupNaming.group_prefix (app/packages/access/common/naming.py:18-23). Moving it would create the second home configuration.md forbids.
  - managed_group_domain: MOVED to AccessRuntimeConfig as dir_domain, alongside dir_prefix/dir_separator - NOT to an AccessSettings env var. It is the same class of fact as dir_prefix (the org's group-naming convention) and is loaded from the same runtime document; splitting one convention across two config mechanisms is the duplication configuration.md targets. It also avoids an SSM/terraform env rename.
  - enforce_managed_group_email: DELETED outright. It defaults True, is unset everywhere, and its False branch is the silent-group-drop defect TASK-25.1.6.3 recorded as finding #4. After the cut, a group with no resolvable email is unconditionally an error.
  - The residual DirectorySettings (provider, cache_ttl_seconds, warmup fields) is relocated from infrastructure/configuration/infrastructure/directory.py to app/infrastructure/directory/settings.py in the final slice, per configuration.md's rule that settings migration rides with whatever work already touches the domain rather than waiting for TASK-24.

D4. RESEARCH OUTCOME on org-level domain ownership (asked for during planning).
Both major IDPs model the set of domains an org owns as a DIRECTORY-LEVEL RESOURCE discovered from the platform, not as application configuration: Microsoft Graph exposes a domain resource per tenant with isVerified/isDefault/isRoot/isInitial (learn.microsoft.com/en-us/graph/api/resources/domain), and Google Admin SDK Directory exposes domains.list per customer (developers.google.com/workspace/admin/directory/reference/rest/v1/domains/list). The best-practice answer is therefore that owned/primary domains are an IDP-authoritative capability, not a hand-maintained constant - and this repo is already accumulating hand-maintained copies in three places: infrastructure/configuration/features/groups.py::GROUP_DOMAIN (legacy), DIRECTORY_MANAGED_GROUP_DOMAIN (this task), and the package-local approved-participant-domain setting from TASK-74/TASK-75. Those are NOT the same concept though: TASK-74's is an ALLOW-LIST policy (which external domains may participate), while this one is an IDENTITY fact (which domain we own). Because closing this properly needs a new DirectoryProvider capability (list_domains / primary_domain) plus a decision-record amendment, and this task explicitly excludes Protocol method-set changes, it is raised as sibling TASK-79 rather than absorbed here. TASK-76 deliberately parks dir_domain as feature-owned configuration in the meantime; TASK-79 is its eventual generic replacement.

D5. DEFECT-CORRECTION POSTURE, added after the human clarified deployment status (see F6).
packages/access is unreleased. Where current provider behaviour on the managed path is a latent defect rather than a working contract, the slices CORRECT it instead of faithfully porting it. Two named corrections: (i) an empty group domain must stop producing an unusable bare-slug group key - dir_domain is validated as required non-empty by the access runtime config, failing loudly at load rather than silently at the IDP call; (ii) the silent success(None) group drop disappears with enforce_managed_group_email (D3). AC#4 is therefore read as preserving INTENDED behaviour as expressed by tests, not as bug-compatible porting.

## Grounding facts verified during planning

F1. PRECONDITION MET. The _build_group / _build_managed_group split from TASK-25.1.6.3 has landed (google.py:420-451 generic, 453-493 managed). This is the seam.
F2. THE MANAGED BRANCH IS INERT IN PRODUCTION. Re-verified 2026-09-04 by grepping terraform/, app/pyproject.toml, Makefile and app/Makefile for DIRECTORY_MANAGED / DIRECTORY_ENFORCE / MANAGED_GROUP: zero hits. managed_group_domain and managed_group_prefix default to empty string and enforce_managed_group_email defaults True. Consequences, which every slice depends on: (i) _managed_group_query_prefix always returns None today, so list_groups never takes the full-list-plus-client-filter path; (ii) _extract_managed_group_email always falls through to the primary email; (iii) _build_managed_group's domain check never rejects; (iv) _normalize_email's completion branch is DEAD CODE - with an empty domain it never fires. So _build_managed_group is observationally identical to _build_group today, and the relocation is a near-pure refactor in production terms. RE-RUN THIS GREP BEFORE EACH SLICE MERGES - if any environment has since set one of these, the risk assessment changes and the slice stops.
F3. RESOLVED BY F6. The planning-time question of whether get_group(slug) with an empty dir_domain is broken in production is answered: the path is never exercised, so it is latent-broken. D5 corrects it rather than preserving it.
F4. NO EXISTING TESTS cover the managed-group provider logic at all - coverage is limited to DirectorySettings env loading (tests/unit/infrastructure/configuration/test_directory_settings.py) and stubbed catalog/sync directory fakes. AC#4's existing suites therefore prove little on their own; each slice must add the missing characterization/behaviour tests rather than lean on them. New tests follow decisions/testing.md: unit tests with Protocol-conformant fakes for the policy and the feature services, provider mapping tests as unit tests over recorded Google payload dicts, no network, feature-boundary assertions rather than infrastructure-boundary ones (AC#5).
F5. ACCESS CONSUMERS to carry across: catalog/service.py:144 list_groups(query=prefix); sync/desired_state.py:221 list_groups(query=prefix) and :130/:155 get_group(slug); request/service.py:187 get_group(slug); request/policies.py:93/102 get_group_members(group_email or fallback_slug); provider-side get_user_groups (google.py:1097) which filters to the managed domain via _build_managed_group.
F6. DEPLOYMENT STATUS (human, 2026-09-04). packages/access is NOT enabled in any environment. It was in-development as the replacement for the frozen modules/provisioning feature, and the antipatterns found while building it are what triggered the wider rearchitecture. Consequences: (i) production risk for the access half of this work is zero, and F2's inertness is explained rather than coincidental; (ii) there is no rollout, env-migration or backward-compatibility burden for dir_domain, which strengthens D3's choice of AccessRuntimeConfig over an env var; (iii) latent defects on the access path may be corrected, not preserved (D5).
F7. LIVE MODULE CONSUMERS ARE ALREADY ON THE PROVIDER, AND ARE ALREADY SAFE FOR D2. Correction to an earlier draft of this plan, which wrongly deferred D2's production impact to future tasks: TASK-25.1.6.4 is DONE and merged, so app/modules/ consumers call DirectoryProvider today. Enumerated and verified 2026-09-04, every one already passes a fully-qualified key, so removing _normalize_email's completion branch is a no-op for all of them:
  - modules/permissions/handler.py:40 get_group_members(group_key), keys from AWS_ADMIN_GROUPS. Grep-verified: NO terraform or Makefile override exists, so the default ['sre-ifs@cds-snc.ca'] (infrastructure/configuration/features/aws_ops.py:28) is what every environment uses - a full email.
  - modules/reports/google_groups.py:100 get_group_members(group.group_email) - provider-returned, fully qualified by construction.
  - modules/dev/google.py:170-171 get_group_members / check_membership on resolved_group_email, which is first_group.group_email from a list_groups result (dev/google.py:143) - fully qualified.
  - modules/provisioning/users.py calls list_users() with no key at all.
  This is belt-and-braces on top of F2(iv): the completion branch is already dead code because the domain is empty everywhere. TASK-76.4 re-verifies this enumeration at merge time rather than trusting it.

## Size gate

Combined change spans the infrastructure model, the Google provider, two settings homes, three access subdomains and their tests - past the single-PR gate on file count and subsystem spread even though production behaviour is inert. Decomposed into four sequenced slices, each independently reviewable and green on merge, per the human's direction to use TASK-76 as coordinator. The slices stay separate despite the zero-risk finding because the gate exists for reviewability, and because each PR must be green on merge - which forbids stripping the infrastructure path before the feature owns it.

## Slice sequence

TASK-76.1 - Expose IDP group aliases on the canonical DirectoryGroup model. Infrastructure-only, purely additive, no behaviour change. Unblocks feature-side alias policy.
TASK-76.2 - Introduce ManagedGroupPolicy and dir_domain in packages/access/common. Feature-only, additive, not yet wired into the services. Carries the AC#5 feature-boundary test and D5's required-domain validation.
TASK-76.3 - Cut catalog, sync and request over to the generic provider path through ManagedGroupPolicy. The behaviour-bearing slice; carries AC#4.
TASK-76.4 - Strip the managed-group policy and its settings out of infrastructure/directory and relocate the residual DirectorySettings to its target home. Subtractive cleanup; satisfies AC#1 and AC#2, and owns the F7 re-verification of the live module consumers.

No temporary shims are required: because the provider keeps both mappers until TASK-76.4, slices 1 through 3 are additive and the old path stays live until the last slice removes it. TASK-76 is checked off and closed only once all four are done and the AC#1 grep returns zero.

## Sibling-task impacts

- TASK-25.1.6.5 (To Do) is the only open task needing an advisory: it migrates modules/provisioning/groups.py onto the batched provider surface, so its new call sites must pass fully-qualified keys and must not expect managed-domain filtering from get_user_groups. Advisory posted there.
- TASK-25.1.6.4 and TASK-22.4 are DONE. No advisory belongs on completed work; the constraints that concerned them are carried forward here as F7 and enforced by TASK-76.4's own acceptance criteria instead.
- TASK-79 (new) carries the IDP-authoritative owned-domains capability from D4.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
COORDINATOR CLOSE-OUT VERIFICATION 2026-09-04. No code landed on TASK-76 itself; all work shipped in TASK-76.1 through TASK-76.5, which are all Done. Every parent AC re-verified empirically against the merged tree rather than inferred from child completion.

AC#1 — grep across app/infrastructure/ for _managed_group_prefix, _managed_group_domain, _managed_group_query_prefix, _matches_managed_group_prefix and _extract_managed_group_email returns ZERO hits. google.py::_normalize_email (line 209-215) is now strip+lowercase only, with a docstring stating callers supply fully-qualified keys — D2's strict-provider cut is in place and the bare-value domain completion is gone.

AC#2 — grep for DIRECTORY_MANAGED / MANAGED_GROUP / ENFORCE_MANAGED across app/, terraform/, Makefile, backlog/docs and decisions/ (all .py/.tf/.toml/.md/Makefile) returns ZERO hits. Confirmed no second home was created: dir_domain lives once on AccessRuntimeConfig (packages/access/common/config/settings.py:72, with the D6 __post_init__ rejecting blank values at line 84-85); the org-wide prefix is DERIVED via AccessGroupNaming.managed_prefix (common/naming.py:19) and consumed through ManagedGroupPolicy.from_config (common/group_policy.py:49) rather than configured; enforce_managed_group_email is deleted outright with no replacement.

AC#3 — mechanism is D1, FEATURE-SIDE FILTERING, not an injected policy strategy: the provider is unconditionally generic and packages/access owns ManagedGroupPolicy (common/group_policy.py:16), a value object built from the runtime config. Rationale recorded in the plan: an injected strategy would have left the branching inside infrastructure and merely renamed the coupling, whereas decisions/layers.md requires a portable capability's Protocol to stay capability-shaped and vendor-neutral. The enabler was exposing IDP-reported aliases on DirectoryGroup as a vendor-neutral FACT (TASK-76.1) so the feature could reproduce alias preference itself.

AC#4 — full non-smoke suite green (make test, user-run 2026-09-04) with catalog, sync and request behaviour pinned by the relocated and newly added tests. Note the correction to plan fact F4 already recorded in the 14:42 comment: the managed path DID have provider-level coverage, so the slices relocated those assertions to the feature boundary rather than authoring characterization tests from scratch.

AC#5 — feature-boundary rejection is proven at the feature, not the provider: request/test_service.py:1095 (test_submit_request_should_reject_group_outside_managed_domain) and sync/test_desired_state.py:236/299/318 all assert DIRECTORY_GROUP_DOMAIN_MISMATCH, plus common/test_access_group_policy.py:82/90 covering is_managed on the canonical value including the managed-alias-rescues-foreign-primary case.

AC#6 — TASK-76.1, 76.2, 76.3, 76.4 and 76.5 all report Status: Done; the DIRECTORY_MANAGED / MANAGED_GROUP grep returns zero as recorded under AC#2. F2's standing instruction to re-run the environment grep before each merge was honoured on the final slice: zero ACCESS_* and zero DIRECTORY_MANAGED* hits in terraform/, Makefile and app/Makefile, so no environment's configuration or boot changes.

CARRIED FORWARD, not regressions: TASK-79 holds D4's IDP-authoritative owned-domains capability (list_domains / primary_domain), which eventually replaces dir_domain as feature-owned configuration; D7 keeps single-domain strict case-insensitive matching until then. TASK-25.1.6.5 keeps its advisory to pass fully-qualified keys and not expect managed-domain filtering from get_user_groups. AWS_ADMIN_GROUPS remains the one LIVE organization-specific default, deliberately excluded from TASK-76.5 because removing it needs a deployment step and its consumer is frozen under decisions/migration.md rule 1 — it still needs its own task.

LEFT FOR HUMAN DoD VERIFICATION: this task is a coordinator with no diff of its own, so closing it is a confirmation that the five child PRs together satisfy the intent. Two child decisions were explicitly flagged for reviewer challenge and remain open for review — TASK-76.2's D7 single-domain assumption, and TASK-76.5's D3 (fallback_approver_slug staying an ACCESS_REQUESTS_ env var rather than moving to AccessRuntimeConfig). Status left To Do for a human to close.
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: task-planner
created: 2026-09-04 14:20
---
PLANNED 2026-09-04. TASK-76 is now a COORDINATOR: the implementation plan holds the decisions (D1 feature-side policy, D2 strict provider keys, D3 settings homes with prefix deleted rather than moved, D4 owned-domains research, D5 defect-correction posture) and the work is decomposed into TASK-76.1 through TASK-76.4 under the single-PR size gate. Sibling TASK-79 was raised from the D4 research. Cross-task advisories were posted to TASK-25.1.6.4, TASK-25.1.6.5 and TASK-22.4. Do not implement against TASK-76 directly.
---

author: task-planner
created: 2026-09-04 14:25
---
PLAN CORRECTED 2026-09-04. An earlier draft of this plan claimed D2's production impact would land on TASK-25.1.6.4 and TASK-25.1.6.5, and advisory comments were posted to TASK-25.1.6.4 and TASK-22.4. That was wrong on two counts and the human called it out: both of those tasks are DONE, so posting planning advisories there is noise on closed work, and the TASK-22.4 sequencing advice (prefer TASK-76.4 first) was impossible since that migration had already merged. Those two comments are being reverted via git.

What the mistake actually surfaced, now folded into the plan as fact F7: because TASK-25.1.6.4 is merged, app/modules/ consumers are ALREADY on DirectoryProvider, so D2's strict-key change has live production reach today and TASK-76.4 must verify it rather than defer it. All four live call sites were enumerated and verified to pass fully-qualified keys already (AWS_ADMIN_GROUPS has no terraform override and defaults to a full email; the other three use provider-returned emails or no key at all), which is belt-and-braces on top of F2(iv) - the completion branch is dead code while the domain is empty. A new acceptance criterion on TASK-76.4 makes that re-verification a merge-time requirement.

TASK-25.1.6.5 remains To Do and keeps its advisory; it is legitimately forward-looking work.
---

created: 2026-09-04 14:42
---
PLAN FACT F4 IS INACCURATE - correction from planning TASK-76.1 (2026-09-04).

F4 states there are NO existing tests covering the managed-group provider logic. There are. app/tests/unit/infrastructure/directory/test_google.py (1755 lines) exercises the managed path directly: the mock_directory_settings fixture (lines 135-142) sets managed_group_prefix='sg-' and managed_group_domain='example.com', so the provider fixture runs with managed policy ACTIVE, unlike every deployed environment (F2). Concretely covered today: managed-alias preference (line 1075), managed-domain mismatch returning DIRECTORY_GROUP_DOMAIN_MISMATCH (line 1119), alias-aware discovery skipping a group with no email (line 1108), and the generic empty-query mapping path including the outside-the-managed-domain case (lines 1200+).

WHAT THIS CHANGES FOR THE REMAINING SLICES:
- TASK-76.3 and TASK-76.4 must RELOCATE these existing assertions to the feature boundary (AC#5), not author characterization tests from scratch as F4 implies. The behaviour is already pinned; the question is where it is pinned.
- TASK-76.1 must UPDATE an existing assertion, not only add new ones: test_google.py:1075 asserts full DirectoryGroup equality against a payload carrying aliases.
- AC#4's reliance on 'existing test suites' is stronger than F4 credited for the provider half, and unchanged (weak) for the packages/access half.

What F4 got right: there is no coverage of the managed path at the FEATURE boundary, and no coverage of DirectorySettings' managed fields beyond env loading. The gap is one of placement, not of existence.

R1 RESEARCH OUTCOME feeding D1 (from TASK-76.1 planning, human-raised): group aliases are not a Google-only concept, so putting them on the canonical model does not couple infrastructure to one IDP. Google exposes aliases[]/nonEditableAliases[]; Microsoft Graph exposes proxyAddresses ('Email addresses for the group that direct to the same group mailbox', uppercase SMTP: marking the primary); an IDP without the concept returns empty. Full citations and the per-provider mapping obligation are in TASK-76.1's plan.
---

author: @task-planner
created: 2026-09-04 15:32
---
PLAN CORRECTION AND DECISION EXTENSION from TASK-76.2 planning (2026-09-04).

D3 IS FACTUALLY WRONG ON THE PREFIX. D3 states that managed_group_prefix is 'DELETED, not moved' because 'AccessRuntimeConfig.dir_prefix + dir_separator already produce this exact value through AccessGroupNaming.group_prefix'. They do not. group_prefix(platform) returns the PLATFORM-SCOPED prefix 'sg-aws-' (app/packages/access/common/naming.py:18-23), while DIRECTORY_MANAGED_GROUP_PREFIX is the ORG-WIDE 'sg-' that _extract_managed_group_email applies across all platforms (app/infrastructure/directory/google.py:277). The org-wide value has no accessor today.

The conclusion survives, the mechanism changes: the value is still DERIVED from existing fields and still gets no setting, but TASK-76.2 must add AccessGroupNaming.managed_prefix (= dir_prefix + dir_separator) to expose it. Human-approved 2026-09-04. AC#2 on TASK-76.2 was reworded to name it.

D6 (NEW, human-approved 2026-09-04) - THE ACCESS RUNTIME CONFIG ENFORCES ITS OWN INVARIANTS. Planning TASK-76.2 surfaced that BundleConfigLoader fabricates AccessRuntimeConfig(dir_prefix='', platforms={}) as a 'waiting mode' sentinel, i.e. the feature's own config type can represent a state the feature cannot operate in. That is the same class of latent defect D5 was written for. Human direction: 'if we state that for the feature to work, we need prefix, then we need the code to reflect the requirement... the feature is currently disabled, so it's best to fix as we make changes. we will have to take time to reassess the whole logic of the access business feature before enabling it.'

So, in TASK-76.2:
- AccessRuntimeConfig gains a __post_init__ rejecting blank dir_prefix and blank dir_domain, making an unusable config unconstructible rather than merely unloadable. This is the D3 dir_domain re-homing plus a correction to the pre-existing dir_prefix gap.
- BundleConfigLoader returns PERMANENT_ERROR CONFIG_NOT_CONFIGURED instead of the hollow config. Verified safe: get_access_runtime_config() is only reached behind each sub-feature's enabled gate (sync/__init__.py:74-81, catalog/__init__.py:40, request/__init__.py:68; the only other caller, jobs/scheduled_tasks.py:186, is registered nowhere), so with every ACCESS_*_ENABLED false (F6) no environment loads this config at all.
- The 'bundle' source itself is KEPT so ACCESS_CONFIG_SOURCE values, the loader factory and the READMEs are unchanged. Whether it still earns its place once it can only error is left as an open question on TASK-76.2 rather than decided.

D7 (NEW) - MULTI-DOMAIN STAYS WITH TASK-79. D4 already parks dir_domain as feature-owned configuration. TASK-76.2 additionally confirms it as a SINGLE required domain with strict case-insensitive equality - a faithful port of google.py:466-471 - on the basis that multi-domain support is a new capability rather than a gap between code and intent. Flagged as an explicit assumption in TASK-76.2's plan for reviewer challenge.

ALSO: F4 remains inaccurate as already noted in the 14:42 comment; TASK-76.2 needs no provider-test relocation itself, but TASK-76.3 and TASK-76.4 still do.
---

author: @task-planner
created: 2026-09-04 15:46
---
NEW CHILD SLICE TASK-76.5 CREATED 2026-09-04 (human-directed, from a finding raised while planning TASK-76.2): 'Remove organization-specific defaults from access settings' (dep TASK-76.2, m-3).

WHY IT SITS UNDER TASK-76. Confirming TASK-76.2's org-agnostic rule (no default for dir_domain anywhere; absent means a named startup error) surfaced the same defect class left behind in the same package: AccessRequestsSettings.manager_group_slug='sg-managers' and fallback_approver_slug='sg-org-admins' (packages/access/common/settings.py:83-84), the second duplicated as a constructor default at request/service.py:131. Each is wrong twice - an organization's own group names presented as universal defaults, and a literal re-encoding of the 'sg-' prefix that dir_prefix + dir_separator already own, which is the same second-home duplication D3 removed for the managed-group prefix.

AC#6 AMENDED accordingly: the all-children bar now reads TASK-76.1 through TASK-76.5 rather than 76.1 through 76.4. The other five ACs are unchanged (restated verbatim, since --acceptance-criteria replaces the whole list). No plan rewrite: the slice sequence in the plan still describes the managed-group relocation itself, which TASK-76.5 does not change - it is adjacent cleanup parked here rather than a sixth step of the relocation.

DELIBERATELY EXCLUDED FROM TASK-76.5, needs its own task with a deployment step: AWS_ADMIN_GROUPS=['sre-ifs@cds-snc.ca'] (infrastructure/configuration/features/aws_ops.py:28). Same defect class, different risk - plan fact F7 already grep-verified that no terraform or Makefile override exists, so that default is what every environment actually uses today at modules/permissions/handler.py:40. Removing it without first provisioning the value breaks a live feature, and its consumer sits in app/modules/, frozen under decisions/migration.md rule 1.
---
<!-- COMMENTS:END -->

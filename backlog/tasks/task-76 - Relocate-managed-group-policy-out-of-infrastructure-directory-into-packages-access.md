---
id: TASK-76
title: >-
  Relocate managed-group policy out of infrastructure/directory into
  packages/access
status: To Do
assignee: []
created_date: '2026-09-03 18:02'
updated_date: '2026-09-04 14:25'
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
- [ ] #1 GoogleDirectoryProvider contains no managed-group prefix, alias-preference or managed-domain logic; grep for _managed_group_prefix, _managed_group_domain, _managed_group_query_prefix, _matches_managed_group_prefix and _extract_managed_group_email returns zero hits under app/infrastructure/, and _normalize_email no longer completes bare values with a group domain
- [ ] #2 DIRECTORY_MANAGED_GROUP_PREFIX, DIRECTORY_MANAGED_GROUP_DOMAIN and DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL no longer exist anywhere: per plan decision D3 the prefix is derived from AccessRuntimeConfig naming rather than re-homed, the domain is owned by packages/access as AccessRuntimeConfig.dir_domain, and enforce_managed_group_email is deleted outright - with no duplicate second home created for any of them
- [ ] #3 The chosen mechanism - feature-side filtering of generic results, or an injected policy strategy - is stated in the task notes with its rationale, rather than the branching simply moving up one layer
- [ ] #4 packages/access/catalog, packages/access/sync and packages/access/request retain their current observable behaviour, proven by their existing test suites plus the new characterization tests the slices add (the managed path has no existing coverage - see plan fact F4)
- [ ] #5 A group outside the managed domain is returned unchanged by the generic provider and rejected (or ignored) by the feature, with a test at the feature boundary rather than the infrastructure one
- [ ] #6 All four subtasks TASK-76.1 through TASK-76.4 are Done and the DIRECTORY_MANAGED / MANAGED_GROUP grep across terraform, Makefile and app config returns zero hits at close
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
<!-- COMMENTS:END -->

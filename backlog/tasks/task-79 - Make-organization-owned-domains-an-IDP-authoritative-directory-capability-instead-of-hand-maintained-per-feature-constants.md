---
id: TASK-79
title: >-
  Make organization-owned domains an IDP-authoritative directory capability
  instead of hand-maintained per-feature constants
status: To Do
assignee: []
created_date: '2026-09-04 14:19'
updated_date: '2026-09-04 15:33'
labels:
  - layering
milestone: m-3
dependencies:
  - TASK-76.4
priority: medium
ordinal: 152000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Raised 2026-09-04 by task-planner while planning TASK-76, from a human-requested research question: where should the concept of the domains the organization owns actually live, given the SRE bot is not a SaaS but still has an app-level domain-management concern.

RESEARCH FINDING. Both major identity platforms model the set of domains an organization owns as a directory-level RESOURCE discovered from the platform, not as application configuration:
- Microsoft Graph exposes a domain resource per tenant carrying isVerified, isDefault, isRoot and isInitial, with ownership established by DNS verification (learn.microsoft.com/en-us/graph/api/resources/domain).
- Google Admin SDK Directory exposes domains.list per customer, returning the customer's domains including the primary one (developers.google.com/workspace/admin/directory/reference/rest/v1/domains/list).
The best-practice conclusion is that owned and primary domains are an IDP-authoritative FACT the app should read, not a constant the app should be told - which is exactly the shape decisions/layers.md gives a portable capability.

THE PROBLEM TODAY. The codebase is accumulating hand-maintained copies of domain knowledge in unrelated places:
- app/infrastructure/configuration/features/groups.py::GROUP_DOMAIN (legacy).
- DIRECTORY_MANAGED_GROUP_DOMAIN in DirectorySettings, which TASK-76 relocates to packages/access as AccessRuntimeConfig.dir_domain.
- The package-local approved-participant-domain setting from TASK-74 and TASK-75 in oncall_sync.
These are not all the same concept and must not be blindly merged: TASK-74's is an ALLOW-LIST POLICY answering which external domains may participate, while the other two are an IDENTITY FACT answering which domain the organization owns. This task is about the identity fact; the allow-list policy stays feature-owned.

SCOPE TO DECIDE THEN BUILD.
1. Whether DirectoryProvider gains a capability for this (for example list_domains or primary_domain) returning a canonical, vendor-neutral frozen dataclass, with the Google implementation on domains.list and a documented Entra mapping. TASK-76 explicitly excluded Protocol method-set changes, which is why this is a separate task.
2. Whether the result is cached or warmed at startup, given directory domains change rarely - relates to the existing DirectorySettings warmup and cache TTL fields.
3. Which of the three existing constants can then be derived rather than configured, and which must remain policy. Expected outcome: AccessRuntimeConfig.dir_domain becomes derivable and its required-non-empty validation from TASK-76.2 can relax; the legacy GROUP_DOMAIN retires with modules/; TASK-74's allow-list stays.
4. Whether decisions/configuration.md or decisions/layers.md needs an amendment recording the general rule - prefer reading an authoritative fact from the platform over configuring a mirror of it - since this is the second time the pattern has come up.

Do the decision work before the code; this is architecture-mode work first. It is sequenced after TASK-76.4 so it amends a clean generic provider rather than one still carrying managed-group policy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A written decision records whether owned/primary domains become a DirectoryProvider capability, with the Google domains.list and Microsoft Graph domain resource mappings cited, and any needed amendment to decisions/configuration.md or decisions/layers.md is made
- [ ] #2 The identity-fact concept and the allow-list-policy concept are explicitly kept distinct, with TASK-74/TASK-75's participant-domain setting left feature-owned
- [ ] #3 If the capability is adopted: it returns a vendor-neutral frozen dataclass, is covered by provider unit tests over recorded payloads, and its caching/warmup behaviour is decided and tested
- [ ] #4 Each of the three existing hand-maintained domain constants is dispositioned as derived, retained-as-policy, or retired, with the disposition recorded
- [ ] #5 mypy, ruff and the full non-smoke pytest run are green
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @task-planner
created: 2026-09-04 15:33
---
ADVISORY from TASK-76.2 planning (2026-09-04). Your eventual replacement target now has a precise address.

The hand-maintained owned-domain constant this task exists to retire lands, for the access feature, as AccessRuntimeConfig.dir_domain (app/packages/access/common/config/settings.py) - a REQUIRED, non-empty-validated field on the runtime config document, consumed only through ManagedGroupPolicy (app/packages/access/common/group_policy.py). It is a single domain with strict case-insensitive equality, a faithful port of the provider check at app/infrastructure/directory/google.py:466-471.

Two consequences for your scope:
- The multi-domain / subdomain gap is deliberately NOT closed in TASK-76, on the reasoning that owned-domain discovery is a new DirectoryProvider capability rather than a defect in the existing code. If that reasoning is wrong, TASK-76.2's plan flags it as assumption A3 for challenge.
- When list_domains / primary_domain lands, the single feature-side seam to redirect is ManagedGroupPolicy.from_config, plus removing dir_domain from the runtime config document, its JSON schema (RuntimeConfigJsonModel), the ACCESS_CONFIG_ENV_DIR_DOMAIN assembly variable and packages/access/access.local.json. No other access file reads the domain directly.

The other two hand-maintained copies named in TASK-76 decision D4 are unaffected by this slice: infrastructure/configuration/features/groups.py GROUP_DOMAIN (legacy) and TASK-74/75's approved-participant-domain, which is an allow-list policy rather than an identity fact.
---
<!-- COMMENTS:END -->

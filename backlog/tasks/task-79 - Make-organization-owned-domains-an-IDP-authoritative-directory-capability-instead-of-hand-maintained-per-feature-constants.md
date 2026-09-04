---
id: TASK-79
title: >-
  Make organization-owned domains an IDP-authoritative directory capability
  instead of hand-maintained per-feature constants
status: To Do
assignee: []
created_date: '2026-09-04 14:19'
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

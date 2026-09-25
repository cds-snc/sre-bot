---
id: TASK-131
title: >-
  Build the host authorization policy: declared permissions, central
  role-to-group configuration, decision lifetime and fail-closed IdP checks
status: To Do
assignee: []
created_date: '2026-09-25 19:43'
updated_date: '2026-09-25 19:58'
labels:
  - architecture
  - security
  - identity
milestone: m-4
dependencies:
  - TASK-116
  - TASK-113
  - TASK-111
  - TASK-129
references:
  - decisions/authorization.md
  - decisions/security.md
  - decisions/people-and-accounts.md
priority: high
ordinal: 279000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implements decisions/authorization.md (Accepted 2026-09-25) in app/server/security/, behind the current-user contract in app/contracts/ (TASK-116).

Scope:
- Features declare permission ids with a default level (everyone, authenticated, role) through a host extension point collected at startup (TASK-113).
- The central configuration maps roles to permissions and roles to IdP group references (idp, tenant, group_id) with display labels (TASK-111).
- A permission check on the contract resolves the caller's person, then asks the IdP about only the role that permission needs: Directory members.hasMember on each of the role's groups until the first yes, cached per (person, role).
- Verdicts never outlive the expires_at of a grant in the bot's own grant record.
- Decision lifetime: 15 min by default (5–60). A privileged permission always re-checks with the IdP. Absolute ceiling of 8 h. Each decision is logged with decided_at, source and expires_at.
- IdP outage: privileged and state-changing actions are refused; non-privileged reads get a 15 min grace period with an alert and an audit entry.
- Delete the unused DIRECTORY_CACHE_TTL_SECONDS setting, or replace it with the lifetime setting.

The task-planner must decompose this under the single-PR size gate. A likely split: the contract and extension point; the role configuration; the IdP membership check and decision lifetime; moving the Backstage routes from scopes to declared permissions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Features declare permission ids with a default level through a host extension point; an undeclared or ungranted permission is refused
- [ ] #2 Roles map to permissions and to IdP group references (idp, tenant, group_id) in typed central configuration; no feature module or settings slice names a group
- [ ] #3 An unlinked caller, including a Slack guest, reaches only everyone-level permissions
- [ ] #4 Verdicts last the configured lifetime (default 15 min); a privileged permission always re-checks with the IdP; decisions log decided_at, source and expires_at
- [ ] #5 With the IdP failing, privileged and state-changing actions are refused, and non-privileged reads are allowed only within the grace period, with an alert
- [ ] #6 Backstage routes check declared permissions; token scopes grant API access only
- [ ] #7 Full test suite, ruff, mypy and lint-imports pass
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-25 correction (authorization.md amended):
- Membership is checked with Directory members.hasMember, one role at a time: the role's groups are tried until the first yes, and the answer is cached per (person, role) for the lifetime. No Cloud Identity API and no group labels.
- Verdicts are capped by the grant's expires_at in the bot's own grant record, never by an IdP expiry field.
<!-- SECTION:NOTES:END -->

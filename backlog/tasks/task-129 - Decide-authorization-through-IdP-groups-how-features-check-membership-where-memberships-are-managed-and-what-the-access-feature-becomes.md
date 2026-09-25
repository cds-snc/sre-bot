---
id: TASK-129
title: >-
  Decide authorization through IdP groups: how features check membership, where
  memberships are managed, and what the access feature becomes
status: To Do
assignee: []
created_date: '2026-09-25 16:34'
updated_date: '2026-09-25 16:50'
labels:
  - architecture
  - identity
  - access
  - security
milestone: m-4
dependencies:
  - TASK-83.1
references:
  - decisions/security.md
  - decisions/approvals.md
  - decisions/people-and-accounts.md
  - decisions/workplace-systems.md
  - app/packages/access
priority: high
ordinal: 277000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ARCHITECTURE DECISION, no production code. Split out of TASK-83.1 on 2026-09-25 so identity (who the caller is) and authorization (what they may do) are decided separately.

Human direction 2026-09-25: the IdP is the source of truth for identity and for permissions. Access to a feature or role comes from membership in IdP groups (Google Directory groups today; Entra ID groups possible later, or both in parallel). Whether a person is a contractor is an organization-level concern with no answer yet, so the app does not model it; group membership limits access instead.

Open questions:
1. How a feature checks authorization: which contract it calls (in app/contracts/ or through the directory capability), whether membership is read per request or cached and for how long, and how a failed read maps to OperationResult and HTTP (fail closed).
2. How groups are named or configured per feature and per role, as typed settings per decisions/configuration.md and not hard-coded constants.
3. Where memberships are managed: the IdP admin UI, a Slack or Teams view that writes memberships to the IdP, or a Backstage plugin that does the same. Research current best practice online (for example, IdP-native access requests, identity governance, SCIM groups) and do not rely on recall.
4. The two-IdP case: a person linked to both Google and Entra identities (decisions/people-and-accounts.md). Which IdP's groups are checked, and whether one group model spans both.
5. What the incomplete access feature (app/packages/access) becomes against this decision and decisions/approvals.md: keep, rescope or retire each part (catalog, request, sync).

Output: an amendment to decisions/security.md or a new decisions/ record, each with a Checks section, then follow-up tasks under the single-PR size gate.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A decisions/ record states how features check authorization through IdP group membership, including caching, failure mapping (fail closed) and group configuration
- [ ] #2 The record chooses where memberships are managed (IdP UI, chat view, Backstage plugin, or a combination), with sourced evidence from current documentation
- [ ] #3 The two-IdP case is decided: which IdP's groups apply to a person linked to both
- [ ] #4 Each part of app/packages/access has a recorded fate against the decision and decisions/approvals.md, and the affected tasks are updated through the CLI
- [ ] #5 Every amended or new record has a mechanically verifiable Checks section; follow-up tasks are created; no production code changes
- [ ] #6 Each feature declares an access policy in typed configuration (everyone, authenticated, or named IdP groups), and the record states where the policy is enforced and how an unlinked or refused caller is answered
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-25 human direction (from the TASK-83.1 session): each feature declares an access policy in configuration with three levels:
(a) everyone, including unlinked callers such as Slack guests. Generic Slack commands must keep working for guests;
(b) authenticated only, meaning the caller resolved to an active person;
(c) members of named IdP security groups.
Backstage always requires SSO, so Backstage callers are at least (b). Some features additionally require (c). Question 1 should decide where this policy is declared and enforced (entry point versus handler) and how an unlinked caller is answered when refused.
<!-- SECTION:NOTES:END -->

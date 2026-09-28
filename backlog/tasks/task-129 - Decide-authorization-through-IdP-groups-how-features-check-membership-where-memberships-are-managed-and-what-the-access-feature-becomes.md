---
id: TASK-129
title: >-
  Decide authorization through IdP groups: how features check membership, where
  memberships are managed, and what the access feature becomes
status: Done
assignee: []
created_date: '2026-09-25 16:34'
updated_date: '2026-09-25 20:01'
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
- [x] #1 A decisions/ record states how features check authorization through IdP group membership, including caching, failure mapping (fail closed) and group configuration
- [x] #2 The record chooses where memberships are managed (IdP UI, chat view, Backstage plugin, or a combination), with sourced evidence from current documentation
- [x] #3 The two-IdP case is decided: which IdP's groups apply to a person linked to both
- [x] #4 Each part of app/packages/access has a recorded fate against the decision and decisions/approvals.md, and the affected tasks are updated through the CLI
- [x] #5 Every amended or new record has a mechanically verifiable Checks section; follow-up tasks are created; no production code changes
- [x] #6 Each feature declares an access policy in typed configuration (everyone, authenticated, or named IdP groups), and the record states where the policy is enforced and how an unlinked or refused caller is answered
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-25 human direction (from the TASK-83.1 session): each feature declares an access policy in configuration with three levels:
(a) everyone, including unlinked callers such as Slack guests. Generic Slack commands must keep working for guests;
(b) authenticated only, meaning the caller resolved to an active person;
(c) members of named IdP security groups.
Backstage always requires SSO, so Backstage callers are at least (b). Some features additionally require (c). Question 1 should decide where this policy is declared and enforced (entry point versus handler) and how an unlinked caller is answered when refused.

2026-09-25 human decisions so far:
- Policy shape: features declare permissions; a central config maps IdP group references to roles and roles to permissions (Argo CD / Backstage pattern).
- The bot is the authorization decision point for every entry point. Backstage scopes only grant access to the bot API, and security.md's rule that permissions come from JWT scopes will be amended.
- Google edition is Enterprise Standard/Plus, so Cloud Identity checkTransitiveMembership and membership expiry are available.
- The access feature predates decisions/ and is not a constraint; the decision follows industry practice and the code is adjusted later.
- Only privileged roles are time-bound (just-in-time), expiring at the IdP; baseline roles are standing memberships.
- A member added directly in the IdP, outside the catalogue, raises an alert only; nobody is removed automatically.
- Access reviews are required, but their design is deferred to TASK-130.
Open: build or adopt for the request front end. The human distinguished identity validity and session/decision lifetime (a configurable time after which the bot re-checks the IdP) from time-bound grants. Research on session lifetime and push revocation is in flight.

2026-09-25 remaining decisions:
- Decision lifetime is 15 min by default (configurable 5–60), with a mandatory IdP re-check before any privileged permission and an 8 h absolute ceiling.
- If the IdP is unreachable, only non-privileged reads get a grace period (15 min past lifetime), with an alert and an audit entry.
- No push revocation for now; Google Reports activities.watch and Microsoft Graph notifications are recorded as the upgrade path.
- Access requests run on the approvals capability plus a git catalogue of requestable groups; the effect writes to the IdP and sets expireTime on privileged grants.
decisions/authorization.md is drafted (status Draft) for human review. The security.md amendment and follow-up tasks come after approval.

2026-09-25: the human accepted decisions/authorization.md ('accept for now, revisit on a blocker').
- Cascade: security.md Identity paragraph amended (token scopes grant API access only); README index updated; people-and-accounts.md amended with self-service cross-IdP joins (proof by signing in to both IdPs, merged_into tombstone, unjoin) at the human's request.
- Follow-ups: TASK-131 (host authorization policy), TASK-132 (report members added outside the catalogue), TASK-83.14 (self-service identity join), TASK-130 (access-review design).
- Updated: TASK-61 (catalogue, no self-approval, IdP expiry), TASK-88 (retire AWS_ADMIN_GROUPS), TASK-83.4 and TASK-83.7 (tombstone and joins).
<!-- SECTION:NOTES:END -->

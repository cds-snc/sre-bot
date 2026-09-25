---
id: TASK-83.1
title: >-
  Answer the identity open questions and accept the three remaining identity and
  entry-point Draft records
status: Done
assignee: []
created_date: '2026-09-10 16:18'
updated_date: '2026-09-25 17:08'
labels:
  - identity
  - architecture
dependencies: []
references:
  - decisions/governance.md
  - decisions/plugin-architecture.md
parent_task_id: TASK-83
priority: high
ordinal: 168000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Updated 2026-09-24. Three Draft records dated 2026-09-10 still set the direction for identity and platform entry points:
- decisions/workplace-systems.md
- decisions/people-and-accounts.md
- decisions/platform-entrypoints.md
The fourth, decisions/capability-packages.md, was deleted. decisions/plugin-architecture.md (Accepted 2026-09-24) replaced it and the deleted layers.md, and commit 3407cd5c already rewrote cloud-portability.md, feature-packages.md, platform-transports.md, transport-slack.md, configuration.md and README.md to match the six layers. The cascade this ticket used to own is done. Re-scoping TASK-18, TASK-26, TASK-33, TASK-42 and TASK-43 to the entry-point split was also done on 2026-09-24.

Implementation under the people-and-accounts coordinator must not start until these records are accepted: decisions/governance.md makes Accepted the binding rule for new code.

Open questions to settle first:
- Which verified-link mechanisms come first: SRE admin links only; self-service linking by signing in to both accounts; or an HR employee number, if populated in both directories (Microsoft Graph employeeId, Google Directory externalIds of type organization).
- The authoritative source of contractors, and the attribute that records a person's kind.
- How SRE reviews suggested links at employee scale (bulk confirmation) without auto-linking.

decisions/interaction-toolkits.md is also Draft but is not part of this ticket; its tickets are created on acceptance.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The open questions in decisions/people-and-accounts.md are answered and recorded in the record
- [x] #2 Each of workplace-systems.md, people-and-accounts.md and platform-entrypoints.md is Accepted, or Rejected with its reason
- [x] #3 Any cascade an acceptance still requires is applied in the same PR, so no Accepted record contradicts another
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-09-25 human direction, recorded in the decisions/people-and-accounts.md rewrite (still Draft):
- Every entry point is SSO-federated to the IdP (Slack through SSO; Backstage through SSO plus JWKS). Google is the IdP now. The design must be ready for Entra, or for Google and Entra in parallel.
- The app-owned Person record stays. Web research found that SCIM, Keycloak, Okta and Backstage all use an internal id with linked external identities.
- The three verified-link mechanisms and bulk review are replaced by links based on what the IdP asserted (idp, idp_subject, sso_email). SRE links by hand only for cross-IdP joins and exceptions.
- Contractor kind is deferred as an organization-level concern. Authorization through IdP groups is split out to TASK-129.
- All three records are accepted in the single decisions-planning PR.

2026-09-25 follow-up:
- Google identities key on the Directory id, not the OIDC sub. The current code keys every human on email: directory lookups, the Backstage email claim, and access actor_email.
- Slack guests are never linked by email; per-feature access policies go to TASK-129.
- The Backstage resolver claim is deferred until the private cds-snc/backstage repository is reachable.

2026-09-25: the human approved the decision.
- people-and-accounts.md was rewritten and Accepted; workplace-systems.md and platform-entrypoints.md were Accepted; README index updated.
- Cascade: platform-entrypoints.md now says an unlinked caller reaches the feature's access policy; workplace-systems.md Context points identity and permissions at the IdP, and its Migration names TASK-38, 39, 119, 120 and 121.
- Rescoped through the CLI: TASK-83, 83.4, 83.5, 83.6, 83.7 (now also depends on TASK-129), 83.8 and 83.9 (now depend on 83.6 instead of 83.7) and 83.13.
- Accepted-status notes were added to TASK-26, 33, 38, 43, 79 and 83.2.
<!-- SECTION:NOTES:END -->

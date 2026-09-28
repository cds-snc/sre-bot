---
id: TASK-83.14
title: 'Offer self-service identity joins across IdPs, proved by signing in to both'
status: To Do
assignee: []
created_date: '2026-09-25 19:43'
labels:
  - identity
  - security
milestone: m-4
dependencies:
  - TASK-83.7
  - TASK-83.13
references:
  - decisions/people-and-accounts.md
parent_task_id: TASK-83
priority: low
ordinal: 281000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build only once a second IdP is trusted (TASK-83.13). decisions/people-and-accounts.md (amended 2026-09-25):
- The bot offers a join when a shared attribute suggests two people are the same human, when the person asks, or when they act from a platform tied to an IdP where their person has no identity.
- The person proves control by signing in to both IdPs in one linking flow. The bot is an OIDC relying party for this flow only, with state, nonce and PKCE.
- The older person survives. The other becomes a merged_into tombstone that still resolves.
- The join is recorded with verified provenance, audit-logged, and announced on the person's chat homes. The person's cached authorization verdict is discarded.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A join commits only after both ID tokens validate (signature, iss, aud, nonce) in one flow with state and PKCE; the subject comes from each token
- [ ] #2 The absorbed person becomes a merged_into tombstone that resolves to the survivor; identities, accounts and homes move in one atomic write
- [ ] #3 The join is recorded with verified provenance and an audit event, is announced on the person's chat homes, and discards the cached authorization verdict
- [ ] #4 The offer appears in each of the three trigger cases, and declining it changes nothing
- [ ] #5 Full test suite, ruff, mypy and lint-imports pass
<!-- AC:END -->

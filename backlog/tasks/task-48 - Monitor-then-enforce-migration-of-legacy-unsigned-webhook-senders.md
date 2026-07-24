---
id: TASK-48
title: Monitor-then-enforce migration of legacy unsigned webhook senders
status: To Do
assignee: []
created_date: '2026-07-24 13:59'
labels:
  - security
  - webhooks
milestone: m-4
dependencies:
  - TASK-47
references:
  - decisions/security.md
priority: medium
ordinal: 72000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Phase 4 behaviour change: retires the Hardened secret-URL (legacy/unsigned) tier from decisions/security.md (Webhooks, amended 2026-07-24) by migrating each live sender identified by TASK-46 onto the HMAC tier delivered by TASK-47. This is the burn-down that lets the risk-accepted-in-writing exception be closed.

Approach (per-webhook_id, never big-bang):
1. Monitor mode: for a legacy auth_mode=none webhook, evaluate the would-be HMAC/allow-list decision and log a would_reject event WITHOUT blocking, so we can confirm the migrated sender signs correctly before enforcing.
2. Flip to enforce per webhook_id once its sender is confirmed migrated (auth_mode: none -> monitor -> hmac). Provide an operator command/flow to advance a webhook through these states.
3. Flagship first migration: GitHub Actions senders (e.g. the failed-workflow warning). GH Actions can compute an HMAC header trivially and GitHub publishes egress ranges via the /meta API, so these can be signed and/or CIDR-pinned early.
4. Track remaining auth_mode=none population to zero; when empty, update decisions/security.md Migration note to mark the generic-webhook exception closed.

Out of scope: the HMAC verification/issuance mechanism itself (TASK-47); observability event emission (TASK-46).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A legacy webhook can be placed in monitor mode where an invalid/absent signature is logged as would_reject but the request is still accepted (test)
- [ ] #2 An operator flow advances a single webhook_id through none -> monitor -> hmac without affecting other webhook IDs (test)
- [ ] #3 The GitHub Actions sender is migrated to a signed (HMAC and/or CIDR-pinned) tier as the reference migration (documented + test)
- [ ] #4 A report/query enumerates the remaining auth_mode=none webhook population so the exception burn-down is measurable
<!-- AC:END -->

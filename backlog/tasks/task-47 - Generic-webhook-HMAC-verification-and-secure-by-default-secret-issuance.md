---
id: TASK-47
title: Generic webhook HMAC verification and secure-by-default secret issuance
status: To Do
assignee: []
created_date: '2026-07-24 13:59'
labels:
  - security
  - webhooks
milestone: m-4
dependencies:
  - TASK-46
  - TASK-24
references:
  - decisions/security.md
priority: high
ordinal: 71000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Phase 4 behaviour change: introduces the Shared-secret HMAC tier from decisions/security.md (Webhooks, amended 2026-07-24). Deferred out of Phase 0 because it changes acceptance behaviour for external senders (it can reject requests that are accepted today). Depends on TASK-46 (origin inventory) so enforcement is only flipped on for senders known to be migratable, and on TASK-24 (SecuritySettings) as the settings home for HMAC config.

Scope:
1. Verification: on the generic (non-provider-signed) webhook path, verify an HMAC signature header computed with a per-webhook secret over the raw body; constant-time compare. Verification lives in the transport/ingress layer, never in feature handlers.
2. Secret provisioning: extend the webhook record (app/modules/slack/webhooks.py create_webhook + DynamoDB item) with a per-webhook secret and an auth_mode field (none | hmac); mint the secret at creation and surface it once via the /sre webhooks create flow (replacing the per-team Slack app pattern). Support rotation and revocation (revoke_webhook already exists).
3. Secure-by-default: newly issued webhooks default to auth_mode=hmac and are enforced from creation; only pre-existing legacy IDs may carry auth_mode=none pending TASK-48 migration.
4. Config: HMAC settings live in the SecuritySettings slice (TASK-24), not scattered constants.

Out of scope: bulk migration/monitor-mode rollout of the existing legacy population (TASK-48); SNS/provider-signed path (TASK-7).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A generic webhook with auth_mode=hmac rejects (401/403) a request with a missing or invalid HMAC signature and accepts a valid one, verified with a constant-time compare (tests for both)
- [ ] #2 HMAC verification runs in the ingress/transport layer with zero verification code in feature handlers (review check)
- [ ] #3 create_webhook mints a per-webhook secret and sets auth_mode; the secret is shown exactly once at creation and never stored in plaintext-readable form in logs (test)
- [ ] #4 Newly issued webhooks are auth_mode=hmac and enforced by default; a legacy auth_mode=none record is still accepted (test)
- [ ] #5 HMAC configuration is owned by the SecuritySettings slice, not ad-hoc constants (review)
<!-- AC:END -->

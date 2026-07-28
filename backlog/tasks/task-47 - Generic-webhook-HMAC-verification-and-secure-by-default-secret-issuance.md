---
id: TASK-47
title: Generic webhook HMAC verification and secure-by-default secret issuance
status: To Do
assignee: []
created_date: '2026-07-24 13:59'
updated_date: '2026-07-28 18:41'
labels:
  - security
  - webhooks
milestone: m-4
dependencies:
  - TASK-37.4
  - TASK-46
references:
  - decisions/webhooks.md
  - decisions/security.md
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1342'
priority: high
ordinal: 71000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 5 of the webhooks rearchitecture sequence (decisions/webhooks.md), built ON the new app/packages/webhooks package - NOT on the legacy modules/slack CRUD - and following coordinator TASK-37's extraction slices. Introduces the Shared-secret HMAC tier and secure-by-default issuance from decisions/security.md (Webhooks, amended 2026-07-24).

Behaviour change: it can reject requests accepted today, so it is gated behind TASK-46 (origin inventory) and lands only after the package cutover (TASK-37.4).

Scope:
1. Verification: in app/packages/webhooks/verification.py (the ingress boundary established in TASK-37.2), verify an HMAC signature header computed with a per-webhook secret over the raw body; constant-time compare. Zero verification code in feature handlers (five-step discipline).
2. Secret provisioning: extend the frozen Webhook domain model (TASK-37.1) with auth_mode (none | hmac) and a secret reference; service.create() mints the secret at creation and surfaces it exactly once via the /sre webhooks admin flow (interactions/slack.py). Support rotation and revocation (the store already exposes revoke).
3. Secure-by-default: newly issued webhooks default to auth_mode=hmac and are enforced from creation; only pre-existing legacy IDs may carry auth_mode=none pending the TASK-48 migration.
4. Config: HMAC settings live in the package-partitioned WebhookSettings (decisions/configuration.md, decisions/webhooks.md), NOT a central SecuritySettings aggregator. This supersedes the earlier TASK-24 settings-home assumption (dependency dropped).

Out of scope: bulk monitor-then-enforce migration of the legacy population (TASK-48); the SNS/provider-signed path (TASK-7); non-Slack dispatch (TASK-37.5).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A generic webhook with auth_mode=hmac rejects (401/403) a request with a missing or invalid HMAC signature and accepts a valid one, verified with a constant-time compare (tests for both)
- [ ] #2 HMAC verification runs in the webhooks package ingress boundary (verification.py) with zero verification code in feature handlers (review check)
- [ ] #3 service.create() mints a per-webhook secret and sets auth_mode; the secret is shown exactly once at creation and never stored in plaintext-readable form in logs (test)
- [ ] #4 Newly issued webhooks are auth_mode=hmac and enforced by default; a legacy auth_mode=none record is still accepted (test)
- [ ] #5 HMAC configuration is owned by the package-partitioned WebhookSettings, not a central SecuritySettings aggregator or ad-hoc constants (review)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 18:41
---
Reframed onto the new app/packages/webhooks package (decisions/webhooks.md, Option A). Dropped the TASK-24 dependency: HMAC settings now live in the package-partitioned WebhookSettings, not SecuritySettings. Deps are now TASK-37.4 (package cutover) + TASK-46 (origin inventory). AC#2/#3/#5 reworded to the package boundary (verification.py / service.create / WebhookSettings).
---
<!-- COMMENTS:END -->

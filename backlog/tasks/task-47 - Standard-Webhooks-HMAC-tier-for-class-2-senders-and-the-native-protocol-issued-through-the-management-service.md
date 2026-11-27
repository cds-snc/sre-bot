---
id: TASK-47
title: >-
  Standard Webhooks HMAC tier for class 2 senders and the native protocol,
  issued through the management service
status: To Do
assignee: []
created_date: 2026-07-24 13:59
updated_date: '2026-11-25T20:52:00Z'
labels:
  - security
  - webhooks
milestone: m-4
dependencies:
  - TASK-37.6.1
references:
  - decisions/webhooks.md
  - decisions/security.md
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1342
  - decisions/plugin-architecture.md
priority: high
ordinal: 71000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The HMAC tier, narrowed to class 2 senders, and the native protocol (decisions/security.md Webhooks; decisions/webhooks.md Authenticity; TASK-168 research packet section 5, row 47, Q4 items 5, 6 and 10, Q9, OQ15 and OQ22). Built on app/capabilities/webhooks/ and the management service (TASK-37.6.1).

Caller classes (security.md): first-party workloads that can hold an identity call feature APIs (TASK-194), so this tier is for third-party or scripted senders that cannot hold an identity but can sign.

Scope:
- A standard_webhooks protocol: Standard Webhooks v1.0.0 (webhook-id, webhook-timestamp, webhook-signature; v1 is HMAC-SHA256 over id.timestamp.body), verified against the raw body with a constant-time compare, a configurable timestamp tolerance (default 300 s), two active secrets during rotation (the old one until a configurable expiry), other schemes ignored so there is no downgrade. Library: standardwebhooks 1.3.0 wrapped in the protocol adapter, or our own (OQ15, decide at planning). webhook-id is the delivery id for the inbox dedupe.
- A native protocol whose body is the InboundEvent schema, signed with the same tier, for owned senders that move off mapping content.
- Issuance and rotation through WebhookAdmin (TASK-37.6.1): a whsec_ secret shown once, encrypted at the application level with KMS (encryption context instance_ref; the AWS Database Encryption SDK or direct KMS, chosen at planning), decrypted on verify with a TTL cache, never logged and never exported.
- Secure by default: new instances get the HMAC tier unless their protocol is provider-signed; legacy instances keep their tier until TASK-48 moves them.
- HMAC settings in the [webhooks] slice.

Out of scope: the caller-migration programme and enforcement on legacy instances (TASK-48); provider-signed protocols (SNS in TASK-37.2.2; GitHub in TASK-147.5); machine principals (TASK-194).

Size: ~300 production LOC.
Production: prod.
Revert / blast radius: one revert; new instances fall back to the URL tier.
Change notice: developer notice: signing is available, with a guide and snippets. User announcement only if the create flow changes visibly (packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The standard_webhooks protocol verifies webhook-id, webhook-timestamp and webhook-signature (v1, HMAC-SHA256 over id.timestamp.body) against the raw body with a constant-time compare and a configurable timestamp tolerance; a missing, stale or invalid signature answers 403 with a generic body and a valid one is accepted (tests for each)
- [ ] #2 During rotation two secrets are accepted, the old one until a configurable expiry, and other signature schemes are ignored (test)
- [ ] #3 A native protocol accepts a signed body in the InboundEvent schema and its webhook-id is the delivery id for inbox dedupe (test)
- [ ] #4 Secrets are minted and rotated through WebhookAdmin, shown exactly once, encrypted at the application level with KMS (encryption context instance_ref), and never logged or exported (test)
- [ ] #5 Verification runs only in the protocol adapter at the ingress boundary, with zero verification code in feature handlers (review)
- [ ] #6 Newly created instances get the HMAC tier unless their protocol is provider-signed, and a legacy-tier instance is still accepted until TASK-48 moves it (test)
- [ ] #7 HMAC configuration (tolerance, rotation expiry, cache TTL) is typed [webhooks] settings with defaults, not a central aggregator or constants (test + review)
- [ ] #8 The PR body carries the developer change notice with a guide and snippets (review)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 18:41

---

Reframed onto the new app/packages/webhooks package (decisions/webhooks.md, Option A). Dropped the TASK-24 dependency: HMAC settings now live in the package-partitioned WebhookSettings, not SecuritySettings. Deps are now TASK-37.4 (package cutover) + TASK-46 (origin inventory). AC#2/#3/#5 reworded to the package boundary (verification.py / service.create / WebhookSettings).

---

created: 2026-11-25T20:52:00Z

---

2026-11-25 re-cut (TASK-168, human-approved). Old title "Generic webhook HMAC verification and secure-by-default secret issuance"; scope narrowed to class 2 senders (TASK-168 packet Q9) and rebuilt on the management API. Old ACs, verbatim (short), and where each intent now lives:
- #1 "A generic webhook with auth_mode=hmac rejects (401/403) a request with a missing or invalid HMAC signature and accepts a valid one, verified with a constant-time compare" -> new AC #1 (Standard Webhooks v1; 403 for webhook signatures, decisions/security.md).
- #2 "HMAC verification runs in the webhooks package ingress boundary (verification.py) with zero verification code in feature handlers" -> new AC #5 (the protocol adapter is the ingress boundary).
- #3 "service.create() mints a per-webhook secret and sets auth_mode; the secret is shown exactly once at creation and never stored in plaintext-readable form in logs" -> new AC #4 (issued through WebhookAdmin, TASK-37.6.1; KMS at rest; never exported).
- #4 "Newly issued webhooks are auth_mode=hmac and enforced by default; a legacy auth_mode=none record is still accepted" -> new AC #6 (auth_tier).
- #5 "HMAC configuration is owned by the package-partitioned WebhookSettings, not a central SecuritySettings aggregator or ad-hoc constants" -> new AC #7 ([webhooks] settings).
Old dependencies: TASK-37.4 and TASK-46 (Done) dropped; now TASK-37.6.1 (issuance and rotation through the management service). Stale paths (app/packages/webhooks, verification.py, entrypoints/slack.py admin flow) replaced. Nothing is archived.

---
<!-- COMMENTS:END -->

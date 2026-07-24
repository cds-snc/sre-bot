---
id: TASK-9
title: >-
  Slack request-signature verification for HTTP mode; validate signing secret at
  boot
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-24 14:00'
labels:
  - security
  - phase-0
  - slack
milestone: m-0
dependencies: []
references:
  - decisions/transport-slack.md
  - 'https://github.com/cds-snc/sre-bot/issues/1263'
  - decisions/security.md
priority: medium
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/transport-slack.md (Verification). Today SIGNING_SECRET is defined twice (app/integrations/slack/settings.py:35 and app/infrastructure/configuration/infrastructure/platforms.py:58 - the dual-home problem task-24 fixes) and validated when Socket Mode is off, but nothing performs HMAC verification on HTTP-mode requests; Socket Mode narrows exposure but HTTP mode is a supported flag and webhook paths exist (SEC-5).

Steps:
1. On every HTTP-mode inbound Slack request, before any body use: verify v0= HMAC-SHA256 over the timestamp+body with the signing secret, constant-time compare, and reject X-Slack-Request-Timestamp older/newer than 5 minutes (replay defense). Bolt provides this - ensure the Bolt request verifier is enabled and not bypassed by custom routes.
2. Verification lives in the transport layer, never in handlers.
3. Validate at boot that the signing secret is configured whenever HTTP mode is selected (fail fast per decisions/configuration.md); in Socket Mode, still validate the secret is present so mode switches are safe.
4. Document in the transport module docstring that Socket Mode relies on the connection handshake.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 HTTP-mode tests: valid signature accepted; tampered body rejected; stale timestamp (>5 min) rejected
- [ ] #2 Boot fails when HTTP mode is selected without a signing secret
- [ ] #3 No verification code exists in feature handlers (review check)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass
- [ ] #2 PR references SEC-5 and decisions/transport-slack.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-24 14:00
---
Cross-reference (2026-07-24): decisions/security.md Webhooks clause was amended to a tiered trust model (provider-signed / shared-secret HMAC / hardened secret-URL). This task is the provider-signed tier for the Slack HTTP transport (Slack platform signing-secret HMAC over timestamp+body). It stays a distinct, correctly-scoped m-0 task and needs no restructuring; the generic-webhook HMAC tier is separate (TASK-47/TASK-48, m-4) and the Phase-1 origin observability that feeds it is TASK-46 (m-0).
---
<!-- COMMENTS:END -->

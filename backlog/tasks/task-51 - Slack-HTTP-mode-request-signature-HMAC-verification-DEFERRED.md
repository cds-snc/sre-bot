---
id: TASK-51
title: Slack HTTP-mode request-signature (HMAC) verification (DEFERRED)
status: To Do
assignee: []
created_date: '2026-07-27 14:02'
updated_date: '2026-07-27 14:03'
labels:
  - security
  - slack
  - phase-4
milestone: m-4
dependencies:
  - TASK-26
  - TASK-9
references:
  - decisions/transport-slack.md
  - decisions/security.md
  - 'https://github.com/cds-snc/sre-bot/issues/1263'
priority: low
ordinal: 79000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
DEFERRED - do not start until further notice. Pick this up only when HTTP Events mode is actually going to be enabled (SLACK__SOCKET_MODE=false). The app runs Socket Mode (WebSocket) today, where request authenticity is carried by the connection handshake, so this per-request verification is latent and not live-exposed until HTTP mode is turned on.

Split out of TASK-9 (2026-07-27). TASK-9 keeps the boot-time signing-secret validation that is doable now; this task carries the HTTP-mode per-request HMAC verification.

Aligns with decisions/transport-slack.md (Verification) and is the provider-signed tier of decisions/security.md's tiered webhook trust model (the generic-webhook HMAC tier is separate: TASK-47/TASK-48).

Steps (when un-deferred):
1. On every HTTP-mode inbound Slack request, before any body use: verify v0= HMAC-SHA256 over the timestamp+body with the signing secret, constant-time compare, and reject X-Slack-Request-Timestamp older/newer than 5 minutes (replay defense). Bolt provides this - ensure the Bolt request verifier is enabled and not bypassed by custom routes.
2. Verification lives in the transport layer (app/infrastructure/slack/ post TASK-26), never in feature handlers.

Depends on TASK-26 (the Slack transport home in app/infrastructure/slack/ where verification belongs) and TASK-9 (boot-time signing-secret validation).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Under HTTP Events mode (SLACK__SOCKET_MODE=false), a valid Slack signature is accepted; a tampered body is rejected; a request whose X-Slack-Request-Timestamp is older than 5 minutes is rejected
- [ ] #2 Verification runs in the transport layer (app/infrastructure/slack/), before any body use, and no verification code exists in feature handlers
- [ ] #3 The Bolt request verifier is enabled for HTTP-mode routes and cannot be bypassed by custom routes
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 HTTP-mode verification tests pass (valid / tampered / stale-timestamp)
- [ ] #2 PR references decisions/transport-slack.md and decisions/security.md (provider-signed tier) and GitHub issue 1263
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-27 14:03
---
DEFER - do not start until further notice. Split out of TASK-9 on 2026-07-27. The app runs Slack Socket Mode (WebSocket) today, where request authenticity is carried by the connection handshake, so this per-request HMAC verification is latent and not live-exposed. Un-defer only when HTTP Events mode (SLACK__SOCKET_MODE=false) is actually going to be enabled, and after TASK-26 has moved the Slack transport into app/infrastructure/slack/.
---
<!-- COMMENTS:END -->

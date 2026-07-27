---
id: TASK-9
title: Validate the Slack signing secret at boot (both delivery modes)
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-27 14:02'
labels:
  - security
  - phase-0
  - slack
milestone: m-0
dependencies: []
references:
  - decisions/transport-slack.md
  - decisions/configuration.md
  - decisions/security.md
priority: medium
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Scope (post-split): validate the Slack signing secret at application boot. The HTTP-mode per-request HMAC verification that previously shared this task is now tracked separately as a deferred follow-up (see the split-out Slack HTTP-mode HMAC verification task) because the app runs Socket Mode today and HTTP Events mode is future work.

Aligns with decisions/transport-slack.md (Verification) and decisions/configuration.md (fail fast at boot on missing required config). Today the signing secret is defined and validated only when Socket Mode is off; in Socket Mode request authenticity is carried by the connection handshake, but the secret should still be present so a later switch to HTTP mode is safe.

Steps:
1. At boot, if HTTP Events mode is selected (SLACK__SOCKET_MODE=false), fail fast when no signing secret is configured (decisions/configuration.md).
2. In Socket Mode, still validate that the signing secret is present at boot so mode switches are safe; surface a clear, actionable error/warning when it is missing.
3. Document in the Slack transport module docstring that Socket Mode relies on the connection handshake for request authenticity, and that HTTP-mode per-request HMAC verification is a separate, deferred task and is not yet implemented.

Out of scope (moved to the deferred HTTP-mode task): computing/verifying the v0= HMAC-SHA256 over timestamp+body, constant-time compare, and the 5-minute replay window. That work only matters once HTTP Events mode is actually enabled.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Boot fails fast when HTTP Events mode is selected (SLACK__SOCKET_MODE=false) and no signing secret is configured
- [ ] #2 In Socket Mode, a missing signing secret is detected at boot and surfaced as a clear, actionable error or warning, so a later switch to HTTP mode is safe
- [ ] #3 The Slack transport module docstring documents that Socket Mode relies on the connection handshake and that HTTP-mode per-request HMAC verification is deferred to a separate task and not yet implemented
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Boot-validation tests pass: HTTP mode without a secret fails fast; Socket Mode without a secret is flagged; with a secret the app boots in both modes
- [ ] #2 PR references decisions/transport-slack.md and decisions/configuration.md and links the deferred HTTP-mode HMAC verification follow-up task
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-27 14:02
---
Scope split (2026-07-27): this task was narrowed to boot-time signing-secret validation, which is doable now while the app runs Socket Mode. The HTTP-mode per-request HMAC verification (v0= HMAC-SHA256 over timestamp+body, constant-time compare, 5-minute replay window) - the provider-signed tier of decisions/security.md's tiered webhook trust model - is split out into a separate follow-up task and DEFERRED until further notice, because HTTP Events mode is future work and is not exposed under Socket Mode. The generic-webhook HMAC tier remains separate (TASK-47/TASK-48); Phase-1 origin observability is TASK-46. GitHub issue 1263 (Slack HTTP verification) moves with the deferred HMAC task.
---
<!-- COMMENTS:END -->

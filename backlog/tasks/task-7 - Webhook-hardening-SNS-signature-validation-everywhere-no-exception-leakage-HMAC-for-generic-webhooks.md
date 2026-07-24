---
id: TASK-7
title: >-
  Webhook hardening (Phase 0): SNS signature validation everywhere, no exception
  leakage, body-size cap
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-24 14:00'
labels:
  - security
  - phase-0
milestone: m-0
dependencies:
  - TASK-1
references:
  - decisions/security.md
  - 'https://github.com/cds-snc/sre-bot/issues/1261'
priority: high
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (Webhooks, amended 2026-07-24). Scope re-narrowed to Phase-0 non-behaviour-change hardening only; the generic-webhook HMAC requirement that was originally step 2 / AC#2 here is a behaviour change (it can reject senders accepted today) and has moved to Phase 4 - see TASK-47 (HMAC verification + secure-by-default issuance) and TASK-48 (monitor-then-enforce migration), enabled by TASK-46 (Phase-1 origin observability). The legacy unsigned population is risk-accepted in writing per the amended Webhooks clause until TASK-48 migrates it.

Today: /hook/{webhook_id} in app/api/v1/routes/webhooks.py authenticates by existence + active flag only; app/modules/webhooks/aws_sns.py:84-85 returns early without SNS signature validation when not app_settings.is_production; 5xx responses interpolate the exception into the body at aws_sns.py:108 and :120 (detail=f"... {e.__class__.__qualname__}: {e}") (SEC-6, OWASP API2:2023).

Steps (Phase 0, non-behaviour-change):
1. SNS: validate the message signature in ALL environments - delete the early-return branch at aws_sns.py:84-85. (SNS is provider-signed, so this hardens a known signed source and does not affect arbitrary senders.)
2. Replace every f-string that embeds the exception (class name or str(e)) in a 5xx response body with a generic message; log the full exception server-side instead.
3. Cap webhook body size.

Deferred to Phase 4 (m-4): per-webhook HMAC signature requirement, secure-by-default secret issuance, and monitor-then-enforce migration of known senders (TASK-46/47/48).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SNS signature validation runs unconditionally; a test covers an invalid-signature rejection
- [ ] #2 grep -rn "e.__class__" and f-string exception interpolation in webhook 5xx paths return zero hits; a forced exception yields a generic 500 body (test)
- [ ] #3 Oversized webhook bodies are rejected (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; existing legitimate webhook flows still succeed against the new auth (documented manual check or smoke test)
- [ ] #2 PR references SEC-6 and decisions/security.md
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-24 14:00
---
Restructured per human direction (2026-07-24): the day-1-infeasible 'reject any generic webhook without a valid HMAC' requirement (former AC#2) removed from this Phase-0 task and re-homed to Phase 4 as TASK-47 (HMAC + secure-by-default issuance) and TASK-48 (monitor-then-enforce migration), with TASK-46 adding Phase-1 origin observability in m-0. decisions/security.md Webhooks clause amended to a tiered trust model; the generic-webhook gap is now risk-accepted in writing (m-0 exit) until TASK-48 closes it. This task remains a single manageable PR: SNS-everywhere + exception-leak removal + body-size cap on the webhook ingress path.
---
<!-- COMMENTS:END -->

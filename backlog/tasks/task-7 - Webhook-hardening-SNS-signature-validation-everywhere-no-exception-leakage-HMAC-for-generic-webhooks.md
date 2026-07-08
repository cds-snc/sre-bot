---
id: TASK-7
title: >-
  Webhook hardening: SNS signature validation everywhere, no exception leakage,
  HMAC for generic webhooks
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
labels:
  - security
  - phase-0
milestone: m-0
dependencies:
  - TASK-1
references:
  - decisions/security.md
priority: high
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (Webhooks). Today: /hook/{webhook_id} in app/api/v1/routes/webhooks.py:28-73 authenticates by existence + active flag only (bearer-capability URL); app/modules/webhooks/aws_sns.py:84-85 returns early without SNS signature validation when not app_settings.is_production; 5xx responses interpolate the exception into the body at aws_sns.py:108 and :120 (detail=f"... {e.__class__.__qualname__}: {e}") (SEC-6, OWASP API2:2023).

Steps:
1. SNS: validate the message signature in ALL environments - delete the early-return branch at aws_sns.py:84-85.
2. Generic webhooks: require an HMAC signature header computed with a per-webhook secret; constant-time compare; URL knowledge alone is never sufficient. Provide secret provisioning/rotation notes in the route docstring.
3. Replace every f-string that embeds the exception (class name or str(e)) in a 5xx response body with a generic message; log the full exception server-side instead.
4. Cap webhook body size.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 SNS signature validation runs unconditionally; a test covers an invalid-signature rejection
- [ ] #2 POST /hook/{id} without a valid HMAC signature returns 401/403 even with a correct id (test exists)
- [ ] #3 grep -rn "e.__class__" and f-string exception interpolation in webhook 5xx paths return zero hits; a forced exception yields a generic 500 body (test)
- [ ] #4 Oversized webhook bodies are rejected (test)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass; existing legitimate webhook flows still succeed against the new auth (documented manual check or smoke test)
- [ ] #2 PR references SEC-6 and decisions/security.md
<!-- DOD:END -->

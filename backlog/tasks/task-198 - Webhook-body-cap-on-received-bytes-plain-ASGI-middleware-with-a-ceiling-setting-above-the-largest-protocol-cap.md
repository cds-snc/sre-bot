---
id: TASK-198
title: >-
  Webhook body cap on received bytes: plain ASGI middleware with a ceiling
  setting above the largest protocol cap
status: To Do
assignee: []
created_date: '2026-11-27T16:46:00Z'
labels:
  - security
  - server
  - webhooks
milestone: m-4
dependencies: []
references:
  - decisions/security.md
  - decisions/webhooks.md
  - decisions/cloud-portability.md
priority: high
ordinal: 559000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
doc-11 row 22.3b; a single PR from origin/main, before 22.7 (TASK-37.4.2 mounts the new route). Created at TASK-37.2.2 planning (2026-11-27, human-approved Q6). server/body_size_middleware.py checks only Content-Length, so a chunked request without it skips the cap (OWASP API4:2023), and its 256 KiB ceiling ([server] webhook_max_body_bytes) is below webhooks.md's SNS cap of about twice SNS's 256 KiB message. The WAF excludes /hook/ from the managed rule set and sets no body limit there, so the app is the only body control: it is enforced in the app, the same on every platform, and an edge limit is optional defence in depth in deployment configuration.
Scope: replace the BaseHTTPMiddleware with plain ASGI middleware that counts received bytes on the webhook paths and answers 413 once the ceiling is passed, whether or not Content-Length is present; a declared Content-Length over the ceiling still answers 413 before reading. The ceiling setting default is 524288 (the largest protocol cap, TASK-37.2.2), with a validator keeping it a positive int. The legacy pins read the cap from settings.
Blast radius: every request under /hook/ and /api/v1/hook/; a defect would 413 or pass oversized bodies on the legacy route. Rollback: one revert. Change notice: none (no caller-visible change below the new ceiling).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A chunked body without Content-Length past the ceiling answers 413 and the route handler never runs; a declared Content-Length past it answers 413 before reading (test)
- [ ] #2 The ceiling is a typed [server] setting with default 524288; the TASK-36.2 413 pins pass reading it (test)
- [ ] #3 Paths outside /hook/ and /api/v1/hook/ are not counted (test)
<!-- AC:END -->

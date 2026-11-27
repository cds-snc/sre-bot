---
id: TASK-49
title: >-
  Webhook rate limiting in two layers: per address before lookup, per instance
  after lookup with overrides
status: To Do
assignee: []
created_date: 2026-07-24 15:02
updated_date: '2026-11-27T16:47:00Z'
labels:
  - security
  - phase-4
  - webhooks
milestone: m-4
dependencies:
  - TASK-37.4.3
  - TASK-3
references:
  - decisions/webhooks.md
  - decisions/security.md
  - decisions/configuration.md
  - https://github.com/cds-snc/sre-bot/issues/1344
  - decisions/plugin-architecture.md
priority: medium
ordinal: 73000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Two-layer rate limiting on the webhook ingress (decisions/security.md Webhooks; TASK-168 research packet section 5, row 49, Q4 item 13 and OQ12). A single PR from main, after the cutover.

Today POST /hook/{webhook_id} is limited at a flat 30/minute by the legacy key, sender address plus URL path (finding F-B, comment #2). SNS deliveries for one instance arrive from many shared AWS addresses, so no bucket bounds an instance, and a spray of random ids costs a table read each before any limit that knows the instance applies (OWASP API4).

Scope, in the capability's entrypoints/http.py:
- Before lookup: a per-address limit that counts only unknown or inactive ids and failed verifications, with a short negative cache for unknown ids.
- After lookup: a per-instance limit keyed by instance_ref (never the URL token), with an optional higher limit per instance set through the management API (TASK-37.6.1) for non-legacy-tier instances only; legacy-tier instances keep the default, so the override cannot bypass the TASK-48 migration.
- A limited request answers 429 with Retry-After.
- Limits and the negative-cache TTL in the [webhooks] settings (added here: TASK-37.2.2 planning, 2026-11-27, human-approved, moved the two-layer rate-limit settings to this task, which first reads them).

Size: ~150 production LOC.
Production: prod.
Revert / blast radius: one revert returns to the route default.
Change notice: developer notice: per-webhook limits, 429 with Retry-After, and how to ask for an override (packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Before lookup, a per-address limit counts only unknown or inactive ids and failed verifications, with a short negative cache for unknown ids; deliveries to known instances never count against it (test)
- [ ] #2 After lookup, the limit is keyed by instance_ref, not caller address: two instances called from one address are limited independently (test)
- [ ] #3 A specific non-legacy-tier instance can carry a higher limit than the default, set through the management API, with no header-based mechanism involved (test)
- [ ] #4 An instance without an override, and any legacy-tier instance, uses the default limit: no regression for the general population (test)
- [ ] #5 A limited request answers 429 with Retry-After (test)
- [ ] #6 Limits and the negative-cache TTL are typed [webhooks] settings with defaults (test)
- [ ] #7 grep confirms no header-presence rate-limit exemption exists anywhere in app/ (guards against re-introducing what TASK-3 removed)
- [ ] #8 The PR body carries the developer change notice (review)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Tests pass
- [ ] #2 PR references decisions/security.md (Webhooks and Rate limiting clauses), TASK-3, and TASK-47
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 18:41

---

Settings home is the package-partitioned WebhookSettings / Webhook record (decisions/webhooks.md, decisions/configuration.md), not a central SecuritySettings aggregator. The rate-limited route lives in app/packages/webhooks/interactions/http.py after the TASK-37.4 cutover. Deps unchanged: TASK-47 + TASK-3.

---

created: 2026-11-20T15:18:00Z

---

2026-11-20 (TASK-36.2 finding F-B): the legacy limiter (slowapi default key style) buckets per sender address AND URL path, not per address across webhook ids: each webhook id already has its own bucket, and /hook/x and /api/v1/hook/x are separate buckets. Pinned: durable per-id bucket; test_legacy_only_ per-sender-address bucket. Design the webhook_id key against this.

---

created: 2026-11-25T20:52:00Z

---

2026-11-25 re-cut (TASK-168, human-approved). Old title "Webhook rate limiting keyed by webhook_id with per-webhook elevated limit overrides"; now two layers (TASK-168 packet Q4 item 13). Dependency on TASK-47 dropped (OQ12): rate limits bind regardless of auth state. Old ACs, verbatim (short), and where each intent now lives:
- #1 "The generic webhook route's rate limiter is keyed by webhook_id, not caller IP - two different webhook_ids called from the same source IP are limited independently" -> new AC #2 (keyed by instance_ref, never the URL token).
- #2 "A specific HMAC-authenticated (auth_mode=hmac) webhook_id can be configured with a higher rate limit than the route default, with no header-based mechanism involved" -> new AC #3 (a non-legacy-tier instance; the override is set through the management API).
- #3 "A webhook_id without a configured override, and any legacy auth_mode=none webhook_id, uses the existing route default limit" -> new AC #4.
- #4 "grep confirms no header-presence rate-limit exemption exists anywhere in app/" -> new AC #7 (verbatim).
Old dependency TASK-3 (Done) kept; TASK-37.4.3 replaces TASK-47. Stale path app/api/v1/routes/webhooks.py replaced by the capability's entrypoints/http.py. Nothing is archived.

---
<!-- COMMENTS:END -->

---
id: TASK-49
title: >-
  Webhook rate limiting keyed by webhook_id with per-webhook elevated limit
  overrides
status: To Do
assignee: []
created_date: '2026-07-24 15:02'
updated_date: '2026-07-28 18:41'
labels:
  - security
  - phase-4
  - webhooks
milestone: m-4
dependencies:
  - TASK-47
  - TASK-3
references:
  - decisions/webhooks.md
  - decisions/security.md
  - decisions/configuration.md
  - 'https://github.com/cds-snc/sre-bot/issues/1344'
priority: medium
ordinal: 73000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aligns with decisions/security.md (Webhooks, amended 2026-07-24): 'rate limits are keyed per webhook_id' ... 'default limits apply to all routes' but nothing implements this yet. Today POST /hook/{webhook_id} in app/api/v1/routes/webhooks.py is rate-limited via the global Limiter key_func (get_remote_address, per-IP once TASK-3 lands) at a flat 30/minute - every webhook_id sharing one source IP shares one bucket; there is no per-webhook_id key and no way to grant a specific known sender a higher ceiling without a header-based exemption (the pattern TASK-3 removes).

This closes that gap using the identity TASK-47 introduces: once a webhook has a verified per-webhook secret (auth_mode=hmac), its webhook_id is a trustworthy key - keying the limiter by webhook_id (not IP) and allowing a configured elevated ceiling for specific migrated webhook_ids (e.g. the Sentinel alerting webhook, once TASK-48 migrates it off the legacy unsigned tier) becomes safe, spoof-proof, and requires no Entra ID/JWT work - superseding the Entra-ID/per-principal-JWT idea floated in TASK-3 comments #1/#2, which does not fit this webhook ingress path (that path is for authenticated API routes per decisions/security.md's general Rate limiting clause, not for webhooks, which have their own clause).

Steps:
1. Route-scoped key_func for POST /hook/{webhook_id}: return a key derived from the path's webhook_id (e.g. f"webhook:{webhook_id}"), overriding the global per-IP key_func for this route only (slowapi's @limiter.limit(..., key_func=...) supports a per-route override - confirmed against the installed slowapi version).
2. Per-webhook limit override: extend the webhook record/settings (SecuritySettings or the webhook record itself, per TASK-47's settings home) with an optional elevated limit value; the route's limit_value becomes a callable that looks up that webhook_id's override, falling back to the existing route default (slowapi's Limiter.limit() accepts limit_value as a callable, confirmed against the installed slowapi version).
3. Only HMAC-authenticated (auth_mode=hmac) webhook_ids may carry an elevated override - a legacy auth_mode=none webhook_id keeps the route default, so this cannot be used to bypass the intent of TASK-47/48's migration.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The generic webhook route's rate limiter is keyed by webhook_id, not caller IP - two different webhook_ids called from the same source IP are limited independently (test)
- [ ] #2 A specific HMAC-authenticated (auth_mode=hmac) webhook_id can be configured with a higher rate limit than the route default, with no header-based mechanism involved (test)
- [ ] #3 A webhook_id without a configured override, and any legacy auth_mode=none webhook_id, uses the existing route default limit - no regression for the general population (test)
- [ ] #4 grep confirms no header-presence rate-limit exemption exists anywhere in app/ (guards against re-introducing what TASK-3 removed)
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
<!-- COMMENTS:END -->

---
id: TASK-46
title: 'Webhook request-origin observability: fingerprint inbound senders'
status: To Do
assignee: []
created_date: '2026-07-24 13:58'
labels:
  - security
  - phase-0
milestone: m-0
dependencies:
  - TASK-7
references:
  - decisions/security.md
priority: high
ordinal: 70000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Phase 1 of the observability-first webhook-auth migration mandated by decisions/security.md (Webhooks, amended 2026-07-24). Purely additive: no request is ever rejected and no sender-visible behaviour changes. Builds the known-sender inventory that Phase 4 (m-4) uses to migrate each legacy unsigned webhook onto a signed tier.

Today app/api/v1/routes/webhooks.py:handle_webhook already binds webhook_id, path, user_agent and ip_address on its logger. This task turns that into a durable, queryable origin fingerprint per invocation.

Steps:
1. Emit one structured `webhook_invocation` event per POST /hook/{webhook_id} with: webhook_id, source IP, user-agent, the inferred/matched payload type (which handler in modules/webhooks/base.handle_webhook_payload matched - AwsSnsPayload / AccessRequest / SimpleTextPayload / generic), and presence/absence of any signature-ish headers (so we learn which senders could already sign).
2. Do not log full request bodies; fingerprint metadata only (avoid sensitive-data leakage per decisions/observability.md).
3. Expose the fingerprint as metrics/queryable fields keyed by webhook_id + inferred source type so an inventory of live senders per webhook_id can be built.
4. Document (route/module docstring) that this data is the input to the Phase-4 monitor-then-enforce migration.

Out of scope: any rejection, signature verification, or settings/schema change that alters acceptance (those are the m-4 tasks).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A structured webhook_invocation event is emitted for every POST /hook/{webhook_id} carrying webhook_id, source IP, user-agent, matched payload type, and signature-header presence (test asserts the event fields)
- [ ] #2 No request is rejected or otherwise behaviourally changed by this task; legitimate webhook flows are byte-for-byte unaffected (test)
- [ ] #3 Request bodies are never emitted to logs/metrics; only fingerprint metadata is (test/review)
- [ ] #4 Fingerprint data is queryable/aggregatable per webhook_id + inferred source type (documented query or metric)
<!-- AC:END -->

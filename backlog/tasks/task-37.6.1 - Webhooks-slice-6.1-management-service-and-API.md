---
id: TASK-37.6.1
title: 'Webhooks slice 6.1: management service and API'
status: To Do
assignee: []
created_date: '2026-11-25T20:49:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.2.2
  - TASK-37.4.1
references:
  - decisions/webhooks.md
  - decisions/managed-content.md
  - decisions/authorization.md
  - decisions/security.md
parent_task_id: TASK-37.6
priority: high
ordinal: 547000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The control-plane service and its API (TASK-168 research packet section 5, row 37.6a, and Q10). A single PR from main, in parallel with TASK-37.4.2 and 37.4.3.

Scope:
- WebhookAdmin, the only writer of instances (managed-content.md one write path). Until TASK-37.8 builds versions on the managed-content store, writes are conditional updates plus audit events.
- /api/v1/webhooks in the capability's entrypoints/http.py: list, get, create, update (channel, sender kinds, destinations, owner), disable and enable, rotate the secret, set auth_tier, deliveries (the last N inbox items: time, kind, outcome, attempts; never the payload) and replay of dead items. Authenticated with get_current_user and the webhooks:admin permission, with an optional per-team scope; deny by default.
- Instance model: active | disabled, auth_tier (legacy | monitor | enforce), protocol, sender kinds, destinations, a required owner (team and contact), sunset_at, expires_at, instance_ref. hook_type is retired into the kinds' event types and destinations.
- AU-3 audit events on every write; reveal is audited for the legacy tier.
- The legacy /sre webhooks surface stays until TASK-37.6.2.

Out of scope: the Slack binding and deleting the legacy admin (TASK-37.6.2); HMAC issuance (TASK-47, built on this service); versions, export and the kill switch (TASK-37.8).

Size: ~380 production LOC, ~9 files.
Production: prod (new authenticated routes).
Revert / blast radius: one revert; ingest is unaffected.
Change notice: developer notice, no action: a new authenticated /api/v1/webhooks, who may use it and the permission it needs (packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 WebhookAdmin is the only writer of instances and its writes are conditional updates (test + grep)
- [ ] #2 /api/v1/webhooks offers list, get, create, update, disable and enable, rotate, set auth_tier, deliveries and replay of dead items; each route authenticates with get_current_user and requires webhooks:admin, deny by default (tests for success and for 401 and 403 per route)
- [ ] #3 Deliveries list the last N inbox items with time, kind, outcome and attempts and never a payload (test)
- [ ] #4 Every write and every legacy-tier reveal emits an AU-3 audit event (test)
- [ ] #5 Create requires an owner; the instance model carries active or disabled, auth_tier, protocol, sender kinds, destinations, owner, sunset_at, expires_at and instance_ref (test)
- [ ] #6 The router has exactly one OpenAPI tag, a summary and description per route, described schema fields and explicit non-2xx response mappings (test + review)
- [ ] #7 Ingest is unaffected and the legacy /sre webhooks surface still works (TASK-36 smoke)
- [ ] #8 The PR body carries the developer change notice (review)
<!-- AC:END -->

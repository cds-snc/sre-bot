---
id: TASK-37.1
title: 'Webhooks slice 1: Webhook domain model + StorageService-backed store'
status: To Do
assignee: []
created_date: '2026-07-28 18:39'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-7
  - TASK-36
references:
  - decisions/webhooks.md
  - decisions/layers.md
  - decisions/feature-packages.md
parent_task_id: TASK-37
priority: high
ordinal: 96000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 1 of the webhooks rearchitecture (decisions/webhooks.md; coordinator TASK-37). Behaviour-preserving: no webhook URL or acceptance behaviour changes; the TASK-36 smoke suite stays green.

Goal: stand up the durable data layer of the new package and route all webhook persistence through it, removing the raw-DynamoDB-item-shape leakage, WITHOUT yet touching payload parsing or dispatch (those are TASK-37.2 / TASK-37.3).

Scope:
1. Create the app/packages/webhooks/ skeleton: __init__.py (empty hookimpl surface, no registration yet), providers.py (feature-local DI), settings.py with a partitioned WebhookSettings (per decisions/configuration.md; add a default-rate-ceiling placeholder field). Do NOT move TASK-7's WEBHOOK_MAX_BODY_BYTES in this slice.
2. domain.py: a frozen dataclass Webhook (id, name, channel, source: WebhookSource, hook_type, active, created_at, user_id, invocation_count, acknowledged_count). Add a WebhookSource enum (AWS_SNS, ACCESS_REQUEST, SIMPLE_TEXT, GENERIC) used as data only this slice; default existing records to GENERIC. Do NOT add auth_mode/secret here (TASK-47 owns those).
3. store.py: a WebhookStore over the infrastructure.storage StorageService Protocol (mirror app/packages/access/sync/store.py::SyncRunRepository). Implement create/get/list/update/delete/toggle/revoke/increment_invocation/increment_acknowledged mapping the frozen model to/from storage, replacing modules/slack/webhooks.py's hand-built dynamodb.* calls. Reuse the existing 'webhooks' table; no schema/terraform change.
4. Repoint callers: app/api/v1/routes/webhooks.py and the /sre webhook admin command read/write via a provider-resolved WebhookStore + frozen model, so no caller handles {'S':..}/{'BOOL':..} shapes. Route otherwise unchanged (still calls the legacy handle_webhook_payload for now).
5. Leave modules/webhooks/* and the legacy select_best_model path intact this slice (deleted in TASK-37.3 / TASK-37.4).

Out of scope: payload parsing redesign (TASK-37.2), intent/renderer (TASK-37.3), cutover/delete (TASK-37.4), auth_mode/secret (TASK-47).

Verify before/while implementing: StorageService TypeSerializer returns Decimal for ints (memory) - if invocation_count/acknowledged_count are consumed as int anywhere, convert on read or store JSON-encoded; confirm the 'webhooks' table attribute names when mapping the model.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A frozen Webhook domain model and a StorageService-backed WebhookStore exist; all webhook persistence goes through the store, with no direct integrations.aws.dynamodb calls left in the webhook read/write path (test + review)
- [ ] #2 No caller above the store handles raw DynamoDB item shapes (S/BOOL wrappers); the route and admin surface speak the Webhook model (grep + test)
- [ ] #3 Webhook URLs and behaviour are unchanged: TASK-36 smoke tests pass before and after
- [ ] #4 import-linter is green: packages/webhooks imports integrations only inside adapters/ (none in this slice)
<!-- AC:END -->

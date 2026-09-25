---
id: TASK-37.1
title: 'Webhooks slice 1: Webhook domain model + StorageService-backed store'
status: To Do
assignee: []
created_date: '2026-07-28 18:39'
updated_date: '2026-09-24 20:03'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-7
  - TASK-36
  - TASK-27.2
  - TASK-108
  - TASK-109
  - TASK-114
references:
  - decisions/webhooks.md
  - decisions/feature-packages.md
  - 'https://github.com/cds-snc/sre-bot/issues/1376'
  - decisions/plugin-architecture.md
parent_task_id: TASK-37
priority: high
ordinal: 96000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rescoped 2026-09-24: webhooks is a capability at app/capabilities/webhooks/ (decisions/webhooks.md, decisions/plugin-architecture.md), not a feature package. It reaches storage, coordination, the queue and the Slack reply surface only through contracts resolved from the service registry, and imports no infrastructure/ or server/ module, so no slice adds an import-linter ignore entry. There is no in-process event bus: features react through the capability's extension point.

Slice 1 of the webhooks rearchitecture (decisions/webhooks.md; coordinator TASK-37). Behaviour-preserving: no webhook URL or acceptance behaviour changes; the TASK-36 smoke suite stays green.

Goal: stand up the durable data layer of the new package and route all webhook persistence through it, removing the raw-DynamoDB-item-shape leakage, WITHOUT yet touching payload parsing or dispatch (those are TASK-37.2 / TASK-37.3).

Scope:
1. Create the app/capabilities/webhooks/ skeleton: __init__.py (empty hookimpl surface, no registration yet), providers.py (feature-local DI), settings.py with a partitioned WebhookSettings (per decisions/configuration.md; add a default-rate-ceiling placeholder field). Do NOT move TASK-7's WEBHOOK_MAX_BODY_BYTES in this slice.
2. domain.py: a frozen dataclass Webhook (id, name, channel, source: WebhookSource, hook_type, active, created_at, user_id, invocation_count, acknowledged_count). Add a WebhookSource enum (AWS_SNS, ACCESS_REQUEST, SIMPLE_TEXT, GENERIC) used as data only this slice; default existing records to GENERIC. Do NOT add auth_mode/secret here (TASK-47 owns those).
3. store.py: a WebhookStore over the storage contract (StorageService in app/contracts/, TASK-108) resolved from the service registry (TASK-109) (mirror app/packages/access/sync/store.py::SyncRunRepository). Implement create/get/list/update/delete/toggle/revoke/increment_invocation/increment_acknowledged mapping the frozen model to/from storage, replacing modules/slack/webhooks.py's hand-built dynamodb.* calls. Reuse the existing 'webhooks' table; no schema/terraform change.
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
- [ ] #4 import-linter is green with no new ignore entry: capabilities/webhooks imports no infrastructure/ or server/ module, and imports integrations only inside adapters/ (none in this slice)
- [ ] #5 Invocation and acknowledgement counters are written with a single atomic storage operation exposed by the StorageService Protocol, never a read-modify-write (decisions/webhooks.md), and the in-memory fake honours the same semantics
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: @claude
created: 2026-09-16 13:47
---
2026-09-16 review of TASK-25.2.5: TASK-27 added as a dependency. Scope item 3 requires the WebhookStore to expose increment_invocation/increment_acknowledged over the StorageService Protocol, but that Protocol (app/infrastructure/storage/protocol.py) offers only put, put_if_not_exists, get, query and delete. There is no update and no atomic counter operation, and decisions/webhooks.md forbids resolving that with a read-modify-write. Without TASK-27 this slice would either grow a vendor-shaped update on the Protocol (the exact leak TASK-27 exists to remove, see decisions/cloud-portability.md contract 4) or hand-roll a race. New AC#5 pins the atomicity requirement. Two further gaps for whoever plans this slice: (a) list_all_webhooks and lookup_webhooks are DynamoDB scans today and the Protocol has no scan or list equivalent either, so the store needs a capability-shaped answer for full-table reads; (b) AC#4 assumes import-linter is running, but it is not installed or wired in app/ today (decisions/toolchain.md still describes it as pending) - the working precedent is the freeze-baseline guard scripts under app/bin/.
---

author: @claude
created: 2026-09-16 13:59
---
2026-09-16: dependency retargeted from TASK-27 to TASK-27.2 now that TASK-27 is decomposed. TASK-27.2 is the slice that adds the atomic update, the atomic numeric increment and the bounded full-table list this store needs, and it is scoped to land with this task as its first consumer - merge it immediately before this slice, or in the same PR if the size gate allows. TASK-27.1 (the typed key-condition read) is a prerequisite of TASK-27.2 and so is transitively required.
---
<!-- COMMENTS:END -->

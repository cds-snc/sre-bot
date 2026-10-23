---
id: TASK-37
title: >-
  Rearchitect modules/webhooks into the app/capabilities/webhooks/ ingress
  capability
status: To Do
assignee: []
created_date: 2026-07-07 19:56
updated_date: '2026-10-23T17:10:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-7
  - TASK-36.2
references:
  - decisions/webhooks.md
  - decisions/migration.md
  - decisions/feature-packages.md
  - https://github.com/cds-snc/sre-bot/issues/1291
  - decisions/plugin-architecture.md
priority: high
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Webhooks is a capability at app/capabilities/webhooks/ (decisions/webhooks.md, decisions/plugin-architecture.md), not a feature package. It reaches records, coordination, the queue and the Slack reply surface only through contracts resolved from the service registry, and imports no infrastructure/ or server/ module, so no slice adds an import-linter ignore entry. There is no in-process event bus: features react through the capability's extension point.

Rearchitect app/modules/webhooks, the webhook CRUD and admin views in app/modules/slack/ (webhooks.py, webhooks_create.py, webhooks_list.py) and the admin registration in app/modules/sre/webhook_helper.py into the app/capabilities/webhooks capability per decisions/webhooks.md. This is a REARCHITECTURE, not a lift-and-shift, so the HMAC hardening (TASK-47) is built on the target design instead of on legacy CRUD.

Coordinator only. This task is implemented by slices TASK-37.1..TASK-37.5 and closes when all slices are Done and the acceptance criteria below hold end-to-end. Do NOT write production code directly against this task; pick up the specific slice.

Target end state (decisions/webhooks.md): a verify -> interpret (by declared source) -> dispatch (multi-sink) pipeline; source-declared typed parsing replacing the probabilistic select_best_model / validate_string_payload_type guessers; a transport-neutral domain intent replacing the Slack-Block-Kit terminal shape; multi-sink dispatch (transport render | handler registered through the capability extension point | durable enqueue) enabling non-Slack transports and cross-feature triggering without feature-to-feature imports; a frozen Webhook domain model over RecordStore; idempotent ingest; and a secure-by-default lifecycle.

Slices (single-PR each):
- TASK-37.1 Domain model + RecordStore-backed store (behaviour-preserving).
- TASK-37.2 Source-declared typed parsing + idempotent ingest (delete the guessers).
- TASK-37.3 Transport-neutral intent + Slack renderer (delete the filesystem-walk registries).
- TASK-37.4 Cutover: package serves the routes and the /sre webhooks admin surface; delete app/modules/webhooks and the legacy CRUD.
- TASK-37.5 Multi-sink dispatch fan-out (registered-handler and enqueue targets; build-on-demand; waits on TASK-34 and TASK-113).

Follow-on tickets (NOT children of this coordinator): TASK-47 (lifecycle + HMAC secure-by-default), TASK-48 (legacy unsigned-sender enforcement burn-down), TASK-49 (per-webhook_id rate limiting).

External contract: the webhook URLs and behaviour are held by the TASK-36.2 route pins and the TASK-36.1.4 admin-interaction pins, green before and after each slice cutover. Carry forward (do not regress) the hardening already on the legacy code: TASK-7 (SNS signature verification in all environments, exception-leak removal, body-size cap) and TASK-46 (origin fingerprint, which seeds each record's declared source).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/webhooks/ matches the feature-packages layout for a capability (api.py, hookspecs.py, README classification); the package-shape check and import-linter are green with no new ignore entry
- [ ] #2 Webhook URLs, the /sre webhooks admin surface and their behaviour are unchanged: the TASK-36.2 and TASK-36.1.4 pins pass before and after cutover
- [ ] #3 app/modules/webhooks/ and app/modules/sre/webhook_helper.py are deleted and the webhook CRUD and admin views in app/modules/slack/ are deleted or relocated into the capability; webhook_helper is absent from the legacy registration list in server/lifespan.py; modules/slack/webhooks.py leaves the packages/aws_platform seam baseline
- [ ] #4 Deprecated-import and import-linter baselines shrank or held (never grew)
- [ ] #5 No payload-guessing (select_best_model / validate_string_payload_type / has_parameters_in_model) and no filesystem-walk handler registration remain; each webhook parses via exactly one source-declared model and dispatch is transport-neutral (grep + review)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Smoke suite green post-cutover; other-team-facing surface verified unchanged
- [ ] #2 PR series references decisions/migration.md recipe
<!-- DOD:END -->

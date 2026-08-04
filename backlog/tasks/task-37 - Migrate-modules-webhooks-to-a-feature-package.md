---
id: TASK-37
title: Rearchitect modules/webhooks into a multi-transport ingress feature package
status: To Do
assignee: []
created_date: '2026-07-07 19:56'
updated_date: '2026-07-28 18:39'
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
  - decisions/migration.md
  - decisions/feature-packages.md
  - decisions/layers.md
  - 'https://github.com/cds-snc/sre-bot/issues/1291'
priority: high
ordinal: 37000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rearchitect app/modules/webhooks into the app/packages/webhooks feature package per decisions/webhooks.md. This is the first strangler target (decisions/migration.md) but is a REARCHITECTURE, not a lift-and-shift, and is pulled forward into m-4 (ahead of the general m-5 strangler) so the Phase-4 HMAC hardening (TASK-47) is built on the target design instead of on legacy CRUD and rewritten later.

Coordinator only. This task is implemented by slices TASK-37.1..TASK-37.5 and closes when all slices are Done and the acceptance criteria below hold end-to-end. Do NOT write production code directly against this task; pick up the specific slice.

Target end state (decisions/webhooks.md): a verify -> interpret (by declared source) -> dispatch (multi-sink) pipeline; source-declared typed parsing replacing the probabilistic select_best_model / validate_string_payload_type guessers; a transport-neutral domain intent replacing the Slack-Block-Kit terminal shape; multi-sink dispatch (transport render | domain event | durable enqueue) enabling non-Slack transports and cross-feature triggering without feature-to-feature imports; a frozen Webhook domain model over StorageService; idempotent ingest; and a secure-by-default lifecycle.

Slices (single-PR each, sequential):
- TASK-37.1 Domain model + StorageService-backed store (behaviour-preserving).
- TASK-37.2 Source-declared typed parsing + idempotent ingest (delete the guessers).
- TASK-37.3 Transport-neutral intent + Slack renderer (delete the filesystem-walk registries).
- TASK-37.4 Cutover: package serves the routes; delete app/modules/webhooks.
- TASK-37.5 Multi-sink dispatch fan-out (event/enqueue targets; build-on-demand).

Follow-on tickets (NOT children of this coordinator): TASK-47 (lifecycle + HMAC secure-by-default), TASK-48 (legacy unsigned-sender enforcement burn-down), TASK-49 (per-webhook_id rate limiting).

External contract: the webhook URLs and behaviour are held by the TASK-36 smoke suite, green before and after each slice cutover. Carry forward (do not regress) the Phase-0 work already landed on the legacy code: TASK-7 (SNS signature verification in all environments, exception-leak removal, body-size cap) and TASK-46 (origin fingerprint, which seeds each record's declared source).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/packages/webhooks/ matches the feature-packages layout table; import-linter green
- [ ] #2 Webhook URLs and behavior unchanged: task-36 smoke tests pass before and after cutover
- [ ] #3 app/modules/webhooks/ deleted; module absent from the legacy registration list
- [ ] #4 Deprecated-import and import-linter baselines shrank or held (never grew)
- [ ] #5 No payload-guessing (select_best_model / validate_string_payload_type / has_parameters_in_model) and no filesystem-walk handler registration remain; each webhook parses via exactly one source-declared model and dispatch is transport-neutral (grep + review)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Smoke suite green post-cutover; other-team-facing surface verified unchanged
- [ ] #2 PR series references decisions/migration.md recipe
<!-- DOD:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-07-28 18:38
---
Reframed from lift-and-shift to a refactor-first rearchitecture per decisions/webhooks.md and the amended decisions/migration.md webhooks clause (Option A). Moved m-5 -> m-4 so TASK-47 HMAC is built on the target design. Decomposed into slices TASK-37.1..37.5; original ACs retained as the all-slices-done coordinator bar, plus one end-state AC for the deleted antipatterns.
---
<!-- COMMENTS:END -->

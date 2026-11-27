---
id: TASK-37
title: >-
  Rearchitect modules/webhooks into the app/capabilities/webhooks/ ingress
  capability
status: To Do
assignee: []
created_date: 2026-07-07 19:56
updated_date: '2026-11-25T20:51:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-168
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
Coordinator only. Do not write production code against this task; pick up a slice.

Webhooks is a capability at app/capabilities/webhooks/ (decisions/webhooks.md, rewritten 2026-11-25 by TASK-37.1 from the TASK-168 design session; decisions/plugin-architecture.md). It reaches records, coordination, the queue and the Slack reply surface only through contracts resolved from the service registry, and imports no infrastructure/ or server/ module, so no slice adds an import-linter ignore entry. There is no in-process event bus: features react through the capability's extension point.

Target end state (decisions/webhooks.md):
- Two planes. The data plane ingests and processes deliveries and has no admin operations. The control plane is a WebhookAdmin service, the only writer of instances, behind /api/v1/webhooks with the webhooks:admin permission and audit; /sre webhooks is one Slack binding over it.
- Three layers, with no guessing: the protocol (code: aws_sns, legacy_slack_json, later standard_webhooks, the native protocol and github) verifies and decodes; sender kinds (provisioned content: match, extract, template, optional handler or suppress) map a decoded payload to an event; the instance (managed content, still the webhooks table behind a WebhookStore port) declares its protocol, an ordered list of sender kinds and its destinations.
- A neutral event model: InboundEvent with CloudEvents attribute names; event types alert, notification and slack.passthrough, plus feature-registered types; the type comes from the matched kind, never the payload.
- An async route with a durable inbox: verify, decode, persist (the conditional insert is the delivery-id dedupe), process inline within a deadline, answer 200 once persisted (503 only when the inbox store is down); a lease-guarded sweeper retries and dead-letters; replay through the control plane.
- Features attach through the webhooks hookspec (event consumers by type, handlers by id), collected once at startup. instance_ref, never the URL token, identifies an instance in logs, keys and button values.

Slices:
- TASK-37.1 Provisioned-content loader, with the webhooks.md rewrite and the task re-cut (Stack W, dark).
- TASK-37.2 coordinator: 37.2.1 event model and engines; 37.2.2 async ingest and inbox (Stack W, dark).
- TASK-37.3 Sender kinds as content, the Notify revocation handler and the incident alert consumer (Stack W, dark).
- TASK-37.4 coordinator: 37.4.1 instance backfill; 37.4.2 shadow; 37.4.3 cutover.
- TASK-37.5 Contract: delete the legacy processing and enforce passthrough hardening.
- TASK-37.6 coordinator (control plane): 37.6.1 management service and API; 37.6.2 Slack binding, deleting the legacy admin.
- TASK-37.7 Inbox on QueueService (after TASK-34).
- TASK-37.8 Instances onto managed content (versions, export without secrets, kill switch).

Follow-on tickets (not children): TASK-47 (Standard Webhooks HMAC tier and the native protocol), TASK-48 (caller migration and burn-down of the legacy tier), TASK-49 (two-layer rate limit), TASK-194 (machine principals for class 1 callers, who call feature APIs instead of webhooks).

External contract: webhook URLs never change. Behaviour is held by the TASK-36.2 route pins and the TASK-36.1.4 admin pins; a pin changes only for a named behaviour change, with its reason. Every developer- or user-visible slice ships a change notice (delivery-session change-notice.md). Carry forward the hardening already on the legacy code: TASK-7 (SNS verification in all environments, no exception leakage, body cap) and TASK-46 (origin fingerprint, which seeds the TASK-37.4.1 backfill).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 app/capabilities/webhooks/ matches the feature-packages layout for a capability (api.py, hookspecs.py, README classification); the package-shape check and import-linter are green with no new ignore entry
- [ ] #2 Webhook URLs are unchanged for every caller; the TASK-36.2 and TASK-36.1.4 pins pass after cutover, changed only for a named behaviour change with its reason (test)
- [ ] #3 app/modules/webhooks/ and app/modules/sre/webhook_helper.py are deleted and the webhook CRUD and admin views in app/modules/slack/ are deleted or relocated into the capability; webhook_helper is absent from the legacy registration list in server/lifespan.py; modules/slack/webhooks.py leaves the packages/aws_platform seam baseline
- [ ] #4 Deprecated-import and import-linter baselines shrank or held (never grew)
- [ ] #5 Every delivery is verified and decoded by its instance's declared protocol, persisted to the inbox with delivery-id dedupe before it is acknowledged, and mapped by the instance's declared sender kinds into an InboundEvent dispatched to registered consumers; no payload guessing and no filesystem-walk handler registration remain (grep + review)
- [ ] #6 Instances are written only through WebhookAdmin behind /api/v1/webhooks with the webhooks:admin permission and audit; /sre webhooks is a binding over it (review)
- [ ] #7 Every developer- or user-visible slice shipped its change notice (review)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Smoke suite green post-cutover; other-team-facing surface verified unchanged
- [ ] #2 PR series references decisions/migration.md recipe
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-10-28 (found in TASK-111.14): modules/slack/webhooks_create.py:37-38 and webhooks_list.py:231 write the webhook URL host https://sre-bot.cdssandbox.xyz in code; the rebuild builds it from HostInfo.public_base_url ([server] public_base_url).
<!-- SECTION:NOTES:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-25T20:51:00Z

---

2026-11-25 re-cut (TASK-168, human-approved; TASK-37.1 plan corrections C6-C10). Description rewritten to the two planes, the inbox and the event model; slices are now TASK-37.1 to 37.8. Old ACs, verbatim (short), and where each intent now lives:
- #1 "app/capabilities/webhooks/ matches the feature-packages layout for a capability (api.py, hookspecs.py, README classification); the package-shape check and import-linter are green with no new ignore entry" -> kept verbatim (new AC #1); first checked in TASK-37.2.1 AC #1.
- #2 "Webhook URLs, the /sre webhooks admin surface and their behaviour are unchanged: the TASK-36.2 and TASK-36.1.4 pins pass before and after cutover" -> new AC #2: URLs unchanged; behaviour changes are named (acknowledge after persist in TASK-37.4.3 AC #2; the admin permission, owner field and reveal in TASK-37.6.2 AC #2) rather than none.
- #3 "app/modules/webhooks/ and app/modules/sre/webhook_helper.py are deleted ...; modules/slack/webhooks.py leaves the packages/aws_platform seam baseline" -> kept verbatim (new AC #3); delivered by TASK-37.5 AC #1 and TASK-37.6.2 AC #3.
- #4 "Deprecated-import and import-linter baselines shrank or held (never grew)" -> kept verbatim (new AC #4).
- #5 "No payload-guessing ... and no filesystem-walk handler registration remain; each webhook parses via exactly one source-declared model and dispatch is transport-neutral" -> new AC #5 (declared protocol, declared sender kinds, InboundEvent); delivered by TASK-37.2.x, 37.3 and 37.5 AC #1.
Follow-ons: TASK-47, 48 and 49 rewritten the same day; TASK-194 (machine principals) created. Nothing is archived.

---
<!-- COMMENTS:END -->

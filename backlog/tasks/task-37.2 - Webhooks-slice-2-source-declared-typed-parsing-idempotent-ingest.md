---
id: TASK-37.2
title: 'Webhooks slice 2: source-declared typed parsing + idempotent ingest'
status: To Do
assignee: []
created_date: '2026-07-28 18:39'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.1
  - TASK-46
references:
  - decisions/webhooks.md
  - decisions/plugins.md
  - decisions/reliability.md
parent_task_id: TASK-37
priority: high
ordinal: 97000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Slice 2 of the webhooks rearchitecture (decisions/webhooks.md; coordinator TASK-37). Deletes the probabilistic payload-typing antipattern and adds ingest idempotency. Behaviour-preserving for known senders (TASK-36 smoke green); a generic/simple-text fallback source preserves acceptance for unclassified senders.

Goal: parse each inbound body by the webhook record's DECLARED source, never by guessing.

Scope:
1. schemas.py: one Pydantic model per source at the trust boundary (aws-sns, generic-json, simple-text, access-request). SNS internal variants (SubscriptionConfirmation / UnsubscribeConfirmation / Notification) are a discriminated union on the SNS Type field, NOT separate top-level candidates.
2. router.py: a DECLARATIVE table mapping WebhookSource -> parser -> intent-builder (a plain registry populated in-module or registered at startup via a hookspec per decisions/plugins.md). NO os.listdir, NO importlib.import_module of handler strings, no catch-and-continue.
3. service.ingest(): load the Webhook record (TASK-37.1), select the parser by record.source, parse the normalized body, produce the interim result. Assign source to existing records: default to the fallback source, seeding known records from the TASK-46 fingerprint inventory where available (document the mapping).
4. Remove the guessers from the ACTIVE request path: modules/webhooks/base.py::validate_payload / select_best_model and modules/slack/webhooks.py::validate_string_payload_type / has_parameters_in_model must no longer be called by the route (final dead-code deletion may defer to TASK-37.4 if entangled).
5. Idempotency (decisions/reliability.md): before dispatch, claim webhooks:<webhook_id>:<provider_delivery_id> via infrastructure.idempotency (IdempotencyStore, shipped by TASK-5.1; get_idempotency_store()). provider_delivery_id = SNS MessageId, else a provider delivery header, else - documented last resort only - a stable hash of (webhook_id, body). Branch per reliability.md: NEW -> proceed; COMPLETED -> return recorded outcome; IN_PROGRESS -> reject/defer.
6. Carry forward TASK-7 into verification.py / the SNS parser path: SNS signature verification in ALL environments and generic (non-leaking) 5xx bodies - do not regress.

Out of scope: transport-neutral intent + renderer (TASK-37.3 - this slice may still hand the parsed result to the existing Slack posting path via a temporary adapter shim), cutover/delete (TASK-37.4), HMAC (TASK-47).

Verify: that every live webhook_id can be assigned a source from TASK-46 data; where it cannot, the fallback keeps it working AND emits a source_unclassified signal for the TASK-48 burn-down.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each inbound webhook is parsed by exactly one parser selected from the record's declared source; select_best_model / validate_string_payload_type / has_parameters_in_model are no longer called on the request path (grep + test)
- [ ] #2 SNS sub-types are handled as a discriminated union on the SNS Type field, not as competing top-level payload candidates (test)
- [ ] #3 Ingest is idempotent: a redelivered request with the same provider delivery id executes the effect exactly once (test asserts single dispatch)
- [ ] #4 An unclassified sender still succeeds via the generic/simple-text fallback source and is flagged for migration (test)
- [ ] #5 SNS signature verification in all environments and generic non-leaking 5xx bodies from TASK-7 are preserved (test)
- [ ] #6 Webhook URLs and behaviour are unchanged for known senders: TASK-36 smoke tests pass before and after
<!-- AC:END -->

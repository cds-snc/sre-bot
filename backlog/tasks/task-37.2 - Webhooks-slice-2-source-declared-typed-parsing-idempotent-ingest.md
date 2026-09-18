---
id: TASK-37.2
title: 'Webhooks slice 2: source-declared typed parsing + idempotent ingest'
status: To Do
assignee: []
created_date: '2026-07-28 18:39'
updated_date: '2026-09-18 15:27'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.1
  - TASK-46
  - TASK-58
references:
  - decisions/webhooks.md
  - decisions/plugins.md
  - decisions/reliability.md
  - 'https://github.com/cds-snc/sre-bot/issues/1377'
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

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-09-17 20:48
---
2026-09-17, from planning TASK-25.2.5.4 - a guard this task needs and cannot see from its own description.

This is the FIRST production consumer of the idempotency store for DEDUP rather than for a lease. Verified 2026-09-17: get_idempotency_store() has no production caller today; every live claim() goes through the lease helpers.

That matters because the store's read-failure policy is about to become use-dependent. When the ConsistentRead after a contended claim fails, dedup needs FAIL-CLOSED (the record is the only evidence that an effect already happened, and the protected operation is explicitly not assumed idempotent - that is the point of the key). Under fail-open, a COMPLETED record plus a failed re-read means re-executing a completed operation and then overwriting its recorded outcome.

TASK-100 flips that policy to fail-OPEN for the lease use, which is correct there for the opposite reason (the job body is idempotent, so failing closed just skips a scheduled period). Its AC#3 requires the dedup use to keep fail-closed and the two policies to be an explicit choice rather than one shared default - but if this task lands first and simply calls claim(), whichever default exists at the time is inherited silently.

ACTION FOR THIS TASK'S PLANNER: state explicitly which read-failure policy the webhook ingest claim uses, and assert it rather than inheriting it. TASK-58 is where the per-use choice naturally lives (it builds the idempotency and lease facades over the one primitive); a comment there records the split. No dependency wired in either direction - just do not assume the default.
---

created: 2026-09-18 15:27
---
2026-09-18 (human decision): TASK-58 is now a real dependency, replacing the advisory comment of 2026-09-17. TASK-58 builds the dedup facade with an explicit fail-closed read-failure policy, and this task's ingest claim consumes that facade. The claim therefore cannot inherit whatever default exists at the time. Order agreed for the primitive: TASK-102, then TASK-58, then TASK-100.
---
<!-- COMMENTS:END -->

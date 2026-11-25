---
id: TASK-37.2
title: >-
  Webhooks slice 2: event model, engines, async ingest and inbox (coordinator of
  37.2.1 and 37.2.2)
status: To Do
assignee: []
created_date: 2026-07-28 18:39
updated_date: '2026-11-25T20:50:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.1
references:
  - decisions/webhooks.md
  - decisions/plugins.md
  - decisions/reliability.md
  - https://github.com/cds-snc/sre-bot/issues/1377
  - decisions/plugin-architecture.md
parent_task_id: TASK-37
priority: high
ordinal: 97000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Coordinator only. Do not write production code against this task; pick up a child.

Stack W layers W2 and W3 (decisions/webhooks.md as rewritten in TASK-37.1). The old single slice (source-declared typed parsing plus idempotent ingest) is split under the size gate (TASK-168 packet OQ10) into:
- TASK-37.2.1 Event model and engines (dark): the capability skeleton, InboundEvent and its event types, SenderKind and WebhookInstance, the matcher, extraction and renderer, the escaping Slack poster, the event-consumer hookspec, the linear email matcher, [webhooks] settings.
- TASK-37.2.2 Async ingest and inbox (dark): the aws_sns and legacy_slack_json protocols, the WebhookStore port, the inbox with conditional-insert dedupe and its state machine, the inline processor, the sweeper, the unmounted async route.

Both are dark and stacked in Stack W (doc-18). Dependencies: the coordinator carries its first child's dependencies (TASK-145.5 and 145.10 precedent).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 TASK-37.2.1 and TASK-37.2.2 are Done
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

created: 2026-11-20T15:18:00Z

---

2026-11-20 (TASK-36.2 findings): F-E equal-priority SNS patterns tie-break by os.listdir order at import (machine-dependent); the pin accepts either winner. F-F budget_auto_adjustment matches but returns no blocks, so the route answers 400 and SNS retries; pinned test_legacy_only_. Retry-After rounding is unreachable at the edge (int setting).

---

created: 2026-11-25T20:50:00Z

---

2026-11-25 re-cut (TASK-168, human-approved; TASK-37.1 plan corrections C6-C10). Old title "Webhooks slice 2: source-declared typed parsing + idempotent ingest". This task becomes the coordinator of TASK-37.2.1 and TASK-37.2.2. Old ACs, verbatim (short), and where each intent now lives:
- #1 "Each inbound webhook is parsed by exactly one parser selected from the record's declared source; select_best_model / validate_string_payload_type / has_parameters_in_model are no longer called on the request path" -> TASK-37.2.2 AC #2 (declared protocol, no other model tried); the guessers are deleted in TASK-37.5 AC #1.
- #2 "SNS sub-types are handled as a discriminated union on the SNS Type field" -> TASK-37.2.2 AC #2.
- #3 "Ingest is idempotent: a redelivered request with the same provider delivery id executes the effect exactly once" -> TASK-37.2.2 AC #4 (the inbox insert is the dedupe, fail-closed).
- #4 "An unclassified sender still succeeds via the generic/simple-text fallback source and is flagged for migration" -> the legacy_slack_json protocol (TASK-37.2.2) and the instance fallback rendering with webhook_unmatched (decisions/webhooks.md); flagged by the TASK-37.4.1 backfill and burned down by TASK-48.
- #5 "SNS signature verification in all environments and generic non-leaking 5xx bodies from TASK-7 are preserved" -> TASK-37.2.2 AC #1 (403 generic body) and TASK-37.4.3 AC #7.
- #6 "Webhook URLs and behaviour are unchanged for known senders: TASK-36 smoke tests pass before and after" -> TASK-37.4.2 AC #5 and TASK-37.4.3 AC #8.
- #7 "The SNS verifier accepts SignatureVersion 1 (SHA1) and 2 (SHA256) per TASK-168's ruling" -> TASK-37.2.2 AC #1.
Comments #1 and #2 (fail-closed dedupe through the TASK-58.2 facade) -> TASK-37.2.2 description and AC #4. Comment #3 findings F-E and F-F -> tests in TASK-37.3 (AC #4).
Old dependencies: TASK-46, TASK-58, TASK-109 (all Done) dropped; TASK-58.2 moves to TASK-37.2.2. Nothing is archived.

---
<!-- COMMENTS:END -->

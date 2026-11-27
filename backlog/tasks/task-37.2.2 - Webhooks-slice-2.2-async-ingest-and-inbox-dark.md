---
id: TASK-37.2.2
title: 'Webhooks slice 2.2: async ingest and inbox (dark)'
status: To Do
assignee: []
created_date: '2026-11-25T20:48:00Z'
updated_date: '2026-11-26T13:23:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.2.3
  - TASK-58.2
references:
  - decisions/webhooks.md
  - decisions/reliability.md
  - decisions/security.md
  - decisions/outbound-clients.md
  - decisions/transport-slack.md
parent_task_id: TASK-37.2
priority: high
ordinal: 542000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack W layer W3 (decisions/webhooks.md Pipeline and Inbox; decisions/reliability.md; TASK-168 research packet section 5, row 37.2b, and Q4, Q5). The async ingest path and the durable inbox, built and tested but not mounted.

Scope:
- Protocols, code, a closed set registered at startup:
  - aws_sns: SignatureVersion 1 and 2 accepted (the version logged); a bad signature answers 403 with a generic body; an optional per-instance TopicArn allowlist; a SubscriptionConfirmation is confirmed from the inbox item only when SubscribeURL is https on sns.<region>.amazonaws.com, with no redirects; the signing certificate fetched with async httpx from an SNS host only and cached; SNS Type is a discriminated union.
  - legacy_slack_json: passthrough to the slack.passthrough event type, with a fingerprint of the passthrough-hardening fields (enforced in TASK-37.5).
  - A body cap per protocol. The instance declares its protocol: a body that fails its protocol's decode answers 400 and no other model is tried.
- A WebhookStore port over the existing webhooks table (the legacy attributes plus the new optional ones), with an async adapter that offloads with to_thread inside the adapter (outbound-clients.md).
- The inbox store: an atomic conditional insert on webhooks:<instance_ref>:<delivery id> is the dedupe (the TASK-58.2 idempotency facade, fail-closed read policy, as TASK-37.2 comments #1 and #2 require); an item state machine received -> processing (lease) -> done | retry | dead, plus render_failed, every transition a conditional write carrying the ownership token; a TTL setting; items hold the decoded envelope, never raw headers.
- The inline processor within [webhooks] inline_processing_deadline_seconds (default 5 s); no fire-and-forget task (transport-slack.md).
- A lease-guarded sweeper job: retries with backoff, dead-letters after a cap with a webhook_dead_lettered event, one asyncio.Runner per run with its async clients built inside the run.
- The async def route handler (verify, decode, persist, process inline, answer 200; 503 only when the inbox store is unavailable), not mounted.
- A KMS application-level secret helper (encryption context instance_ref), with no consumer yet.
- Two-layer rate-limit settings (enforcement is TASK-49).
- The legacy protocol has no delivery id: no dedupe for legacy_slack_json, a written exception ended by TASK-48, narrowed by an optional Idempotency-Key request header.

Carries the old TASK-37.2 AC #7 (SignatureVersion 1 and 2) and the intent of its ACs #2, #3 and #5.

Out of scope: mounting the route (TASK-37.4.2); sender-kind files and handlers (TASK-37.3); the instance backfill (TASK-37.4.1); rate-limit enforcement (TASK-49); HMAC (TASK-47).

Size: ~450 production LOC, ~10 files (OQ10 split of the old 37.2).
Production: dark. No route is mounted.
Revert / blast radius: one git revert; nothing serves it.
Change notice: none (dark slice, packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The SNS verifier accepts SignatureVersion 1 (SHA1) and 2 (SHA256) per TASK-168's ruling and answers 403 on a bad signature, ending the TASK-36.2 test_legacy_only_ SignatureVersion 2 row (test)
- [ ] #2 SNS sub-types are a discriminated union on the SNS Type field; a body that fails the instance's declared protocol answers 400 and no other model is tried (test)
- [ ] #3 A SubscriptionConfirmation is confirmed from its inbox item only when SubscribeURL is https on an sns.<region>.amazonaws.com host, with no redirects; a TopicArn outside an instance's allowlist is rejected; the certificate fetch is async and cached (test)
- [ ] #4 A redelivered message with the same delivery id is persisted and processed once: the conditional insert is the dedupe and its read-failure policy is fail-closed (test asserts single dispatch)
- [ ] #5 Every inbox state transition is a conditional write carrying the ownership token; the inline attempt and the sweeper never process one item twice (test)
- [ ] #6 The handler answers 200 once the item is persisted, whether processing finished, failed or hit the deadline, and 503 only when the inbox store is unavailable (test)
- [ ] #7 The sweeper runs under a lease, retries with backoff, dead-letters after the cap with a webhook_dead_lettered event, and builds its async clients inside its run (test)
- [ ] #8 legacy_slack_json items are not deduplicated (the written exception), an optional Idempotency-Key header is honoured, and the passthrough-hardening fields are fingerprinted (test)
- [ ] #9 Body caps, the inline deadline, the inbox TTL, retry and rate-limit values are typed [webhooks] settings with defaults; make check-settings-key-ownership is green (test + check)
- [ ] #10 The slice is dark: no route is mounted and production behaviour is unchanged; make check-import-contracts is green with no new ignore entry (check)
- [ ] #11 Protocol decoders parse JSON strictly (RFC 7493): a duplicate key, NaN or Infinity, a lone surrogate, a non-finite number or nesting past the depth limit answers 400 (test)
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-26T13:19:00Z

---

2026-11-26 (TASK-37.2.1 planning, human-approved P1 and P3). Now waits on TASK-37.2.3 (W2b: the extension point and the Slack poster that the inline processor dispatches to) instead of 37.2.1 directly. Protocol placement within the feature-packages.md layout table, since protocols/ is not a table name:
- verify, delivery id and decode per protocol go in entrypoints/http_<protocol>.py (http_aws_sns.py, http_legacy_slack_json.py), beside entrypoints/http.py, following the entrypoints/slack_*.py precedent;
- the Pydantic envelopes go in schemas.py;
- the outbound SNS certificate fetch and the SubscriptionConfirmation call go in adapters/aws_sns.py, behind a Protocol in interfaces.py (with service.py).
Verification stays at the capability's HTTP entrypoint on the raw body, before any handler (Stripe, Svix, GitHub, octokit); the platform-transports.md scope line saying per-instance webhook verification is not host middleware lands with TASK-37.2.1.

---

created: 2026-11-26T13:23:00Z

---

2026-11-26 OWASP review (TASK-37.2.1 planning): every protocol decoder parses JSON strictly per RFC 7493 (I-JSON): duplicate member names, NaN/Infinity, lone surrogates and non-finite numbers are rejected and nesting depth is limited (RecursionError caught), each answering a stable 400 (Bishop Fox, JSON interoperability vulnerabilities; stdlib json keeps the last duplicate silently).

---
<!-- COMMENTS:END -->

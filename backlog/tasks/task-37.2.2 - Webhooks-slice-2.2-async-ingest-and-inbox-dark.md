---
id: TASK-37.2.2
title: 'Webhooks slice 2.2: async ingest and inbox (dark)'
status: In Progress
assignee: []
created_date: '2026-11-25T20:48:00Z'
updated_date: '2026-11-27T16:45:00Z'
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
Stack W layer W3 (decisions/webhooks.md Pipeline, Responses, Canonical model, Authenticity and Security additions; decisions/reliability.md; decisions/outbound-clients.md one retry point). The async ingest path and the durable inbox, built and tested but not mounted.

Scope:
- Protocols, code, a closed set:
  - aws_sns: our own verifier on cryptography, accepting SignatureVersion 1 and 2 (the version logged); a bad signature, an off-host SigningCertURL, a TopicArn outside the instance's allowlist, or a Timestamp past the replay bound answers 403 with a generic body; the signing certificate is fetched async through an httpx factory in integrations/aws_sns/ (SNS host only, no redirects) and cached; a SubscriptionConfirmation is confirmed from the inbox item only when SubscribeURL is https on sns.<region>.amazonaws.com; SNS Type is a discriminated union.
  - legacy_slack_json: passthrough to the slack.passthrough event type, with a fingerprint of the passthrough-hardening fields (enforced in TASK-37.5) and an optional Idempotency-Key header.
  - A body cap and allowed Content-Types per protocol; strict JSON (RFC 7493). The instance declares its protocol: a body that fails its protocol's decode answers 400 and no other model is tried.
- A WebhookStore port over the existing webhooks table (the legacy attributes plus the new optional ones: instance state and topic_arns), async, offloading with to_thread inside the adapter.
- The inbox store on the records contract: the item's own conditional insert on webhooks:<instance_ref>:<delivery id> is the dedupe (anything but a confirmed insert answers 503 and does no work); states received -> processing (lease) -> done | retry | render_failed | dead, every transition a guarded update carrying the owner token; per-target progress so a retry repeats no finished post, consume or handler; a TTL; items hold the decoded envelope, never raw headers. Its table is TASK-37.2.4 (row 22.3a).
- The inline processor within [webhooks] inline_processing_deadline_seconds; no fire-and-forget task.
- The sweeper job (lease, backoff with full jitter, dead-letter with webhook_dead_lettered, one asyncio.Runner per run), built but not registered (TASK-37.4.3 registers it).
- The async def route handler (verify, decode, persist, process inline, answer 200; 503 only when the inbox store is unavailable), not mounted.

Carries the old TASK-37.2 AC #7 (SignatureVersion 1 and 2) and the intent of its ACs #2, #3 and #5.

Out of scope: mounting the route (TASK-37.4.2); registering the sweeper (TASK-37.4.3); the inbox table (TASK-37.2.4); the server body cap (TASK-198); the encryption service for secrets at rest (TASK-197); sender-kind files and handlers (TASK-37.3); the instance backfill (TASK-37.4.1); rate-limit settings and enforcement (TASK-49); HMAC (TASK-47).

Size: about 1,150 production LOC in about 18 files, one PR under a size-gate exception approved by the human on 2026-11-27 (dark).
Production: dark. No route is mounted and no job is registered.
Revert / blast radius: one git revert; nothing serves it.
Change notice: none (dark slice, packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The SNS verifier accepts SignatureVersion 1 (SHA1) and 2 (SHA256) and answers 403 with a generic body on a bad signature, an unknown version, an off-host SigningCertURL or a Timestamp older than the replay bound; the TASK-36.2 SignatureVersion 2 legacy_only pin records the new path's accepting counterpart (test)
- [ ] #2 SNS sub-types are a discriminated union on the SNS Type field; a body that fails the instance's declared protocol answers 400 and no other model is tried (test)
- [ ] #3 A SubscriptionConfirmation is confirmed from its inbox item only when SubscribeURL is https on an sns.<region>.amazonaws.com host, with no redirects; a TopicArn outside an instance's allowlist answers 403; the certificate fetch is async through the integrations/aws_sns factory and cached (test)
- [ ] #4 A redelivered message with the same delivery id is persisted and processed once: the inbox item's conditional insert is the dedupe, and any outcome other than a confirmed insert answers 503 and does no work (test asserts single dispatch)
- [ ] #5 Every inbox state transition is a guarded update carrying the owner token; the inline attempt and the sweeper never process one item twice, and a stale token changes nothing (test)
- [ ] #6 The handler answers 200 once the item is persisted, whether processing finished, failed or hit the deadline, 503 only when the inbox store is unavailable, and 404, 405, 413 and 415 per decisions/webhooks.md Responses (test)
- [ ] #7 The sweeper runs under a lease, retries with backoff (full jitter, retry_after honoured), dead-letters after the cap with a webhook_dead_lettered event, and builds its async clients inside its run (test)
- [ ] #8 legacy_slack_json items are not deduplicated (the written exception), an optional Idempotency-Key header is honoured, the passthrough-hardening fields are fingerprinted by name only, and a payload channel is ignored (test)
- [ ] #9 Body caps, Content-Types, JSON depth, the inline deadline, the lease margin, the inbox table name and TTL, the SNS replay bound and fetch values, and the retry and sweeper values are typed [webhooks] settings with defaults; make check-settings-key-ownership is green (test + check)
- [ ] #10 The slice is dark: no route is mounted, no job is registered and production behaviour is unchanged; make check-import-contracts is green with no new ignore entry and contract (p) lists every new core module (check)
- [ ] #11 Protocol decoders parse JSON strictly (RFC 7493): a duplicate key, NaN or Infinity, a lone surrogate, a non-finite number or nesting past the depth limit answers 400 (test)
- [ ] #12 An item records each finished post, consume and handler, and a retry repeats none of them (test)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
PLAN (2026-11-27). APPROVED 2026-11-27 by the human: Q1 (D1), Q2 (D2, D3), Q3a (D6), Q3b (D7), Q4 (D9), Q5 (D17) and Q6 (D19). Stack W layer W3, above W2b (#1896). Dark: no route mounted, no job registered, no table read in production.

Inputs: decisions/webhooks.md 3, 5, 5a, 6, 9; reliability.md (inbox, ownership, jobs); outbound-clients.md (one retry point, async ports, httpx connect-only retries); lifecycle.md (no network before yield except credential checks; leased jobs); security.md Webhooks and Request limits; deployment.md; contracts/records/store.py (put_if_not_exists, guarded update, sparse index query); contracts/coordination (LeaseStore); TASK-37.2.3 notes on this task.

DECISIONS (each with a recommendation; Q = needs the human)

D1 (Q1) The inbox item's own conditional insert is the dedupe, on the records contract, as the incident status updates already do (features/incident/core/store.py: `put_if_not_exists` to create, then `update(..., expected={"state": ...})` per transition; TASK-140.4, TASK-145.8). `InboxStore.insert` calls `RecordStore.put_if_not_exists` on key `webhooks:<instance_ref>:<delivery id>`: data=True is new, data=False is a duplicate (200, no work), and any other result answers 503 and processes nothing. That is fail-closed: no confirmed insert, no work, and the sender retries. `IdempotencyStore` (contracts/coordination, TASK-58.2, live in features/incident/response/adapters/claims.py) is not used: a coordination record holds only a claim and an outcome, with no envelope, state or index, so persisting would take two writes that cannot be made atomic. Gap fixed in reliability.md, whose text says dedup "and outbox claims are all uses of the one conditional-write primitive ... `ConditionalWriteStore`": a record that carries its own state machine (the inbox, status updates) takes the same primitive through the records contract's conditional insert and guarded update, and its read-failure rule is that any outcome other than a confirmed insert is treated as not persisted. Changes lines in reliability.md and webhooks.md; TASK-37.2.2's description and AC #4 drop "the TASK-58.2 idempotency facade"; a pointer comment on TASK-37.2 (comments #1 and #2).
D2 The inbox gets its own table, `sre_bot_webhook_inbox` (partition `item_key`), with two sparse indexes. `by_due` (partition `due`, a constant, sort `due_at`, epoch seconds) holds only `processing`, `retry` and `received` items, so the sweeper queries `due_at < now` with a batch limit ([sparse indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general-sparse-indexes.html), [priority queueing](https://aws.amazon.com/blogs/database/implementing-priority-queueing-with-amazon-dynamodb/)). `by_instance` (partition `instance_ref`, sort `received_at`) serves TASK-37.6.1 AC #3 (the last N items of an instance), so that row adds no index later. Index reads are eventually consistent, which is harmless because every claim is a guarded write. Items expire through the table's TTL attribute (`[webhooks] inbox_ttl_seconds`, default 7 days, webhooks.md section 3).
D3 (Q2) The table goes in its own single-PR row because deployment.md runs `tf_apply.yml` on a push to main that changes `terraform/` and `build_and_deploy.yml` on any other push, so a PR mixing terraform and app code deploys no app image. No ADR or task creates the inbox table: webhooks.md Consequences names "an inbox table" as a cost, but no row builds it. The row is new subtask TASK-37.2.4, "Webhook inbox table (expand, empty)", doc-11 row 22.3a: a single PR from origin/main that adds the table, both indexes, TTL and an entry in `dynamodb_table_arns` (task-role IAM and backup). It must merge before 22.7 (TASK-37.4.2, which first mounts the route); W3 does not wait on it. Blast radius: one empty table and one more table ARN in the task role. Rollback: a revert never destroys the table; removal is a `removed` block with `lifecycle { destroy = false }`, as the SSM rule (TASK-145.7.13) treats names. bin/deploy-checks.zsh pre and post apply. The table name is a non-secret `[webhooks] inbox_table_name` setting in the configuration files: no SSM name.
D4 Hot path, one write before the answer. The insert writes the item already `processing`, with an owner token and `due_at` = now + inline deadline + `[webhooks] processing_lease_margin_seconds`. Every later transition is `RecordStore.update` with `expected={state, owner}`. Done, render_failed and dead remove `due`/`due_at`; retry sets them to retry_at. The sweeper takes over an expired lease under the old owner's token, so the inline attempt and the sweeper never both own an item (a lost guard means another owner, so nothing is done). This is not fencing (reliability.md): a stale holder's in-flight post is absorbed by D5.
D5 Per-target progress on the item, so a retry never repeats a finished side effect. After each successful post, consumer `consume` or handler, a guarded update adds its target key to the item's `done_targets`; a retry skips those. Without this, a transient failure on destination 2 would re-post destination 1. This one is new: the ADRs say a post is never retried in process, but they don't say a retried item skips the targets that already succeeded. webhooks.md section 3 step 6 gains a sentence.
D6 (Q3a) The application-level encryption service for secrets at rest becomes platform infrastructure, built ahead of its consumers, so the KMS helper leaves this task. organisation-content.md requires it for any managed record holding a non-public value, so its consumers are TASK-47 (webhook secrets) and TASK-37.8 (managed content). It is new top-level TASK-197, with two single PRs from origin/main, rows 22.12a and 22.12b, before 22.13:
- TASK-197.1 is the deployment binding: today's KMS key and task-role IAM, terraform only.
- TASK-197.2 is a cloud-neutral contract in contracts/: `seal(plaintext, *, context)` and `open(sealed, *, context)`, returning opaque versioned bytes that name their key. It has an in-memory fake and a conformance suite (cloud-portability.md contract 4).
- Its infrastructure/ implementation is Google Tink's KMS envelope AEAD: a per-value AES-256-GCM data key bound to the context as associated data, wrapped by a key-encryption key named by a key URI in the configuration files (aws-kms://, gcp-kms://, hcvault://).
- A plaintext cache with TTL and size settings lives in the service.
- An Azure Key Vault wrap/unwrap client is the adapter added on a move to Azure. Consumers, the contract and the stored format don't change.

The AWS Encryption SDK (its message format has only AWS KMS keyrings) and the Database Encryption SDK (it wraps the DynamoDB client and bypasses the records contract) are rejected for portability. The ADR edits land with TASK-197.2: webhooks.md section 9, security.md, organisation-content.md, and cloud-portability.md (a hosting contract). `tink` 1.16.1 (2026-08-13) has cp314 wheels.
D7 (Q3b) The two-layer rate-limit settings move to TASK-49, whose AC #6 already owns them, with no reader until then. TASK-49's "added in TASK-37.2.2" line is corrected.
D8 SNS verification is our own code, in entrypoints/http_aws_sns.py, on `cryptography`. That package is already locked as a transitive dependency; it becomes a direct one at the locked version, so the cooldown rule holds and no new package is added. `aws-sns-message-validator` 0.0.5 is rejected: it accepts only SignatureVersion 1 and fetches the certificate synchronously with requests. Our verifier uses AWS's canonical string per Type: Notification (Message, MessageId, Subject if present, Timestamp, TopicArn, Type); SubscriptionConfirmation and UnsubscribeConfirmation (Message, MessageId, SubscribeURL, Timestamp, Token, TopicArn, Type). Version 1 is RSA PKCS#1 v1.5 with SHA1 and version 2 with SHA256; any other value answers 403, and the version is logged ([AWS: verifying SNS signatures](https://docs.aws.amazon.com/sns/latest/dg/sns-verify-signature-of-message.html), [SHA256 signing](https://aws.amazon.com/blogs/security/sign-amazon-sns-messages-with-sha256-hashing-for-http-subscriptions/)). SigningCertURL is parsed, not matched by regex: https, host exactly `sns.<region>.amazonaws.com` with a region label of lowercase letters, digits and hyphens, no userinfo, port or query, and a path ending `.pem`. Otherwise 403 with no fetch. The certificate is fetched through adapters/aws_sns.py behind an interfaces.py Protocol, on an `httpx.AsyncClient` with `follow_redirects=False`, a per-attempt timeout setting and `AsyncHTTPTransport(retries=[webhooks] sns_connect_retries)` (outbound-clients.md). It is cached per replica by URL, with a TTL and a size cap as settings.
D9 (Q4) Replay bound. An SNS `Timestamp` older than `[webhooks] sns_max_message_age_seconds` answers 403. The default is 24 h, and a validator keeps it no larger than the inbox TTL. SNS's HTTP/S retries end within 3,600 s, a hard limit ([SNS delivery retries](https://docs.aws.amazon.com/sns/latest/dg/sns-message-delivery-retries.html)), so 24 h leaves room for clock skew and self-throttling. Dedup forgets a key once its item expires, so a replay of a captured, validly signed message after the TTL would post again. OWASP pairs "a signed timestamp with tolerance plus event-id dedup", and webhooks.md section 9 lists the same pairing.
D10 The TopicArn allowlist and instance state. WebhookInstance gains `state` (active | disabled) and `topic_arns` (a tuple; empty means no allowlist until backfilled, per security.md "enforced once backfilled"). A TopicArn outside a non-empty list answers 403. WebhookStore over the existing `webhooks` table returns an instance only for a provisioned item (`instance_ref` and `protocol` present). A legacy-only item, or a disabled one, is None, which answers 404 on the new path. The new attributes are optional, so legacy code ignores them.
D11 The decoded SNS document that sender kinds match on is the envelope's signed fields, with `Message` replaced by its strict-JSON parse when that parse is an object and left as a string otherwise. TASK-37.3's kinds then match `$.Message.AlarmName`. webhooks.md section 2 records this, since it is the content contract for SNS kinds.
D12 HTTP edge per protocol. The allowed Content-Types are a setting per protocol: aws_sns takes `text/plain` (what SNS sends) and `application/json`; legacy_slack_json takes `application/json`. Anything else answers 415. The body is read as a stream and answers 413 once it passes the protocol's cap (aws_sns 512 KiB, twice SNS's 256 KiB; legacy 256 KiB), before verify. JSON is parsed strictly (RFC 7493) in domain/strict_json.py: duplicate names through `object_pairs_hook`, NaN and Infinity through `parse_constant`, non-finite numbers through `parse_float`, lone surrogates by a walk, and depth past `[webhooks] max_json_depth` (default 64) by an iterative walk with RecursionError caught. Python's int digit limit already raises. Each answers 400. Only POST is routed, so FastAPI answers 405 to other methods. Error bodies are generic.
D13 legacy_slack_json. The delivery id is `local:<uuid>`, so nothing is deduplicated (the written exception), unless an `Idempotency-Key` header is present. That header must be printable ASCII of at most `[webhooks] idempotency_key_max_chars` (default 255); then the key becomes `idem:<key>` under the instance's prefix and is deduplicated. A malformed header answers 400. The passthrough-hardening fingerprint holds the sorted names of the fields present (callback_id, action_id, block_id, parse, link_names, username, icon_*, thread_ts, reply_broadcast, and interactive elements without a url), never their values, and goes on the item and the ingest log event. A payload `channel` is ignored: the destination decides (section 5a).
D14 Passthrough posting. `OutboundMessage` gains `PassthroughMessage`. The Slack adapter posts it to the destination's conversation, unhardened for now (hardening is monitored in TASK-37.4.2 and enforced in TASK-37.5), with the same per-attempt timeout and no in-process retry. `poster_for` already skips non-Slack destinations.
D15 The processor (service.py) follows TASK-37.2.3's notes. Per item it:
- resolves the instance's kinds from the ContentCatalogue and runs `interpret`;
- for each destination, resolves `LanguagePolicy.shared_languages(system, tenant, conversation_id)` and renders;
- picks the poster with `poster_for(get_channel_posters(), destination, event type)`, where a missing poster is skipped and reported;
- takes one `DeliveryPoster` per item through `for_delivery()`;
- gathers `actions_for` only where the destination sets triage;
- calls each consumer's `consume` once and the kind's handler from the item, each with `EventContext(item_id, service_scopes)`.

Unmatched and RenderFailed post `fallback_message` and leave the item `render_failed`, with `webhook_unmatched` and `webhook_render_failed`; Suppressed is done. A SubscriptionConfirmation is confirmed through the aws_sns adapter (SubscribeURL already host-checked at decode, no redirects, timeout); an UnsubscribeConfirmation is logged and done. A TRANSIENT_ERROR sets retry_at to the later of the backoff and `retry_after`. Any other failure retries with backoff until the cap, then dead with `webhook_dead_lettered` (instance_ref, kind id, attempts; no payload). Backoff is exponential with full jitter, with `retry_base_seconds`, `retry_max_seconds` and `retry_max_attempts` as settings ([AWS Builders' Library](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)). The inline call runs inside `asyncio.timeout(inline_processing_deadline_seconds)`; on timeout the item keeps its lease and the sweeper takes it after expiry. service.py never imports providers.py: posters, translator, catalogue and stores are passed in by the entrypoint or the job.
D16 The sweeper is built but not registered. `entrypoints/jobs.py` has a sync job body that opens one `asyncio.Runner` per run. Inside the run it builds its async clients from providers.py, queries due items (`sweeper_batch_size`), claims each under its token and processes it. This follows the precedent of features/incident/response/legacy_upgrade_job.py. The webhooks plugin is enabled in base.toml, so a job registered now would run in production against a table that does not exist yet. Registration through `register_background_jobs` with `lease_ttl` becomes a new AC on TASK-37.4.3, the first instance on the pipeline. The route router in entrypoints/http.py is likewise not included (TASK-37.4.2 AC #1).
D17 Size: about 1,150 production LOC in about 18 files, past the gate. Approved by the human on 2026-11-27 as one W3 layer under a size-gate exception: every part is dark, and the production-changing table is its own row (D3).
D19 (Q6) The server body cap becomes cloud-neutral and is enforced on received bytes: new TASK-198, row 22.3b, a single PR from origin/main before 22.7. server/body_size_middleware.py checks only Content-Length, so a chunked request skips the cap, and its 256 KiB ceiling is below the SNS protocol cap. It becomes plain ASGI middleware that counts the bytes it actually receives. Its ceiling is a [server] setting at least as large as the largest protocol cap. The legacy pins read the cap from settings. The WAF excludes /hook/ from the managed rule set and sets no body limit there, so the app is the control and the edge is optional defence in depth. W3 still caps each protocol on the stream.
D20 The SNS certificate fetch and subscription confirmation get an httpx client factory in app/integrations/aws_sns/client.py, following the opsgenie, openai and canada_holidays factories: a per-attempt timeout, AsyncHTTPTransport(retries=N) for connect-only retries, and follow_redirects=False. It ships in this dark PR: it is only a factory, with no terraform and nothing that runs in production.
D18 Lane A hand-off (a): add an AC to TASK-37.6.2: "the incident's interim AlertAcknowledgements adapter (TODO(TASK-37.6.2)) and its acknowledged_count increments are deleted; the stored attribute is no longer written". Its TODO already names TASK-37.6.2 (migration.md rule 7), and webhooks.md lists it as tolerated until 37.6.2. Old items keep the attribute; data is never deleted.

FILES (production)
- capabilities/webhooks/entrypoints/http.py (router, not included), http_aws_sns.py, http_legacy_slack_json.py, jobs.py
- capabilities/webhooks/adapters/aws_sns.py (certificate fetch and cache, subscription confirmation); adapters/slack.py (PassthroughMessage)
- capabilities/webhooks/domain/strict_json.py, domain/inbox.py (item states, transitions, backoff: pure), domain/kinds.py (state, topic_arns), domain/messages.py (PassthroughMessage)
- capabilities/webhooks/schemas.py (SNS envelopes as a discriminated union on Type; the legacy envelope)
- capabilities/webhooks/interfaces.py (SnsCertificates, SubscriptionConfirmer, InboxStore, WebhookStore Protocols)
- capabilities/webhooks/store.py (RecordWebhookStore, RecordInboxStore; async, one asyncio.to_thread per call)
- capabilities/webhooks/service.py (the processor), providers.py (sns adapter, stores), settings.py plus config base/ci/local/production
- app/integrations/aws_sns/client.py and its settings slice (D20)
- app/pyproject.toml (cryptography direct at the locked version; contract (p) adds capabilities.webhooks.store)
- decisions/webhooks.md, reliability.md, security.md (Changes lines for D1, D5, D9, D11)

STEPS (TDD; failing tests first, each file named test_webhooks_<entity>_<action>.py)
1. Strict JSON and SNS envelopes: tests for each RFC 7493 refusal and the discriminated union (AC #2, #11).
2. SNS verifier: v1 and v2 sign and verify with a generated key and certificate; bad signature, unknown version, cert URL off-host and stale Timestamp give 403; the cert fetch is async, cached and never follows redirects (respx or a fake transport) (AC #1, #3). End the TASK-36.2 `test_legacy_only_webhook_sns_signature_version_2_is_rejected_with_500` row: it stays a legacy pin (the legacy route still rejects v2), and its docstring gains the new path's accepting counterpart. Confirm at implementation how the pin convention records "ended".
3. Legacy decoder: Idempotency-Key, fingerprint, channel ignored (AC #8).
4. WebhookStore and InboxStore on the in-memory RecordStore fake: insert new or duplicate, 503 on an error, guarded transitions, a stale token gets False, sparse due index membership (AC #4, #5).
5. Processor: single dispatch on a redelivery, per-target progress, retry_after to retry_at, fallback to render_failed, subscription confirmation host rule, cap to dead with webhook_dead_lettered (AC #4, #5, #7, new #12).
6. Router through a test app: the responses table, 200 on downstream failure or timeout, 503 only on a store error, 413, 415, 405, 404 (AC #6).
7. Sweeper job: lease taken, async clients built inside the run, expired-lease takeover, backoff (AC #7).
8. Settings in the configuration files; make check-settings-key-ownership, check-import-contracts, check-package-shape, check-test-seams (AC #9, #10).
9. ADR Changes lines, task notes and ACs one by one; full mypy then pytest under the lock.

AC EDITS (backlog CLI, after approval)
- #9 becomes: body caps, Content-Types, JSON depth, inline deadline, lease margin, inbox table and TTL, retry, sweeper and SNS fetch values are typed [webhooks] settings with defaults; make check-settings-key-ownership is green (test + check).
- #10 adds: no job is registered and no router is included.
- New #12: an item records each finished post, consume and handler, and a retry repeats none of them (test).
- The description drops the KMS helper and the rate-limit settings (D6, D7) and names the inbox table row (D3).
- Elsewhere: TASK-37.2.4 (D3), TASK-197 with 197.1 and 197.2 (D6) and TASK-198 (D19) created; TASK-47 and TASK-37.8 depend on TASK-197.2; TASK-49 note (D7); TASK-37.4.3 gains the sweeper registration AC (D16); TASK-37.6.2 gains the D18 AC; TASK-37.2 gets the D1 pointer comment.

Production: dark. Revert: one git revert. Change notice: none (dark layer; row 22.3a is also dark, an empty table).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-11-26 (TASK-37.2.3, human-approved): the processor resolves each destination's languages through LanguagePolicy before rendering, posts through the ChannelPoster for the destination's WorkplaceSystem (a destination with no poster, or slack.passthrough to a non-Slack destination, is skipped and reported), gathers consumer actions only where the destination sets triage, and sets the item's retry_at from a 429's retry_after (the inbox is the one retry point; posts are never retried in process).

2026-11-27: plan approved by the human (Q1-Q6). The KMS helper moved to TASK-197 and the rate-limit settings to TASK-49; the inbox table is TASK-37.2.4 (row 22.3a) and the server body cap TASK-198 (row 22.3b).
<!-- SECTION:NOTES:END -->

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

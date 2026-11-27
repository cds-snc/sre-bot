---
status: Accepted
date: 2026-11-25
applies: target
scope: The inbound webhooks capability: placement, the protocol, sender-kind and instance layers, the async ingest pipeline and its inbox, the canonical event model, responses, the data and control planes, caller classes, observability and the caller migration.
---

# Webhooks

## Context

`POST /hook/{webhook_id}` is the organisation's single inbound-webhook ingress ([security.md](security.md)), mounted bare and under `/api/v1/hook`; production traffic is almost all on the bare mount (TASK-46). Today the route (`api/v1/routes/webhooks.py`) is a sync handler that:
- **guesses the payload type** by counting fields shared with four Pydantic models (`select_best_model`), then switches on the class name; a second, divergent guesser (`validate_string_payload_type`) is dead code;
- **finds sender handlers by walking the filesystem at import time** (`os.listdir` and `importlib.import_module` over `patterns/`, failures caught and skipped), with ties broken by directory order, which differs per machine. Eleven per-sender modules (about 1,300 LOC) hold an `is_*` predicate, a priority and a Slack Block Kit builder each; one (`api_key_detected`) also revokes a Notify key, and its four `(\w.+)` groups backtrack on authenticated SNS text;
- **is Slack all the way through**: the pipeline's output type is Block Kit, built with a `WebClient`, and a Slack failure returns 500 so the sender retries;
- **keeps business logic in the route**: email-to-mention mapping (one `users_lookupByEmail` per address, unbounded), IP hydration, incident buttons keyed on the `hook_type == "alert"` magic string, a read-modify-write invocation counter, and the full record plus payload sent to Sentinel;
- **has no idempotency**: a redelivered SNS message posts twice;
- **forwards sender-built Slack fields** (`blocks`, `attachments`, `username`, `icon_*`, `thread_ts`, `parse`, `link_names`), so a sender can post a button carrying the bot's own `callback_id`, and payload text reaches mrkdwn unescaped (`<!channel>`, `<@U…>`);
- **uses the URL token as identity and credential at once**: the `webhook_id` is the only credential of generic senders, yet it is the log field, the rate-limit key and the value of the incident "ignore" button, stored in every alert message;
- answers a bad SNS signature with 500, verifies SignatureVersion 1 only, confirms an SNS subscription with a 60 s `requests.get` on an unchecked `SubscribeURL` host, and rate-limits per source address, which all SNS traffic shares;
- is managed only from Slack (`/sre webhooks`: list, create, toggle, reveal), with no permission check and unversioned, unaudited writes.

The record was reassessed (TASK-168) after the organisation-content decision (TASK-167) made sender mappings provisioned content and instances managed content ([organisation-content.md](organisation-content.md)). Two inputs from TASK-36.2 shaped it: the pins hold the external contract, and SNS SignatureVersion 2 is pinned `legacy_only`. TASK-190 added the linear-processing rule for untrusted text ([security.md](security.md) Request limits). Two corrections to earlier reasoning: SNS retries only 5xx and 429, so any other 4xx discards the notification when the subscription has no dead-letter queue ([SNS delivery retries](https://docs.aws.amazon.com/sns/latest/dg/sns-message-delivery-retries.html)); and a 256 KiB SNS message, JSON-escaped inside the signed HTTP envelope, can exceed today's 262,144-byte body cap, while SNS's 1 MiB limit applies to SQS, Firehose and Lambda subscriptions only ([SNS large payloads](https://docs.aws.amazon.com/sns/latest/dg/large-message-payloads.html)).

## Decision

### 1. Placement

Inbound webhooks is a **capability** at `app/capabilities/webhooks/` ([plugin-architecture.md](plugin-architecture.md), [product-scope.md](product-scope.md)): a domain-agnostic engine other features consume, as Svix Ingest, Hookdeck, incident.io and PagerDuty model a *source → route and transform → destination* engine ([Svix Ingest](https://docs.svix.com/ingest), [incident.io HTTP sources](https://docs.incident.io/alerts/custom-http-sources)). HTTP is not a platform transport ([platform-transports.md](platform-transports.md)); the ingress route is the capability's own `entrypoints/http.py`, registered through `register_routes`. Posting to a channel is messaging outside a request, so it goes through a channel-poster port with one adapter per platform. Domain types are ingress-neutral (`InboundEvent`, `Source`, `Delivery`): an HTTP webhook is the first ingress adapter. SNS to SQS for topics the organisation owns is a recorded option with no slice; it is revisited when an owned topic needs more than 256 KiB or the public endpoint is to be closed.

```text
app/capabilities/webhooks/
├── plugin.py          # hookimpls: register_content_kinds, register_routes, register_slack_commands, jobs
├── api.py             # public surface: Protocols, domain types, provider function
├── hookspecs.py       # the extension point: event consumers by event type, handlers by id
├── domain/            # pure: events, sender kinds and instances, matching, extraction, rendering, interpret, the email finder, value hygiene
├── schemas.py         # Pydantic at the trust boundary: the sender-kind file model, the protocol envelopes
├── interfaces.py      # the Protocols service.py depends on (the SNS certificate and confirmation port)
├── service.py         # ingest and processing; WebhookAdmin, the control plane's one writer
├── store.py           # WebhookStore and the inbox store, through the records and coordination contracts
├── settings.py        # the [webhooks] slice: limits, deadlines, TTLs, retry policy
├── entrypoints/
│   ├── http.py        # POST /hook/{webhook_id}; /api/v1/webhooks (control plane)
│   ├── http_<protocol>.py  # one per wire protocol: verify, delivery id, decode
│   └── slack.py       # /sre webhooks, a binding over WebhookAdmin
└── adapters/
    ├── slack.py       # the channel poster on AsyncWebClient, with escaping
    └── aws_sns.py     # the SNS certificate fetch and subscription confirmation
```

Every name is in [feature-packages.md](feature-packages.md)'s layout table (`domain.py` grown into `domain/`); a wire protocol is a driving adapter at the HTTP edge, verified on the raw body before any handler, as Stripe, Svix and GitHub verify at the endpoint ([Stripe](https://docs.stripe.com/webhooks), [Svix](https://docs.svix.com/receiving/verifying-payloads/how), [GitHub](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)).

There is no `router.py` string table and no `importlib`. Features attach through the capability's hookspecs, collected once at startup ([plugins.md](plugins.md)).

### 2. Three layers, no guessing

| Layer | What it is | Source |
| --- | --- | --- |
| **Protocol** | How a delivery is verified and decoded: `aws_sns`, `standard_webhooks`, `github`, `legacy_slack_json`, and a native protocol whose body is the `InboundEvent` schema. Each verifies authenticity, gives the delivery id and decodes into one typed envelope; variants inside a protocol (SNS `Type`) are a discriminated union | code, a closed set registered at startup |
| **Sender kind** | Which event this is and how to word it: a declarative `match`, an `extract` map, a template per text field, optionally `handler: <registered id>` and `suppress: true` | provisioned content |
| **Instance** | One endpoint: its `protocol`, an **ordered list of sender kinds**, its destinations, owner and tier | managed content |

The instance declares its protocol, so a body that fails that protocol's decode answers 400 and nothing tries another model. Kinds are tried in the order the instance lists them and the first match wins (declarative routing, as PagerDuty Event Orchestration and Grafana IRM routes do: [Event Orchestration](https://support.pagerduty.com/docs/event-orchestration), [Grafana routing templates](https://grafana.com/docs/grafana-cloud/alerting-and-irm/irm/configure/escalation-routing/alert-templates/)); no match falls to the instance's fallback rendering and emits `webhook_unmatched`. Svix declares a type per source the same way ([Svix Ingest](https://docs.svix.com/ingest)). Matching (route) and rendering are separate stages, so a match never renders nothing by accident; a kind that should post nothing says `suppress: true`.

Pydantic models type the **protocol envelope** at the trust boundary, the only place Pydantic is used. Sender kinds work on the decoded JSON through declared extraction, and the kind's field schema validates the result; there is no Pydantic model per sender.

Senders the organisation owns that publish custom text (confirmed per kind before TASK-37.4.1) are adapters to ourselves: they move to an authenticated API (decision 5b) or the native protocol (TASK-48), and their kinds retire. Mapping content is for third-party shapes (CloudWatch, Budgets, Upptime, GitHub).

### 3. Pipeline (data plane)

The route is `async def`. Durability is the baseline, not an option: verify, persist, acknowledge, then process, as the [OWASP Webhook Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Webhook_Security_Cheat_Sheet.html) ("return `200` only after the event is durably queued or processed"), Svix ([webhook consumer](https://www.svix.com/resources/glossary/webhook-consumer/)) and Hookdeck ([asynchronous processing](https://hookdeck.com/webhooks/guides/why-implement-asynchronous-processing-webhooks)) recommend.

1. **Verify.** Body cap per protocol (SNS about twice its 256 KiB message limit); authenticity per protocol against the raw body before parsing ([security.md](security.md) Webhooks); the two-layer rate limit. An SNS certificate fetch goes through async httpx from an SNS host only, cached.
2. **Decode** with the instance's protocol; a failure answers 400. JSON is parsed strictly, as [RFC 7493](https://www.rfc-editor.org/rfc/rfc7493) I-JSON requires: a duplicate member name, `NaN` or `Infinity`, a lone surrogate, a non-finite number or nesting past a depth limit is refused, since parsers disagree on them and the standard library keeps the last duplicate silently ([JSON interoperability](https://bishopfox.com/blog/json-interoperability-vulnerabilities)).
3. **Persist** the decoded envelope as an **inbox item** through an atomic conditional insert keyed `webhooks:<instance_ref>:<delivery id>`. That insert is the delivery idempotency ([reliability.md](reliability.md)): an existing key answers 200 with no work. It is called through an async adapter that offloads the sync store with `asyncio.to_thread` inside the adapter ([outbound-clients.md](outbound-clients.md)) until TASK-25 gives async ports.
4. **Acknowledge** with 200.
5. **Process** inline, inside `asyncio.timeout([webhooks] inline_processing_deadline_seconds)` (default 5 s, below GitHub's 10 s and SNS's about 15 s): match → extract → `InboundEvent` → consumers by event type (the channel poster, alert consumers, registered handlers). No fire-and-forget task ([transport-slack.md](transport-slack.md)): a draining replica finishes or abandons the attempt, and the item stays durable. The answer is 200 whether processing finished, failed or timed out.
6. **Retry, dead-letter and replay are ours**, not the sender's. Item states: `received → processing (lease until) → done | retry (retry_at) | render_failed | dead`. Every transition is a conditional write carrying the claim's ownership token, so the inline attempt and the sweeper never both process an item. A **sweeper** job, Tier-2 under a lease ([lifecycle.md](lifecycle.md), [reliability.md](reliability.md)), retries `retry` items with backoff, moves an item past the retry cap to `dead` with `webhook_dead_lettered`, and opens one `asyncio.Runner` per run, building its async clients inside that run. Replay of `dead` and `render_failed` items is an authenticated, audited control-plane action. Items carry a TTL (default 7 days), hold the decoded envelope and never raw headers. An SNS `SubscriptionConfirmation` is an inbox item too: the processor confirms it, so the request path makes no outbound call.
7. **v2** (TASK-37.7): once `QueueService` lands (TASK-34), step 5 becomes an enqueue and the sweeper becomes the queue consumer and its DLQ; the inbox item stays the delivery log. Whether the inbox is the "durable cross-process reaction" that triggers building TASK-34 now is open ([reliability.md](reliability.md)); v1 ships inline plus sweeper.

**Delivery idempotency is not alert dedup.** The delivery id dedupes the transport. An `alert` event's `dedup_key` groups distinct deliveries describing one condition, as incident.io resolves an alert from a resolved event with the same key ([deduplication](https://docs.incident.io/alerts/deduplication)). Neither is ever a payload hash ([reliability.md](reliability.md)).

**The linear-processing rule binds the interpret and render stages** ([security.md](security.md) Request limits, TASK-190): extraction uses RFC 9535 **singular queries only** (name and index segments, no filters); content holds **no regular expression**; each protocol decoder is linear in the body size; each stage has an adversarial test at the body cap; and the email-to-mention matcher is linear and token-bounded, with a cap on Slack lookups per message, cached per delivery (today one `users_lookupByEmail` per match, unbounded). Text that needs parsing is a protocol decoder or a registered handler in code, where the rule's pattern discipline applies. Parsing, matching and rendering stay on the event loop: they are bounded by the cap and this rule, and `to_thread` would not help CPU work that holds the GIL.

| Call | Target |
| --- | --- |
| DynamoDB (inbox, `WebhookStore`, claims) | `asyncio.to_thread` inside the async adapter until TASK-25 |
| SNS signature verification | an async certificate fetch from an SNS host, cached, or the validator offloaded in the adapter; whether `aws-sns-message-validator` fetches synchronously is checked at TASK-37.2.2 |
| SNS subscription confirmation | from the inbox item, async httpx, host rule, no redirects, a timeout setting |
| Slack post and email lookups | `AsyncWebClient` |
| Notify key revocation | async httpx in the registered handler, run from the inbox item |

### 4. Content rules

Sender kinds follow [organisation-content.md](organisation-content.md) and [provisioned-content.md](provisioned-content.md); instances follow [managed-content.md](managed-content.md).
- **Files.** One kind per file at `<content root>/webhooks/sender-kinds/[<folder>/...]<id>.yaml`, self-describing (`kind: webhooks/sender-kinds`, integer `version`); examples under `app/content/examples/webhooks/sender-kinds/` (example.com). The schema is generated into `app/content/schemas/webhooks/sender-kinds.json`.
- **Engines.** Matching is a declarative condition list: a path plus an operator from a closed set (`equals`, `in`, `exists`, `starts_with`, `contains`), combined with `all` and `any` to depth 2, PagerDuty's condition model; CEL is the upgrade path if conditions outgrow it. Extraction is [RFC 9535](https://datatracker.ietf.org/doc/html/rfc9535) JSONPath, singular queries only, in strict mode (python-jsonpath). Templates are [python-liquid](https://github.com/jg-rp/liquid) 3 with `StrictUndefined`, no loader and `ResourceLimits` set from `[webhooks]` (`max_loop_iterations`, `max_render_size`, `max_context_depth`; 3.x has no local-namespace limit, and `assign` is removed, so none is needed). Only plain-text tags are kept: `include`, `render`, `assign`, `capture`, `increment`, `decrement`, `cycle`, `ifchanged`, `liquid` and `tablerow` fail at parse. Filters are an allowlist of string, number, list and date filters; filters that decode (`base64_decode`, `url_decode`), mark up (`escape`, `safe`, `newline_to_br`) or run a regular expression over a value (`strip_html`) are absent, and an unknown filter fails at boot. Names are checked at boot through static analysis (`global_variable_segments`). Templates parse at boot only, never per request.
- **Fixed data model.** A template sees only `fields.<name>` (the kind's extracted values, `str | int | float | bool | list[scalar]`, each length-capped and each list capped in elements), `instance.name` and `received_at`; never the raw payload or a Python object, and payload values are data, never template text. It produces only the event type's text fields as **plain text, never mrkdwn**. The code-owned Slack adapter builds Block Kit and escapes every value (decision 9); content never builds platform JSON.
- **Wording per language.** The bot's wording (title, summary, link labels) holds one template per supported language, required by the kind's model and its JSON Schema ([languages.md](languages.md)), and renders in the destination's shared languages in policy order. The sender's own text is one `details` template, in its source language, shown once.
- **Extracted text is neutralised** before any template or adapter sees it: NFC-normalised, with control characters other than newline and tab, bidirectional controls and invisible format characters removed ([Trojan Source](https://trojansource.codes/), CVE-2021-42574; [UTS #39](https://www.unicode.org/reports/tr39/)). This is not output encoding, which the adapter still applies ([OWASP Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)).
- **Links.** A `url` field is parsed and refused when ambiguous: a scheme other than `https`, userinfo, no host, spaces or control characters, or over `max_url_chars`. Its host is kept in punycode and the URL is rebuilt with every character outside the URL's safe set percent-encoded, so no Slack link delimiter (`|`, `<`, `>`) survives; a kind may list `allowed_hosts` per field ([OWASP Unvalidated Redirects and Forwards](https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html)). A link's label is fixed wording and names no payload field: a payload label over a payload URL is a phishing lure.
- **Limits are `[webhooks]` settings with defaults** (TASK-37.2.1): file 16 KiB; conditions 50, depth 2; extracted fields 30, each value 4 KiB, lists 50 elements; link URLs 2,048 characters; template 2 KiB; render output 3,000 characters; rendered title 150 characters; loops 100 iterations; context depth 10; kinds 200; kinds per instance 20; email lookups 10 per message. The content validator checks files against the defaults, as it does the `[content]` ceilings ([provisioned-content.md](provisioned-content.md)). Slack's 3,000 characters per section and 50 blocks are Slack API facts, constants in the Slack adapter.
- **Names are checked at boot**: a template naming a field the kind does not extract, a `handler:` no plugin registered, or over-limit content fails boot naming the file.
- **A stored instance naming an unknown kind** is skipped and reported, never a boot failure ([managed-content.md](managed-content.md): readers treat stored content as untrusted).
- **Runtime failure is fail-soft.** A render error, or an extraction miss on a required field, posts the instance's fallback rendering (escaped, truncated text of the decoded message), emits `webhook_render_failed` with the kind id and field, leaves the item `render_failed` for replay after a content fix, and answers 200. incident.io creates a default alert on a transform error the same way ([HTTP sources](https://docs.incident.io/alerts/custom-http-sources)). A 4xx would make SNS discard the notification.

### 5. Responses

| Status | When |
| --- | --- |
| 200 | once the item is persisted, including a duplicate, an unmatched delivery, a render failure, a processing timeout or a downstream (Slack) failure, which we retry |
| 400 | the body fails the instance's protocol decode (SNS does not retry a 4xx) |
| 403 | a bad webhook signature, with a generic body that never says why |
| 404 | an unknown or inactive instance |
| 405 | any method other than POST |
| 413 | over the protocol's body cap |
| 415 | an unexpected `Content-Type` |
| 429 | a rate limit, with `Retry-After` |
| 503 | only when the inbox store is unavailable, so nothing was persisted, with `Retry-After` |

The answer comes within the inline deadline. **Behaviour change at TASK-37.4.3:** a Slack failure no longer returns 500 or 503; the TASK-36.2 pins that assert it are updated there with that reason ([migration.md](migration.md) named change, kind b).

### 5a. Canonical model

Anything can be a webhook payload, so the canonical model is a neutral **event** and an alert is one event type. `InboundEvent` is a frozen dataclass using the [CloudEvents 1.0](https://github.com/cloudevents/spec) context attribute names:
- `id`: the protocol's delivery id, or a server-generated `local:<uuid>` when the protocol has none;
- `source`: the instance's `instance_ref`, never the URL token;
- `type`: set by the **matched sender kind**, never read from the payload;
- `time`: received time; a sender-supplied time is an attribute only after verification;
- `subject`: optional;
- `data`: only the kind's validated, extracted fields, typed and capped.

The raw payload never leaves the interpret stage, except as the inbox item's decoded envelope. Event types are closed per deployment and registered at startup:
- `alert`: title, summary, status (`firing | resolved | info`), severity, `dedup_key`, links. `dedup_key` and `status` are carried but unused in v1, so the cutover keeps parity; they allow update-on-resolve and alert-to-incident ([incident-management.md](incident-management.md)) without breaking content;
- `notification`: title, summary and links, no triage; it replaces `hook_type: info`;
- `slack.passthrough`: the `legacy_slack_json` protocol, opaque, Slack-only and hardened (decision 9);
- types a feature registers (TASK-147.5's GitHub types).

The payload never chooses its type, routing, channel or action: "a valid signature proves who sent the payload, not that its contents are safe" (OWASP cheat sheet), and `data` is validated against the kind's strict schema before anything downstream sees it ([OWASP API10:2023](https://owasp.org/API-Security/editions/2023/en/0xaa-unsafe-consumption-of-apis/)).

**Extension point.** The webhooks hookspec (TASK-37.2.1) lets features register, once at startup:
- **event consumers by event type**: the channel poster is the default consumer for `alert` and `notification`; the incident feature registers an **alert consumer** that contributes triage actions ("call incident", "ignore") to the poster's render and receives the typed event (title, attributes, `instance_ref`, inbox item id). This replaces the `hook_type == "alert"` string and the alert text pasted into a button value; from TASK-37.4.3 the button carries `instance_ref` and the inbox item id, coordinated with the incident feature;
- **handlers by id**: a kind's `handler:` names one; it runs from the inbox item, keyed on the delivery id, so a redelivery cannot act twice. The Notify key revocation becomes such a handler with a linear pattern, in a small package that owns the Notify integration (named at TASK-37.3), never in content or the capability core.

The instance declares its destinations: each a workplace reference (system, tenant and conversation id, never a bare channel id: [workplace-systems.md](workplace-systems.md) rule 4), and whether triage consumers apply. There is no in-process event bus ([plugin-architecture.md](plugin-architecture.md)). No Opsgenie inbound source is built: Opsgenie's end of support is 2027-04-05.

### 5b. Two planes and three caller classes

- **Data plane**: ingress, inbox and processing; no admin operation.
- **Control plane**: `WebhookAdmin`, the only writer of instances, which is the webhook-instance kind's one write path ([managed-content.md](managed-content.md)). It is API first (TASK-37.6.1): `/api/v1/webhooks`, authenticated with `get_current_user` and the `webhooks:admin` permission, deny by default, optionally scoped per team ([authorization.md](authorization.md)). Operations: list, get, create, update (channel, kinds, destinations, owner), disable and enable, rotate the secret, set `auth_tier`, list deliveries (the last N inbox items: time, kind, outcome, attempts, never the payload) and replay. Every write is an AU-3 audit event; reveal is audited for the legacy tier and removed for signed tiers, whose secret is shown once. `/sre webhooks` becomes one Slack binding over the same service (TASK-37.6.2), as Backstage can be another.
- **Instance model**: `active | disabled`, `auth_tier` (`legacy | monitor | enforce`), `protocol`, `sender_kinds`, destinations, a required `owner` (team and contact), `sunset_at`, `expires_at`, `instance_ref`, and for SNS an optional `topic_arns`. `hook_type` is retired into the kinds' event types and the destinations. Instances stay in the `webhooks` table behind a `WebhookStore` port; the new attributes are optional (an expand step legacy code ignores). Versions, export without secrets and the kill switch arrive with TASK-37.8, on the first managed kind's version store; until then writes are conditional updates plus audit events.

| Class | Front door | Authenticity | Shape |
| --- | --- | --- | --- |
| 1. First-party workloads with an identity (GitHub Actions, Logic Apps and Sentinel playbooks, Backstage, the organisation's services) | the owning feature's API under `/api/v1/` | a workload JWT validated through JWKS and mapped to a principal ([security.md](security.md), TASK-194); 401 or 403 | typed request and response; the response returns ids so the caller can update or resolve later |
| 2. Third parties and AWS services that can only sign | `/hook/{webhook_id}` | provider signature (SNS, GitHub) or Standard Webhooks HMAC | mapped by sender-kind content into an `InboundEvent` |
| 3. Legacy | `/hook/{webhook_id}` | the secret URL | burned down (TASK-48) |

First-party callers do not need this capability: the webhook ingress is the adapter for senders that cannot change their shape or hold an identity. **Both front doors converge on one application service**: for example, the incident feature's alert-intake endpoint and its webhook alert consumer call the same service. That endpoint and its slice belong to the incident re-cut, not to webhooks. Where an event triggers an action on a system the bot can read, the consumer fetches current state rather than trusting payload fields (TASK-147.5 through the GitHub App; [Stripe thin events](https://docs.stripe.com/webhooks/migrate-snapshot-to-thin-events)). AWS callers stay on SNS; a direct-call identity for AWS workloads is not decided.

### 6. Authenticity

Governed by [security.md](security.md) Webhooks: SNS SignatureVersion 1 and 2, 403 on a bad signature, the per-instance TopicArn allowlist, the `SubscribeURL` host rule, Standard Webhooks v1 as the HMAC tier (TASK-47), secrets encrypted at the application level and never exported, and rotation. The GitHub protocol (`X-Hub-Signature-256`) is built inside TASK-147.5, its first consumer. Which Standard Webhooks library is used (`standardwebhooks` 1.3.0 wrapped in the protocol adapter, or our own) is decided at TASK-47.

### 7. URLs

The bare `/hook/{webhook_id}` is a **durable contract**: its URLs never change across the migration. It is a durable public address for signed tiers and a revocable secret for the legacy tier, so rotating a legacy credential means a new URL. Whether `/api/v1/hook` is kept or dropped is decided by TASK-37.4.3 after the production access-log check ([migration.md](migration.md)).

### 8. Observability

- Events carry `instance_ref`, the kind id, the protocol and the outcome. No full record and no payload reach Sentinel; `webhook_sent` sends ids, kind and outcome, after a check that no SIEM rule reads the payload fields.
- **Counters are metrics, not read-modify-write.** Invocation and acknowledgement counts are metrics; the stored `invocation_count` and `acknowledged_count` are not updated by the pipeline. **`acknowledged_count` is approximate.** The incident feature's interim adapter that increments it (`AlertAcknowledgements`, TASK-145.7.10) is tolerated until TASK-37.6.2 replaces the legacy admin surface that displays it.
- Never logged: the URL token, `Authorization` and signature headers, request bodies.
- Alerts on signature-failure spikes, unknown-id sprays, sustained 4xx or 5xx, and dead-lettered items.
- Events named here: `webhook_unmatched`, `webhook_render_failed`, `webhook_dead_lettered`, `webhook_shadow_result`.

### 9. Security additions

Recorded in [security.md](security.md) Webhooks and applied here:
- **`instance_ref`**: an internal, non-secret random id on every instance. Logs, metrics, rate-limit keys, flag contexts, idempotency keys and Slack button values use it; the URL `webhook_id` appears only in the route lookup.
- **Secrets at rest**: application-level KMS encryption of the secret attribute with encryption context `{instance_ref}`, decrypted on verify and cached within a TTL setting; export never includes secrets, import mints new ones. The AWS Database Encryption SDK or direct KMS is chosen at TASK-47.
- **Output encoding**: the Slack adapter escapes every content-derived value (`&`, `<`, `>`) before inserting trusted tokens (matcher mentions, adapter-built links), sets `verbatim: true` on `mrkdwn` text carrying payload values so Slack does not auto-link them, uses `plain_text` where no trusted token is needed, and truncates after escaping; link URLs are not escaped but re-encoded at extraction (decision 4); every kind's fixture proves `<!channel>`, `<@U123>` and `<https://x|y>` render inert ([Slack formatting](https://docs.slack.dev/messaging/formatting-message-text), [text objects](https://docs.slack.dev/reference/block-kit/composition-objects/text-object)). Every Slack call has a timeout and a bounded retry ([OWASP API10:2023](https://owasp.org/API-Security/editions/2023/en/0xaa-unsafe-consumption-of-apis/)).
- **Passthrough hardening** for `slack.passthrough`, monitored by TASK-37.4.2 and enforced by TASK-37.5: drop `callback_id`, `action_id` and `block_id` values any feature registered; drop interactive elements without a `url`; drop `parse` and `link_names`; drop `username`, `icon_*`, `thread_ts` and `reply_broadcast` unless the instance allows them; add a "via webhook <instance name>" context line.
- **Two-layer rate limit** (TASK-49): before lookup, a per-address limit counting only unknown or inactive ids and failed verifications, with a short negative cache for unknown ids; after lookup, the per-instance limit with an override.
- **OWASP alignment**: POST only; an unexpected `Content-Type` refused; generic error bodies; verify the raw body before parsing; a signed timestamp with tolerance plus event-id dedup.
- **Instance hygiene**: a required `owner`; auto-disable after an inactivity window setting, with notice to the owner first; an optional `expires_at`; the channel changed only through the control plane.
- **SNS subscription hygiene** for topics the organisation owns (terraform outside this repository): a subscription dead-letter queue and a longer HTTP/S delivery policy, prefer SignatureVersion 2. Recommended here and in the TASK-48 owner guide.

### 10. Caller migration

The cutover is invisible to callers; the end state changes what callers do, so it runs as a programme with dates (TASK-48).

**Cutover per instance (no caller action, done by TASK-37.5):** expand, migrate, contract. TASK-37.4.1 backfills each instance's `instance_ref`, `protocol`, `sender_kinds` (SNS instances get today's ten kinds in today's priority order), destinations from `hook_type`, `topic_arns` and `owner` from the TASK-46 evidence. A per-instance OpenFeature flag, default `legacy`, has three states: `legacy | shadow | pipeline`. In `shadow` (TASK-37.4.2) legacy stays primary and the pipeline verifies, decodes, matches and renders without dispatching, emitting `webhook_shadow_result` (`instance_ref`, the kind each path matched, a structural digest of both renders, never the text) and the passthrough fingerprints; this is the parallel-run pattern ([GitHub Scientist](https://github.com/github/scientist)). An instance moves to `pipeline` (TASK-37.4.3) after N matching deliveries or reviewed differences, N set per instance by a human; an instance that receives more than one protocol stays `legacy` until it is split. Canary one instance, then all; TASK-37.5 deletes the legacy path after the soak.

**End state per caller class:**

| Caller | Today | End state |
| --- | --- | --- |
| GitHub Actions workflows | secret URL, Slack JSON or text | preferred: the owning feature's API with a GitHub OIDC token ([GitHub OIDC](https://docs.github.com/en/actions/reference/security/oidc)); fallback: Standard Webhooks HMAC |
| Azure Sentinel and Logic Apps playbooks | secret URL (from logs) | preferred: the API with a managed-identity token; fallback: HMAC if the playbook can compute it, checked per playbook at TASK-48 |
| AWS SNS topics | SNS signature | unchanged URL and protocol; owned topics adopt the subscription hygiene above, owned custom publishers move to the native protocol or the API |
| Scripts and SaaS posting Slack-shaped JSON | secret URL | Standard Webhooks HMAC, or the API if the caller can hold an identity; no interactive or impersonation fields |
| Unknown | secret URL | found by the inventory, then one of the above |

**Phases with callers (TASK-48):**
1. Inventory and owners: every instance gets an owner, backfilled from its creator and channel; the TASK-46 fingerprints classify it; unknown instances get a notice in their channel.
2. Announce: one announcement with the end state and a dated timeline, a guide per caller class, and a direct message to each owner listing their instances.
3. Opt-in window: the new methods are live; legacy-tier responses carry `Deprecation` ([RFC 9745](https://www.rfc-editor.org/rfc/rfc9745)), `Sunset` ([RFC 8594](https://www.rfc-editor.org/rfc/rfc8594)), no earlier than the deprecation date, and `Link: <guide>; rel="deprecation"`, and the bot posts a rate-limited notice in the instance's channel; SRE gets a weekly compliance report by owner.
4. Brownouts: short, announced enforcement windows before the sunset date.
5. Enforce per instance (`auth_tier` monitor then enforce); exceptions are written, time-boxed and owned.
6. Remove the legacy tier; this ends the no-dedupe exception.

The sunset date, where the guides live, and the communication artifacts are set at TASK-48 planning. Legacy senders that cannot move yet may send an optional `Idempotency-Key` header ([IETF draft](https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/)), opt-in, so nothing changes for others; its draft status is checked at TASK-48.

## Rejected

- **A managed gateway** (Svix Ingest, Hookdeck): the bot runs standalone, it adds a SaaS dependency, and mapping is still needed.
- **CloudEvents as the wire contract**: no alert source sends it; only its attribute names are borrowed for `InboundEvent`.
- **RFC 9421 HTTP Message Signatures** and Standard Webhooks `v2a` (ed25519): no webhook provider found using RFC 9421; neither is adopted now.
- **Jinja2** (`ImmutableSandboxedEnvironment`): no built-in resource limits, a Python attribute model inside templates, and three sandbox CVEs in 2024-25 (CVE-2025-27516). **Mustache**: a missing key renders empty, which breaks the undefined-name rule. `string.Template` is too weak (no filters or conditionals). PEP 750 t-strings are source literals: used for code-owned renderers (the Slack adapter, the fallback), never for content.
- **JMESPath** (more logic than needed, not a standard), **JSON Logic** (unmaintained Python ports), **JSON Schema as a matcher** (no readable priority, slow per kind), **regex conditions** (security.md Request limits).
- **Payload-hash dedupe** ([reliability.md](reliability.md)).
- **Processing in the request with the sender as the retry queue**: SNS gives up after about a minute and GitHub never retries.
- **An Opsgenie inbound source** (end of support 2027-04-05).

## Consequences

- No payload guessing at any layer; an instance's kinds and their order are declared, so routing is deterministic.
- A new sender shape is a content pull request, reviewed and validated like code, not a Python module.
- Delivery is acknowledged once durable; retries, dead letters and replay are ours and visible to owners.
- The URL token stops being the identity; a leaked button value or log no longer reveals a credential.
- Cost: an inbox table, a sweeper job and a second front door (feature APIs) to build; the cutover runs three flag states per instance.
- **Exception: the legacy protocol has no delivery id, so `legacy_slack_json` deliveries are not deduplicated.** This is written and time-boxed, consistent with reliability.md's ban on body hashes, and narrowed by the optional `Idempotency-Key` header; it ends when the last instance leaves the legacy tier (TASK-48).

## Checks

- No `select_best_model` / `has_parameters_in_model` / `validate_string_payload_type` payload guessing remains; each delivery decodes with exactly the instance's declared protocol.
- grep: no `os.listdir`/`walk_packages`-based handler discovery and no `importlib.import_module` of handler strings under the webhooks package; protocols, consumers and handlers register at startup and boot fails on a bad registration.
- grep and import-linter: no `slack_sdk`/`WebClient` import and no Block Kit construction in the capability core (domain, content, service, protocols); Slack shapes exist only in `adapters/slack.py`.
- No raw DynamoDB attribute shapes (`{"S": …}`/`{"BOOL": …}`) above `store.py`; the route and service speak the domain model.
- import-linter: `capabilities/webhooks` imports `integrations` only inside `adapters/`, and imports no feature.
- Boot test: a bad sender kind, a template naming an undefined field, an unknown `handler:` and over-limit content each fail boot naming the file; every consumer and handler registered through the extension point is registered before the capability initializes.
- Test: a redelivered SNS notification with the same `MessageId` posts once; a duplicate answers 200 with no work.
- Test: the responses table, including 200 on a Slack failure and 503 only when the inbox store is unavailable.
- Test: an adversarial body at the cap through decode, match, extract and render runs well under one second; the email matcher makes no more Slack lookups than its cap.
- Test: `<!channel>`, `<@U123>` and `<https://x|y>` render inert for every kind's fixture; a passthrough carrying a registered `callback_id` posts no such button once enforced.
- grep: no URL `webhook_id` in a log field, metric, button value or idempotency key outside the route lookup.
- The TASK-36.2 legacy pins pass on the new route, with the named changes above.
- Authenticity, rate-limit and body-cap checks follow [security.md](security.md) Webhooks.

## Migration

Tickets, in delivery order:
- TASK-37.1: the provisioned-content loader ([provisioned-content.md](provisioned-content.md)) and this record (dark).
- TASK-37.2.1: event model and engines: `InboundEvent`, event types, `SenderKind`, `WebhookInstance`, the matcher, extraction, renderer, the Slack poster with escaping, the event-consumer hookspec, the bounded email matcher, `[webhooks]` settings (dark).
- TASK-37.2.2: async ingest and inbox: `aws_sns` (v1 and v2, 403, TopicArn, `SubscribeURL` rule) and `legacy_slack_json` protocols, `WebhookStore`, the inbox store, the inline processor and sweeper, the route (not mounted), the KMS secret helper, rate-limit settings (dark).
- TASK-37.3: the sender kinds as content with examples and parity tests (an injection case per kind), the Notify handler, the incident alert consumer (dark).
- TASK-37.4.1: backfill of the new instance attributes (production data, inert).
- TASK-37.6.1: `WebhookAdmin` and `/api/v1/webhooks`, in parallel with the cutover.
- TASK-37.4.2: shadow; TASK-37.4.3: cutover (responses change, button value, `/api/v1/hook` decision).
- TASK-37.5: delete legacy processing; enforce passthrough hardening.
- TASK-37.6.2: the Slack binding; deletes `modules/slack/webhooks*.py` and `modules/sre/webhook_helper.py`.
- TASK-49: the two-layer rate limit. TASK-194: machine principals for inbound API callers. TASK-47: Standard Webhooks tier and native protocol. TASK-48: caller migration and burn-down.
- TASK-37.7: the inbox on `QueueService` (after TASK-34). TASK-37.8: instances onto managed content.
- The `github` protocol and handler land inside TASK-147.5.

Tolerated until each closes:
- the legacy route, payload guessers, walk registries and Slack-terminal shape (TASK-37.5);
- the `modules/slack/webhooks.py` CRUD, the unpermissioned `/sre webhooks` surface and the stored counters it displays (TASK-37.6.2);
- the incident interim `AlertAcknowledgements` adapter incrementing `acknowledged_count` (TASK-37.6.2);
- the `webhooks` table's unversioned writes (TASK-37.8);
- the plain-text import-time log lines excluded from deploy-checks' Non-JSON check (TASK-37.5);
- the risk-accepted legacy unsigned population and its no-dedupe exception (TASK-48).

**Changes:**
- 2026-09-24: Migration names epic tickets only, and the pipeline is a capability whose extension point replaces domain events; handler folder renamed `entrypoints/`.
- 2026-10-13: the storage contract is the records contract (`RecordStore`, TASK-27.4).
- 2026-10-26: under reassessment (TASK-168, after TASK-167); TASK-37's slices wait for it; the import-time, no-walk, no-guessing and idempotency invariants stand.
- 2026-11-25: rewritten (TASK-168 direction approved by the human; lands with TASK-37.1). Three layers (protocol, sender kind as provisioned content, instance as managed content); async ingest that persists to an inbox before acknowledging, with the conditional insert as delivery idempotency and a lease-guarded sweeper; the neutral `InboundEvent` model with `alert`, `notification` and `slack.passthrough` types; the linear-processing rule carried into interpret and render; a responses table (200 once persisted, 503 only when the inbox store is unavailable); data and control planes and three caller classes; `instance_ref`; counters as metrics and `acknowledged_count` approximate; the caller migration. Supersedes the per-source Pydantic model, the idempotency claim in Verify and durable enqueue "on demand".
- 2026-11-26: TASK-37.2.1 (human, after an OWASP review): the layout uses only layout-table names (`domain/`, `schemas.py`, `entrypoints/http_<protocol>.py`, `adapters/aws_sns.py`; no `content.py` or `protocols/`); bot wording is one template per supported language and sender details appear once; extracted text is neutralised (bidi, invisible and control characters); link URLs are parsed, refused when ambiguous and re-encoded rather than escaped, and link labels name no payload field; lists are capped; Liquid keeps an allowlist of tags and filters, and the python-liquid 3 limit names replace the non-existent local-namespace limit; decode parses JSON strictly (RFC 7493); the Slack adapter sets `verbatim`, prefers `plain_text` and bounds every call; Slack's section and block limits are adapter constants, not settings. Corrects the earlier rules that links needed only an `https` check and that escaping `&`, `<` and `>` sufficed for them.
- 2026-11-26: a destination is a workplace reference (system, tenant, conversation id), so posters are chosen by system and no bare channel id is stored (TASK-37.2.3 planning, human).

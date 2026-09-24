---
status: Accepted
date: 2026-07-28
applies: target
scope: The webhooks ingress capability — placement, the verify→interpret→dispatch pipeline, source-declared parsing, transport-neutral dispatch, and secure-by-default lifecycle.
---

# Webhooks

## Context

`app/modules/webhooks/` is the organization's single inbound-webhook ingress ([security.md](security.md)), built before the current corpus as an early, incomplete attempt to decouple webhook ingest from Slack. That attempt did not land, and the package accreted several structural antipatterns that no other record sanctions:

- **Probabilistic payload typing.** `POST /hook/{webhook_id}` accepts an arbitrary body and *guesses* which of several known Pydantic models it best matches by counting overlapping fields (`select_best_model` in `modules/webhooks/base.py`, and a second, divergent implementation `validate_string_payload_type`/`has_parameters_in_model` in `modules/slack/webhooks.py`). The result is ambiguous, order-sensitive, and split across two drifting implementations feeding a `match payload_type.__name__:` string switch.
- **Filesystem-walk handler registries.** `init_pattern_handlers()`/`init_notification_handlers()` `os.listdir` a `patterns/` directory, `importlib.import_module` each file, scan for `_HANDLER` attributes, and catch-and-continue on failure. Handlers are addressed by import-path strings resolved at runtime. This is exactly the implicit, non-fail-fast discovery [plugins.md](plugins.md) forbids, plus an unnecessary dynamic-execution surface.
- **Slack coupling in the "decoupled" package.** The terminal stage returns Slack Block Kit and takes a `slack_sdk.WebClient`; the output type *is* a Slack message. Webhooks are Slack-only sinks.
- **Vendor wire shapes at the edge.** The route reads raw DynamoDB item shapes (`webhook["channel"]["S"]`, `webhook.get("active", {}).get("BOOL", False)`); CRUD is hand-built low-level `dynamodb.*` calls living in a `modules/slack/` file despite being generic webhook persistence. There is no domain model.
- **Business logic in the route.** Payload guessing, invocation counting, email→Slack-mention mapping, IP hydration, incident-button decoration keyed on a `hook_type == "alert"` magic string, and the Slack `chat.postMessage` all live in the handler — violating the five-step handler discipline ([feature-packages.md](feature-packages.md)).
- **No idempotency.** SNS and most providers redeliver, but ingest has no idempotency claim ([reliability.md](reliability.md)); a redelivered notification double-posts.

The pivotal observation: the `webhook_id` in the path already scopes the sender, so the payload guessing was never necessary — the webhook *record* can declare its source. Separately, the product direction now requires webhooks to trigger behaviours never originally planned (posting to future non-Slack transports; triggering *other* business features), which the Slack-terminal design cannot express.

## Decision

### Placement

The incoming-webhook pipeline is a **capability** at **`app/capabilities/webhooks/`** ([plugin-architecture.md](plugin-architecture.md)): a domain-agnostic engine that features react to, shaped per [feature-packages.md](feature-packages.md). It is not hosting code, so it is not in `infrastructure/`. It owns an **extension point** where features register the source parsers and alert handlers they care about at startup — for example, the incident feature registers the alert actions it handles. Alert webhooks already arrive through the legacy route (`api/v1/routes/webhooks.py`, `hook_type == "alert"`), which is how that need exists today. The capability gets authenticity verification ([security.md](security.md)), coordination and the durable queue ([reliability.md](reliability.md)) and platform transports ([platform-transports.md](platform-transports.md)) through `contracts/` Protocols from the service registry.

```text
app/capabilities/webhooks/
├── __init__.py        # hookimpls: register_routes (+ register_slack for the admin surface), i18n
├── api.py             # public surface: Protocol, domain types, provider function
├── hookspecs.py       # the extension point: features register source parsers and alert handlers
├── domain.py          # frozen Webhook, WebhookSource(enum), Target/Action, InboundEnvelope, intents
├── schemas.py         # per-source Pydantic parse models (SNS, generic-json, simple-text, …) at the trust boundary
├── service.py         # the only orchestrator: ingest(), plus lifecycle CRUD (create/update/rotate/activate/deactivate)
├── verification.py    # tiered authenticity (SNS signature | HMAC | hardened secret-URL) per security.md
├── router.py          # source → typed parser → intent (declarative table; no runtime import strings)
├── dispatch.py        # intent → transport render OR registered handler OR durable enqueue
├── store.py           # persistence via StorageService Protocol (frozen model in/out)
├── settings.py        # partitioned WebhookSettings (body cap, default rate, tier flags)
├── providers.py       # capability-local DI wiring
├── entrypoints/
│   ├── http.py        # POST /hook/{webhook_id} ingress + admin CRUD routes (five-step handlers)
│   └── slack.py       # the /sre webhooks admin slash-command surface
├── adapters/          # ONLY files importing app.integrations, if a provider needs a raw client
└── locales/           # EN/FR, if user-facing text exists
```

### The three-stage pipeline

Ingress collapses into three explicit stages; no guessing at any point.

1. **Verify (ingress boundary).** Tiered authenticity ([security.md](security.md) §Webhooks), body-size cap, per-`webhook_id` rate limit, and an idempotency claim keyed by the *sender-assigned* delivery id ([reliability.md](reliability.md)). All controls bind regardless of auth state. Output: a normalized `InboundEnvelope{webhook_id, raw_body, headers, provider_delivery_id}`.
2. **Interpret (by declared source, no guessing).** Load the `Webhook` record, which declares its `source`. Parse the body with **that source's** single Pydantic model at the trust boundary; provider-internal variants (e.g. SNS `SubscriptionConfirmation` vs `Notification`) branch on the provider's own discriminator as a discriminated union — never cross-model field-counting. Output: a **transport-neutral domain intent**. This stage replaces `select_best_model`, `validate_string_payload_type`, and both filesystem-walk registries.
3. **Dispatch (multi-sink).** The webhook record declares one or more **targets**, each of exactly one kind:
   - **Transport render** — post to a chat platform via its Protocol + `OperationResult`→message renderer ([platform-transports.md](platform-transports.md)). Slack today; a second transport is a new renderer over the same intent, with zero change to stages 1–2.
   - **Registered handler** — call the handler a feature registered for this source or alert through the capability's extension point (e.g. the incident feature's alert actions). The call is explicit, typed and visible at startup; the capability never imports the feature. There is no in-process event bus ([plugin-architecture.md](plugin-architecture.md)).
   - **Durable enqueue** — hand work that must survive a crash to `QueueService` ([reliability.md](reliability.md)); an idempotent consumer processes it. This is the reliable path for "trigger another business feature".

**The transport-neutral intent is the contract** that makes multi-transport and cross-feature triggering possible: it names *what happened*, not how to render it or who handles it. The capability never imports `slack_sdk.WebClient`, never imports a feature ([plugin-architecture.md](plugin-architecture.md)), and never builds a platform response shape inline.

### Source-declared, typed, fail-fast registration

The set of supported sources and their parsers is a **declarative table** in `router.py` (source → typed parser → intent builder), filled from the capability's own sources and from features' registrations through the extension point at startup, not a directory walk and not runtime import-string resolution. New sources are a reviewed code change registered at startup ([plugins.md](plugins.md)); an unresolvable or raising registration fails boot rather than being swallowed. A `generic-json`/`simple-text` fallback source preserves acceptance for senders not yet classified, while they are fingerprinted for migration (TASK-46).

### Lifecycle — secure by default

`service.py` owns webhook CRUD over the `Webhook` frozen domain model behind the storage contract ([plugin-architecture.md](plugin-architecture.md)); no code above the store handles raw DynamoDB item shapes. The admin surface (the `/sre` slash-command in `entrypoints/slack.py`, and/or authenticated HTTP admin routes) calls the service, never the store or the vendor client directly. Authenticity tiers, secret issuance, rotation/revocation, and per-`webhook_id` rate limits are governed by [security.md](security.md) §Webhooks (secure-by-default HMAC issuance; the hardened secret-URL tier is a tracked, time-boxed exception). Webhook configuration — body-size cap, default and per-webhook rate ceilings, tier flags — lives in a **partitioned `WebhookSettings`** owned by the capability ([configuration.md](configuration.md)), never in a central settings aggregator. Invocation/acknowledgement counters are an idempotent metric update or structured observability, never a read-modify-write race.

## Consequences

- Removing the guess collapses a fragile, duplicated heuristic into one typed parse per declared source; missing branches become type errors, not silent mis-classifications.
- The intent contract turns "webhooks = Slack poster" into "webhooks = authenticated ingress that fans an inbound fact out to transports and features"; adding Teams or a business-feature trigger touches only stage 3.
- Cost: every source needs an explicit parser and every webhook record must declare its source; the `generic-json` fallback absorbs the unclassified tail during migration but is itself a tracked exception, not a resting state.
- Registered-handler and durable-enqueue targets are built **on demand**: until a feature registers a handler or a crash-critical hand-off exists, dispatch targets are transport renders only — no speculative pub/sub.

## Checks

- No `select_best_model` / `has_parameters_in_model` / `validate_string_payload_type` payload-guessing remains; each webhook parses via exactly one source-declared model.
- grep: no `os.listdir`/`walk_packages`-based handler discovery and no `importlib.import_module` of handler strings under the webhooks package; sources register through the declarative table at startup and boot fails on a bad registration.
- grep: no `slack_sdk`/`WebClient` import and no Block Kit construction in the webhooks capability core (schemas/service/router/dispatch/domain); Slack shapes exist only behind the transport renderer.
- No raw DynamoDB attribute shapes (`{"S": …}`/`{"BOOL": …}`) above `store.py`; the route and service speak the `Webhook` domain model.
- Ingest is idempotent under redelivery (test: a redelivered SNS notification with the same `MessageId` posts once) per [reliability.md](reliability.md).
- Authenticity, rate-limit, and body-cap checks are governed by [security.md](security.md) §Webhooks (its Checks apply at this boundary).
- import-linter: `capabilities/webhooks` imports `integrations` only inside `adapters/`, and imports no feature.
- Boot test: every feature handler registered through the webhooks extension point is registered before the capability initializes.

## Migration

This capability is migrated **refactor-first, ahead of the general `app/modules/` strangler**: the payload-guessing and filesystem-walk antipatterns must not be lifted-and-shifted into `capabilities/`, and the Phase-4 authenticity hardening (HMAC, secure-by-default issuance) is built on the target design rather than on the legacy DynamoDB CRUD and re-written later. The webhooks migration is therefore pulled into m-4, sequenced before the HMAC work, and decomposed into single-PR slices; the external contract (webhook URLs and behaviour) is held by the smoke suite (TASK-36) across every slice, per [migration.md](migration.md).

Tickets: TASK-37 (extraction into `capabilities/webhooks/` and rearchitecture), TASK-47 (lifecycle and secure-by-default HMAC), TASK-48 (burn-down of legacy unsigned senders), TASK-49 (per-webhook rate limiting).

Tolerated until the slices close: the legacy `modules/webhooks` guessers, walk registries, and Slack-terminal shape; the `modules/slack/webhooks.py` CRUD; and the risk-accepted legacy unsigned population ([security.md](security.md)).

**Changes:**
- 2026-09-24: Migration names epic tickets only, and the pipeline is a capability whose extension point replaces domain events; handler folder renamed `entrypoints/`.

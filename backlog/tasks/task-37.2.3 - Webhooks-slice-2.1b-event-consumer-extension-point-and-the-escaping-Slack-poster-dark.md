---
id: TASK-37.2.3
title: >-
  Webhooks slice 2.1b: event-consumer extension point and the escaping Slack
  poster (dark)
status: To Do
assignee: []
created_date: '2026-11-26T13:18:00Z'
updated_date: '2026-11-26T18:40:00Z'
labels:
  - migration
  - webhooks
  - phase-4
milestone: m-4
dependencies:
  - TASK-37.2.1
  - TASK-113
references:
  - decisions/webhooks.md
  - decisions/languages.md
  - decisions/security.md
  - decisions/plugins.md
parent_task_id: TASK-37.2
priority: high
ordinal: 554000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Stack W layer W2b, split out of TASK-37.2.1 at its planning (P1, human-approved 2026-11-26). Stacked above W2; waits on TASK-113 (host extension-point phase, which TASK-195 was folded into) merged. decisions/webhooks.md 5a Extension point and 9 Output encoding; languages.md.

Scope:
- capabilities/webhooks/hookspecs.py: the webhooks extension point (event consumers by event type, handlers by id), declared through TASK-113's register_extension_points and collected once at startup into a frozen WebhookExtensions value in the service registry; a duplicate handler id or a consumer for an unregistered event type fails boot naming the plugin.
- api.py: the EventConsumer, EventHandler and registrar Protocols, and EventAction (a consumer's contributed action: a MultilingualText label, an action id, a value), so the incident alert consumer (TASK-37.3) contributes triage actions without Slack types.
- adapters/slack.py: the channel poster on AsyncWebClient, the default consumer for alert and notification. It escapes every content-derived value (&, <, >) before inserting trusted tokens (resolved mentions, adapter-built https links), and lays out MultilingualText (title, summary, link and action labels) in the destination's shared languages (LanguagePolicy). Sender details are posted once, and Slack's 3,000-character section and 50-block limits are adapter constants (Slack API facts).
- The fallback rendering for an unmatched delivery or a render failure: escaped, truncated text of the decoded message under a bot-worded header from catalogue keys in capabilities/webhooks/locales/ (en-US and fr-FR parity).
- The mention resolver: TASK-37.2.1's find_email_addresses, then at most [webhooks] email_lookups_per_message users_lookupByEmail calls per message, cached per delivery (TASK-190 hand-off F-I).

Out of scope: protocols, the inbox, ingest and the route (TASK-37.2.2); sender-kind files, the Notify handler and the incident alert consumer (TASK-37.3).
Size: ~330 production LOC, ~7 files.
Production: dark. No route, no instance, no traffic; the extension point collects no implementation outside the capability.
Revert / blast radius: one git revert.
Change notice: none (dark slice, packet section 7.4).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The webhooks extension point (consumers by event type, handlers by id) is declared through register_extension_points and its implementations are collected once at startup; a duplicate handler id or an unknown event type fails boot naming the plugin; no pluggy hook is called per request (test)
- [ ] #2 The Slack poster escapes every content-derived value: <!channel>, <@U123> and <https://x|y> in a payload field render inert, and links come only from validated https fields (test)
- [ ] #3 Bot wording (title, summary, link and action labels, the fallback header) is laid out as MultilingualText in the destination's shared languages, and sender details appear once (test)
- [ ] #4 The mention resolver makes at most the configured number of Slack lookups per message, cached per delivery (TASK-190 hand-off F-I) (test)
- [ ] #5 The fallback rendering posts escaped, truncated text of the decoded message under a catalogue-keyed header with en-US and fr-FR parity (test)
- [ ] #6 The capability core imports no slack_sdk; Slack shapes exist only in adapters/slack.py; make check-import-contracts, check-package-shape and check-fake-coverage are green (check)
- [ ] #7 The slice is dark: no route is mounted, no instance is read and production behaviour is unchanged (review)
- [ ] #8 mrkdwn objects carrying payload text set verbatim: true, plain_text is used where no trusted token is needed, truncation happens after escaping, and every Slack call has a timeout and a bounded retry (test)
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Gate: implementation starts once the TASK-113 PR (#1894, row 22.1c) has merged; `gh stack rebase` then brings ExtensionPoint, register_extension_points and run_extension_points under this layer (planned against #1894: `pm.add_hookspecs(point.specs)`, `collect` keyed by entry-point name and refusing hooks outside the specs class, `services` closed after initialize, `service_scopes` the host opener, `ExtensionPointError`). Planned against decisions/webhooks.md (1, 5a, 9), plugins.md, lifecycle.md, dependency-injection.md, platform-transports.md, platform-entrypoints.md, workplace-systems.md, languages.md, security.md, outbound-clients.md, reliability.md, people-and-accounts.md, feature-packages.md; doc-11, doc-15, doc-16, doc-17 and doc-18 hold no conflicting webhook decision (doc-16 L9c, TASK-145.7.11, owns the legacy alert-button id; doc-15 has no webhook consumer; doc-18 records W2's P1-P5).

Platform separation (the legacy webhooks are Slack end to end: modules/slack/webhooks*.py, Slack JSON in, the Slack helpers' unbounded lookups, button values pasted with alert text). The capability core is platform-neutral; Slack is one driven adapter. Backstage keeps channels as processors in separate modules behind its notifications engine ("notifications can be sent to external channels (like email) via processors implemented within plugins", backstage.io/docs/notifications) and Grafana keeps contact points apart from rules and templates (grafana.com contact points); platform-entrypoints.md names "a capability with one adapter per platform"; platform-transports.md "outbound messages are intents".
S1 (conflict, fix in W2) Destination carries its system. workplace-systems.md rule 4: "Every stored reference to a workplace artifact, account or conversation records the system and tenant alongside the vendor's id. Never store a bare vendor id." W2's `Destination(channel, triage)` breaks it (prior decisions: incident's `ResourceReference`, languages.md `shared_languages(system, tenant, conversation_id)`). Fix: `Destination(system: WorkplaceSystem, tenant: str, conversation_id: str, triage: bool = False)` (contracts/workplace's enum; no feature import), as a follow-up commit on W2's layer (stack rule: a lower layer is fixed in that layer), one test fixture updated. Scope notes: TASK-37.4.1's backfill writes `system=slack` and the configured `[slack.tenant]` id; TASK-37.6.1 validates a destination against `ConfiguredSystems`; TASK-37.2.2 skips and reports a destination whose system has no poster (managed content is untrusted, webhooks.md 4). A shared conversation reference in `contracts/workplace/` waits for a third need.
S2 One poster per platform. `ChannelPoster` (interfaces.py) takes a platform-neutral `ChannelMessage`; posters are keyed by `WorkplaceSystem`; only `slack` exists now. `slack.passthrough` (opaque Slack JSON, webhooks.md 5a) is delivered only to a Slack destination; any other is skipped and reported. Posters are capability adapters, not plugin contributions (platform-entrypoints.md); a Backstage-style poster hook is the recorded upgrade path if a platform is ever supplied by a plugin.
S3 The core decides what to say; the adapter decides how. Languages come from `LanguagePolicy.shared_languages(destination.system, tenant, conversation_id)` in the core (the processor, TASK-37.2.2), before rendering; the fallback header's wording comes from catalogue keys through a `Translator` port (interfaces.py; `adapters/i18n.py` on infrastructure.i18n, incident's pattern). The Slack adapter only lays out, escapes, resolves mentions and posts.
S4 Actions are neutral; clicks stay with the consumer. `EventAction(action_id, value, label)` has no Slack field; each poster renders it natively. A click lands on the consumer's own platform entrypoint (Slack block_actions go to the app's Request URL with `action_id` and `value`, docs.slack.dev); webhooks never handles clicks. An action id must start with the contributing plugin's entry-point name and a dot, checked when actions are gathered, so a consumer cannot fire another feature's handler.
S5 Imports. Contract (p) `webhooks-core-no-slack` (indirect imports forbidden) lists every core module: api, domain, plugin, schemas, settings, hookspecs, service, interfaces, in_memory. `providers.py` (feature-packages layout name) is the composition root that builds the Slack poster and is imported only by entrypoints and jobs (from TASK-37.2.2), so no core module reaches slack_sdk even indirectly ([composition root](https://blog.ploeh.dk/2011/07/28/CompositionRoot/)). Contract (g) already bars `modules/`; the Slack adapter uses `AsyncWebClient` and `classify_slack_error` from `integrations/slack/client.py` only, never the legacy helpers in `integrations/slack/users.py`.
S6 Neutral names. Settings and events carry no platform name (`post_attempt_timeout_seconds`, `webhook_action_dropped`); Slack limits are constants inside adapters/slack.py.

D1 Extension point. `hookspecs.py`: `WebhooksSpecs` with `register_webhook_consumers() -> Sequence[EventConsumer]` and `register_webhook_handlers() -> Sequence[EventHandler]`; TASK-113's `collect` keys results by plugin, so no registrar Protocol (dropped from scope). plugin.py adds `register_extension_points` (`ExtensionPoint(specs=WebhooksSpecs, provides=WebhookExtensions, initialize=initialize_extensions)`) and `register_i18n_resources`. `initialize_extensions(context)` (service.py) collects both hooks once; a non-sequence or non-Protocol value, a consumer with empty `event_types`, a type outside `EventType` or `slack.passthrough`, and a handler id failing `HANDLER_ID_PATTERN` or registered twice raise `ExtensionPointError` naming the plugin(s); through `context.services` every loaded sender kind's `handler:` must name a registered handler, else boot fails naming the kind (content loads before phase 4, lifecycle.md). Returns frozen `WebhookExtensions(consumers: Mapping[EventType, tuple[RegisteredConsumer, ...]]` (consumer plus its plugin name, load order), `handlers: Mapping[str, EventHandler]`, `service_scopes)`. An empty point is valid; no hook is called after startup.

D2 Contracts (api.py): `EventConsumer` (`event_types`, `actions(event, languages) -> tuple[EventAction, ...]`, `async consume(event, delivery)`, once per event), `EventHandler` (`handler_id`, `async handle(event, delivery)`), frozen `EventAction(action_id, value, label: MultilingualText)` and `Delivery(delivery_id, instance_ref, item_id, service_scopes)`; strategies open a per-call scope (dependency-injection.md) and key effects on `delivery_id`. `in_memory.py` holds the fakes check-fake-coverage requires. Invoking them from an inbox item is TASK-37.2.2.

D3 (Q1) The poster is the capability's built-in output beside consumers: the processor posts once per destination (S2); consumers contribute actions where the destination sets `triage` and receive the event once. webhooks.md 5a "the channel poster is the default consumer" is reworded. TASK-125 (notifications capability) gets a note: webhooks' ChannelPoster is a second post-to-a-channel need; at TASK-125 decide whether the webhooks adapter moves onto it.

D4 Slack layout (adapters/slack.py). `for_delivery()` returns a `DeliveryPoster` holding the per-delivery mention cache; `post(destination, message)` lays out one section per language in the given order (title in bold, summary, that language's link labels), the sender's details once, the actions block (label parts joined " / "), and a top-level `text` with the same content as plain lines (screen readers and notifications read `text`). Slack facts as adapter constants: 3,000 per section text, 50 blocks, 25 actions-block elements, 75 per button label, 2,000 per button value, 255 per action id, 4,000 for `text`; an action over a limit is dropped and logged without its value.

D5 (Q2) Encoding (security.md Webhooks; webhooks.md 9). Every content-derived value is escaped (`&` first, then `<`, `>`) into mrkdwn with `verbatim: true`, then trusted tokens are inserted: `<@U…>` (id checked `^[UW][A-Z0-9]+$`) and `<url|label>` from W2's re-encoded https URLs (a URL holding `|`, `<`, `>` or whitespace is dropped). `plain_text` only for code-owned wording (button labels): Slack calls `&`, `<`, `>` "control characters for special parsing in text objects" without exempting plain_text and documents no literal rendering of mentions in it. webhooks.md 9 and AC #8 narrowed (Changes line); plain_text for payload text only after a recorded Block Kit Builder or sandbox check.

D6 (Q3, gap) Truncation: the limit is measured on the escaped length, the raw value is cut to fit (ellipsis inside the budget) and escaping is the last step, so no entity or token is split (OWASP XSS Prevention: encode "as close to where the data is rendered is possible"; Django truncatechars_html respects markup). Code-point cuts. webhooks.md 9 and security.md Output encoding gain the rule.

D7 (Q5, conflict, tolerated) Mentions: people-and-accounts.md routes "reach this person" through the people capability (TASK-83, To Do). Until then the Slack adapter resolves directly, written as tolerated in webhooks.md Migration; TASK-83 gets an adoption note. Rules (AC #4): only for a kind with `mentions: true`, over summary and details; `find_email_addresses(text, limit)` first-seen order; at most `[webhooks] email_lookups_per_message` distinct lookups per delivery, concurrent, on the read handle; hits and misses (`users_not_found`, errors, 429, timeout) cached as "no mention"; logs carry counts, never addresses.

D8 (Q4, gap) One retry point. outbound-clients.md: "attempts × timeout, plus backoff, must fit the caller's deadline"; posts on the rate-limit-only write handle (transport-slack.md 2026-11-05, TASK-145.6.3); reliability.md: `TRANSIENT_ERROR` consumers honour `retry_after`. The Slack factories' 10 s attempt and slack_sdk's uncapped Retry-After sleep cannot fit the 5 s inline deadline. Practice: AWS Builders' Library "retry at a single point in the stack", Google SRE deadline propagation, OpenAI SDK caps Retry-After. Fix: a caller owning durable retry builds its handles with its own attempt timeout and no in-process 429 wait, handing `retry_after` to its durable retry. `integrations/slack/client.py` factories gain optional `timeout_seconds` and `rate_limit_retries` (defaults unchanged); `[webhooks] post_attempt_timeout_seconds` (default 2.0); posts never retry in process; lookups retry only a connection that never opened. outbound-clients.md gains the rule.

D9 Fallback (AC #5): `domain/rendering.py` `fallback_text(decoded, limit)` (compact JSON, `ensure_ascii=False`, neutralised); the core builds the header `MultilingualText` from `webhooks.fallback.header` (S3); the adapter escapes and lays out header and body. Catalogues `locales/webhooks.en-US.yml` and `.fr-FR.yml`; French reviewed by a human in the PR.

D10 ADR and task edits (ride with this PR): webhooks.md 1 (posters per platform, providers.py composition root), 5a (TASK-37.2.3 owns the hookspec; poster rewording; destination system and tenant), 9 (D5, D6), Migration list and the D7 tolerated line, Changes line; security.md Output encoding (D6); outbound-clients.md (D8); README. Task edits on approval: AC #1 drops "registrar"; AC #8 per D5/D6; new ACs for S1/S4/S5 (destination carries system and tenant; action ids namespaced; no core module reaches slack_sdk) and D8; TASK-147.5 depends on TASK-37.2.3 instead of 37.2.1; notes on TASK-125, TASK-83, TASK-37.2.2 (`retry_at` from `retry_after`; destinations without a poster skipped; languages resolved before render), TASK-37.4.1 and TASK-37.6.1 (S1).

Steps (TDD, failing tests first):
0. W2 layer (`gh stack checkout stack-w/task-37.2.1-event-model`): S1 Destination change and its fixture; ruff and webhooks tests; human commits, `gh stack rebase`.
1. Tests: `test_webhooks_extension_point_collects.py` (empty point, duplicate handler id naming both plugins, unknown and passthrough types, non-Protocol value, unknown `handler:` naming the kind, no hook after initialize), `test_webhooks_hookspecs_inventory.py`, `test_webhooks_event_actions_namespaced.py`.
2. hookspecs.py, api.py, in_memory.py, service.py, plugin.py; contract (p) lists the new core modules.
3. Tests: `test_webhooks_slack_poster_escapes.py` (`<!channel>`, `<@U123>`, `<https://x|y>` and `&` inert in every field; verbatim; truncation never splits an entity or token), `test_webhooks_slack_poster_languages.py`, `test_webhooks_mention_resolver_bounded.py`, `test_webhooks_slack_poster_bounded_calls.py`, `test_slack_client_factory_overrides.py`, `test_webhooks_fallback_rendering_posts.py`, `test_webhooks_locales_parity.py`, `test_webhooks_poster_selection_by_system.py`.
4. interfaces.py, providers.py, adapters/slack.py, adapters/i18n.py, locales, `fallback_text`, settings, factory parameters.
5. ADR and task edits; ruff, targeted tests, make check-import-contracts, check-settings-key-ownership, check-package-shape, check-test-seams, check-fake-coverage, check-content-schemas; full mypy then pytest under the shared lock.

Size: ~520 production LOC across ~15 files in W2b plus ~10 LOC in W2 (no consumer, dark). Over the gate, combined under the dark-slice exception. Split if refused: W2b-1 extension point and contracts (S4, S5, D1, D2; ~240 LOC), W2b-2 poster (S2, S3, D4-D9; ~280 LOC).
Production: dark; factory defaults unchanged for every existing caller. Revert: one git revert per layer. Change notice: none (dark; the hookspec's FYI rides with TASK-37.3). Shared with Lane A: `integrations/slack/client.py`, outbound-clients.md, security.md (whichever merges second keeps both sides).
<!-- SECTION:PLAN:END -->

## Comments

<!-- COMMENTS:BEGIN -->
created: 2026-11-26T13:23:00Z

---

2026-11-26 OWASP review (TASK-37.2.1 planning): mrkdwn objects carrying payload text set verbatim: true; plain_text wherever no trusted token is needed; truncate after escaping; every Slack call (post, users_lookupByEmail) has a timeout and a bounded retry (OWASP API10:2023).

---
<!-- COMMENTS:END -->

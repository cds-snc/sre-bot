---
status: Accepted
date: 2026-07-21
applies: target
scope: The Slack transport — delivery mode, verification, handler mechanics, errors, parsing/help.
---

# Slack Transport

## Context

Slack is the app's primary front door and a first-class part of the process, not an occasional outbound SDK. Six legacy records deferred Slack decisions to a `transport-slack.md` that never existed; this is that record.

Current state: sync Bolt (`App` + `SocketModeHandler` + threads) in `integrations/slack/provider.py`, while `integrations/slack/bootstrap.py` already builds an `AsyncApp`. The parser, formatter and per-command help also live in `integrations/slack/`. Legacy modules register through a hard-coded list beside pluggy discovery. `infrastructure/slack/settings.py` holds `COMMAND_PREFIX`; `infrastructure/configuration/infrastructure/platforms.py` still duplicates the Slack credential and mode fields.

## Decision

**Homes** ([platform-transports.md](platform-transports.md), [plugin-architecture.md](plugin-architecture.md)):
- `app/server/slack/`: the Bolt runtime, Socket Mode connection, verification, dispatch, parser, formatter and help, plus the transport settings.
- `app/contracts/`: the Slack registration hookspecs, handler request and reply models, and the outbound messaging Protocol handlers use to reply.
- `app/integrations/slack/`: the authenticated Web API client and `classify_slack_error`, shared by the runtime and by any feature that acts on Slack. Slack credentials live in its `settings.py` ([configuration.md](configuration.md)).

**Two client kinds, don't conflate.** Only the runtime (`AsyncApp` + `AsyncSocketModeHandler`) has a lifecycle: it opens the WebSocket in lifespan phase 5 and closes it at shutdown. A Web API client (`AsyncWebClient`) has no lifecycle; it is a plain authenticated caller built by a cached provider. There are two, differing only by token and scope:
- a **bot-scoped** client behind the outbound messaging Protocol (reply surface);
- an **admin-scoped** client behind a feature's own port when Slack is that feature's target (e.g. usergroup changes through a Path B `GroupMembershipWriter`).

Same builder, same classifier, different credential. The rule: *opens a connection and receives* → runtime, lifespan-managed; *only makes outbound calls* → a cached `AsyncWebClient` from `integrations/slack/`, starts nothing.

**Delivery mode.** Socket Mode by default (no inbound exposure; right for current deployments). HTTP Events mode is selectable with `SLACK__SOCKET_MODE=false`. Settings fail fast at boot if the selected mode's credentials are missing.

**Verification.** In HTTP mode every request is verified before its body is used: `v0=` HMAC-SHA256 with the signing secret, constant-time compare, and `X-Slack-Request-Timestamp` rejected beyond 5 minutes. In Socket Mode the connection handshake carries this; the signing secret is still configured and validated so mode switches are safe. Verification lives in the runtime, never in handlers.

**Concurrency.** Target is async Bolt (`AsyncApp` + `AsyncSocketModeHandler`) on the app's event loop, so `contextvars` correlation flows into handlers. Until then, handlers must not assume loop-local context.

**Ack-then-work.** Handlers `ack()` within the deadline, then continue in the same listener; Bolt runs each listener on its own task, so no ad-hoc `create_task` or threads. Bolt lazy listeners (a beta FaaS feature) are not used. Outcomes report through `respond` or `chat.postMessage`; anything slower than a few seconds goes through the queue ([reliability.md](reliability.md)).

**Handlers.** Features implement the Slack hookspecs in `contracts/` (`register_slack_commands`, etc.) to attach handlers at startup, through a registrar Protocol, never the Bolt app. A command handler parses via the shared parser, calls one service method, gets `OperationResult`, and renders it via the shared renderer. Discipline per [feature-packages.md](feature-packages.md).

**Block actions and view submissions.** The same registrar attaches them: a feature registers a native Bolt listener for an exact `action_id` or `callback_id`, at startup, from its `entrypoints/slack.py` ([platform-entrypoints.md](platform-entrypoints.md) rule 3). Each id is registered once and a duplicate aborts boot; ids carry the plugin's entry-point name (`incident.scribe.…`). The listener gets Bolt's own arguments, acks first (Slack allows 3 seconds), returns view field errors in that ack (`response_action="errors"`), and then does its work. Options, shortcuts, `view_closed`, regex ids and middleware are not registrable until a feature needs them. The first consumer is the status-update modal: a responder writes or AI-drafts the update, then reviews and approves it in place (TASK-140, TASK-144). Sources, read on 2026-10-06: [Bolt acknowledge](https://docs.slack.dev/tools/bolt-python/concepts/acknowledge), [Slack modals](https://docs.slack.dev/surfaces/modals), [Rootly AI](https://docs.rootly.com/ai/ai-summaries) ("You review and edit the draft before submitting").

**Command namespacing.** A dev bot and the prod bot share one Slack workspace, so slash-command names must not collide (`/dev-sre` vs `/sre`). This is a transport setting, `COMMAND_PREFIX` (env `SLACK__COMMAND_PREFIX`, default `""`), never derived from `ENVIRONMENT` ([configuration.md](configuration.md)). Features declare base names (`sre`, `aws`); the runtime prepends the prefix once, centrally, when wiring registered commands into Bolt.

**Errors.** No wrapper layer around Bolt callables: monkey-patching `say`/`respond` changes Bolt's documented contract and depends on its internals. Web API calls go through a Protocol (the outbound messaging Protocol for replies; a feature's own port for outbound targets) whose adapter maps `SlackApiError` → `OperationResult` via `classify_slack_error` (rate limit → `TRANSIENT_ERROR` with `retry_after`). `say`/`respond` failures inside a handler use a small shared try/except helper. SDK-native `RetryHandler` is configured once at client construction.

**Rich interactions.** Entry points use Bolt's documented objects (`ack`, `client`, `respond`, `say`) directly; services never see them. Any shared helper for modals, message updates or replies adds conventions on top of those calls and never wraps Bolt or `slack_sdk` ([platform-transports.md](platform-transports.md) rule 7). A standard Slack toolkit is proposed in [interaction-toolkits.md](interaction-toolkits.md) (Draft).

**Parsing and help.** The incumbent parser (`Argument` schema, quote-aware) is kept; its tokenizer should delegate to `shlex.split`. Help is rendered from the same schema that parses. `description_key`/`example_keys` are the localized form; plain `description`/`examples` literals are deprecated once i18n parity lands ([i18n.md](i18n.md)).

## Consequences

- One home per part ends the "where does Slack live" dispute; command names and behavior are unchanged by the move.
- Rejecting the callable wrapper keeps Bolt's documented semantics for anyone reading Slack's docs.
- Cost: the registrar Protocol hides Bolt registration options the contract doesn't expose; handling inside a listener is not limited.

## Checks

- HTTP-mode signature verification has tests (valid, tampered, stale timestamp).
- `slack_bolt` imported in features only by `entrypoints/slack.py`; `slack_sdk` only there, in `adapters/`, or as declared pure-data models; none in services, `core/` or `common/`.
- Boot test: a duplicate action or view id aborts boot.
- One registration path: no hard-coded `register(bot)` list once migration completes.

## Migration

Tickets: TASK-26 (Slack home consolidation), TASK-33 (async Bolt), TASK-41 (legacy registration list), TASK-24 (one settings home per vendor), TASK-140 (action and view-submission registration).

Tolerated until then:
- the runtime, parser, formatter and help in `integrations/slack/`, and `COMMAND_PREFIX` in `infrastructure/slack/settings.py`;
- sync `SocketModeHandler` in `provider.py` beside the `AsyncApp` in `bootstrap.py`;
- dual registration: the legacy `register(bot)` list in `server/lifespan.py` beside the `register_slack_commands(registrar: SlackCommandRegistrar)` hookspec;
- `slack_sdk.WebClient` imported outside `adapters/` in `packages/oncall_sync/providers.py` and `packages/rant/platforms/slack.py`;
- legacy modules building command names from `COMMAND_PREFIX` in their own `bot.command()` calls;
- the duplicate Slack settings in `infrastructure/configuration/infrastructure/platforms.py`, deleted rather than extended.

**Changes:**
- 2026-09-24: runtime moves to `server/slack/`, hookspecs and the outbound Protocol to `contracts/`, per plugin-architecture.md; dropped the closed `PREFIX` retirement; Migration names epic tickets only; shared Slack helpers never wrap Bolt or `slack_sdk`, and a standard toolkit is an open Draft.
- 2026-10-01: the Slack hookspec takes the registrar Protocol and `register_slack_listeners` is deleted (TASK-26.1); the dual-registration item now names only the legacy list.
- 2026-10-06: block actions and view submissions are registered through the registrar as native Bolt listeners in feature entry points; `slack_bolt` is allowed there only (TASK-140.1).
- 2026-10-09: the first consumer is described as the human-first status-update modal, where AI drafting is an optional assist (TASK-144).

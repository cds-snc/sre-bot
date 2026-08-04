---
status: Accepted
date: 2026-07-21
applies: target
scope: The Slack transport — delivery mode, verification, handler mechanics, errors, parsing/help.
---

# Slack Transport

## Context

Slack is the app's primary front door and a first-class part of the process — not an occasional outbound SDK. Six legacy records deferred Slack decisions to a `transport-slack.md` that never existed; this is that record. Current state: sync Bolt (`App` + `SocketModeHandler` + threads) in `integrations/slack/`, with a working command parser and per-command help; legacy modules register via a hard-coded list beside pluggy discovery.

## Decision

**Home.** The Slack **inbound transport** lives in `app/infrastructure/slack/` per [platform-transports.md](platform-transports.md): Bolt runtime, verification, dispatch, parser, formatter, help, and the `SlackService` reply Protocol. The authenticated **Web API client** (`build_slack_web_client`) and `classify_slack_error` live in `app/integrations/slack/` — shared by the transport and by any feature that acts on Slack. Slack credentials live in `app/integrations/slack/settings.py` ([configuration.md](configuration.md)).

**Two client kinds — don't conflate.** Only the **inbound runtime** (`AsyncApp` + `AsyncSocketModeHandler`) has a lifecycle: it opens the WebSocket in lifespan phase 5 and closes it at shutdown. A **Web API client** (`AsyncWebClient`) has no lifecycle — it is a plain authenticated caller built by a cached provider, opening no persistent connection. There are two of them, differing only by token/scope: a **bot-scoped** client backing the transport's `SlackService` (reply surface), and an **admin-scoped** client behind a feature's outbound port when Slack is that feature's target (e.g. HTTP-triggered usergroup changes — a Path B `GroupMembershipWriter`, not `SlackService`). Same `build_slack_web_client`, same classifier, different credential — see [platform-transports.md](platform-transports.md) "a platform is also a driven dependency". The rule: *opens a connection and receives* → transport, lifespan-managed; *only makes outbound calls* → a cached `AsyncWebClient` from `integrations/slack/`, starts nothing.

**Delivery mode.** Socket Mode by default (no inbound exposure; right for current deployments); HTTP Events mode selectable via `SLACK__SOCKET_MODE=false` for environments that need it. Settings fail fast at boot if the selected mode's credentials are missing.

**Verification.** In HTTP mode, every request is verified before body use: `v0=` HMAC-SHA256 with the signing secret, constant-time compare, and `X-Slack-Request-Timestamp` rejected beyond 5 minutes (replay). In Socket Mode this is carried by the connection handshake; the signing secret is still configured and validated so mode switches are safe. Verification lives in the transport, never in handlers.

**Concurrency.** Target is async Bolt (`AsyncApp` + `AsyncSocketModeHandler`) on the app's event loop, so `contextvars` correlation flows into handlers. The sync-Bolt-plus-threads implementation is a tolerated divergence with a migration ticket; until it closes, handlers must not assume loop-local context.

**Ack-then-work.** Handlers `ack()` within the deadline, then continue the remaining work **in the same listener** — Bolt runs each listener on its own worker/task, so no ad-hoc `create_task` or threads are needed. (Bolt *lazy listeners* are a beta FaaS-deployment feature and are not used in this long-running process; revisit only if handlers ever move to FaaS.) Outcomes report through `respond`/`chat.postMessage`; anything slower than a few seconds goes through the queue ([reliability.md](reliability.md)).

**Handlers.** Features implement Slack hookspecs (`register_slack_commands`, etc.) to attach handlers at startup. A handler: parses via the shared parser, calls one service method, gets `OperationResult`, renders via the shared renderer. Discipline per [feature-packages.md](feature-packages.md).

**Command namespacing (dev vs prod).** A dev bot and the prod bot share one Slack workspace, so their slash-command names must not collide (`/dev-sre` vs `/sre`). This is a **transport-owned** concern, not an environment-derived one: an explicit `COMMAND_PREFIX: str = ""` field on the Slack transport settings (`app/infrastructure/slack/settings.py`, env `SLACK__COMMAND_PREFIX`; transport settings home per [configuration.md](configuration.md)), **never** derived from `ENVIRONMENT` or the legacy `PREFIX==""` bit ([configuration.md](configuration.md) prohibits `PREFIX`/environment derivation). Features declare **base** command names (`sre`, `aws`) via `register_slack_commands`; the transport prepends `COMMAND_PREFIX` **once, centrally, at registration/compose time** when wiring hookspec-registered commands into Bolt. One place owns the prefix, not each handler. Default `""` (prod); set `SLACK__COMMAND_PREFIX=dev-` for dev instances.

**Errors.** No wrapper layer around Bolt callables (the rejected "Slack shield" — monkey-patching `say`/`respond` changed Bolt's documented contract and depended on Bolt internals). Instead: Web API calls go through a Protocol (`SlackService` for the transport's replies; a feature's own port for outbound targets), whose adapter maps `SlackApiError` → `OperationResult` via `integrations/slack`'s shared `classify_slack_error` (rate-limit → `TRANSIENT_ERROR` with `retry_after`). `say`/`respond` failures inside a handler use a small shared try/except helper. SDK-native `RetryHandler` is configured once at client construction.

**Parsing & help.** The incumbent parser (`Argument`-schema, quote-aware) is blessed as-is; its tokenizer should delegate to `shlex.split`. Help is rendered from the same schema that parses — one source of truth; `description_key`/`example_keys` are the localized form and the plain `description`/`examples` literals are deprecated once i18n parity lands ([i18n.md](i18n.md)).

## Consequences

- One home ends the three-way "where does Slack live" dispute; other-team-facing surface (command names, behavior) is unchanged by the move.
- Rejecting the callable-wrapper keeps Bolt's documented semantics for anyone reading Slack's docs — new-dev friendliness beats envelope uniformity inside handlers.

## Checks

- HTTP-mode signature verification has tests (valid, tampered, stale timestamp).
- No `slack_bolt` or `slack_sdk` imports in `app/packages/` outside declared pure-data model imports.
- One registration path: no hard-coded `register(bot)` list once migration completes.

## Migration

Tickets: home consolidation (runtime → `infrastructure/slack/`, Web client + classifier → `integrations/slack/`); async Bolt completion; legacy-list removal (tracked in [migration.md](migration.md)). Tolerated: mixed sync/async Bolt (an `AsyncApp` already exists in `bootstrap.py` while `provider.py` runs the sync `SocketModeHandler`), current dual registration, transport code (parser, formatter) still under `integrations/slack/`.

**Third Slack settings home — `platforms.py` retirement.** `app/infrastructure/configuration/infrastructure/platforms.py` (`SlackPlatformSettings`/`PlatformsSettings`) is a **third, undocumented duplicate** of the Slack credential/mode fields already owned by `integrations/slack/settings.py::SlackSettings` (the target home) and the old twin `infrastructure/configuration/integrations/slack.py`. It is dead at runtime except for the settings aggregator and tests — the live provider (`integrations/slack/provider.py`) reads `get_slack_settings()` from `integrations/slack/settings.py`, not `platforms.py`. It is retired as part of the *same* one-home-per-vendor consolidation as [configuration.md](configuration.md) / TASK-24, whose scope must be widened to name this third home (TASK-24 today names only the `integrations/` twin). No credential or namespacing field lands in `platforms.py`; it is deleted, not extended. Ticket: TASK-24 owns the `platforms.py` deletion (as part of the one-home consolidation); the `COMMAND_PREFIX` transport setting is TASK-45.

**Command namespacing — retiring `AppSettings.PREFIX` (TASK-45).** The legacy files that build `f"/{PREFIX}<cmd>"` from `AppSettings.PREFIX` (`atip`, `aws`, `incident`, `role`, `secret`, `sre`, plus the `dev` package docstring) are frozen ([migration.md](migration.md)) — but retiring the overloaded `PREFIX` namespace is the freeze's one bounded carve-out ([migration.md](migration.md)), because the overload blocks the settings-home consolidation and the environment-derivation guardrail. `AppSettings.PREFIX` no longer carries any environment meaning — TASK-1.2.3 moved all environment derivation to the typed `ENVIRONMENT` ([configuration.md](configuration.md)); the field now exists **solely** as this command-namespace string, and is being removed. Each module cuts over **individually, one PR each, behind pre/post command-name smoke tests**: it stops reading `AppSettings.PREFIX` and reads the transport's `COMMAND_PREFIX` instead. Interim shape is allowed — a still-legacy module may read `COMMAND_PREFIX` directly while keeping its own `bot.command()` call; a fully migrated feature declares a **base** name and lets the transport prepend the prefix centrally. During coexistence operators keep `PREFIX` and `SLACK__COMMAND_PREFIX` set to the **same** value per environment (both `dev-` in dev, both `""` in prod) so a half-migrated process never mixes `/dev-sre` with `/aws`; each module's smoke tests verify the resulting command name is unchanged. `atip`'s **second** use of `PREFIX` — prefixing created *channel names* (`dev-tmp-atip-…`) — is **not** a command-namespace concern and does **not** move to `COMMAND_PREFIX`; it moves to its own home (`ENVIRONMENT`-derived or an `atip` feature setting) during atip's cutover. `AppSettings.PREFIX` is deleted when the **last module cuts over** (no longer gated on full `app/modules/` deletion); the environment-derivation guardrail's whitelist ([configuration.md](configuration.md) Checks, TASK-1.3) ratchets down to empty as each module lands.

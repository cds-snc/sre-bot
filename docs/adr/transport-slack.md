---
title: "Slack Transport"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [api, architecture, plugins]
constrained_by: [layered-architecture.md, dependency-injection.md, configuration-ownership.md, application-lifecycle.md, plugin-registration-discovery.md, feature-package-structure.md, cross-channel-correlation.md, multi-transport-architecture.md, feature-handler-standard.md, operation-result-pattern.md, client-module-placement.md, type-boundaries.md, infrastructure-i18n.md, package-management.md, client-sdk-shield-pattern.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Slack Transport

## Context and Problem Statement

Slack is a first-class platform the application integrates with. Inbound interactions arrive as slash commands, events, block actions, shortcuts, and view interactions. Outbound communication uses Slack's Web API (`chat.postMessage`, `views.open`, etc.) and the interaction `response_url` webhook path.

This record pins: SDK selection; delivery mode; module placement; developer-facing outbound surface and how it is injected into handlers; Bolt context access; hookspec catalogue; inbound dispatch and verification; authentication; slash command argument parsing; help text; i18n; and settings-driven enablement.

**Core design intent:** feature handlers import an initialized `SlackService` and call its methods with the same syntax as the raw `AsyncWebClient`. The resilience boundary (retry, budget, `OperationResult` classification) is invisible at the call site. Handlers never write `try/except SlackApiError` and never call `shield.execute(...)` directly.

**Constraints:**

- Feature handler and adapter code never imports `slack_bolt.*`, `slack_sdk.web.*`, `slack_sdk.socket_mode.*`, or `slack_sdk.errors.*` per [import-governance.md](import-governance.md). Pure-data model imports (`slack_sdk.models.*`) are permitted everywhere per [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md).
- Vendor clients receive scalar credentials via constructor; the `BaseSettings` instance is never passed to vendor clients ([configuration-ownership.md](configuration-ownership.md)).
- `app/integrations/slack/` owns raw, authenticated vendor SDK access ([client-module-placement.md](client-module-placement.md)). The composed service lives in `app/infrastructure/slack/`.
- `ack()` is **excluded from the shield** — it is a framework-managed in-process signal with no network failure surface. It must be the first `await` in every interactive handler and must never be routed through `SlackService`.

**Non-goals:** per-feature handler implementations; Teams or other platform specifics; `OperationResult` shape; i18n library selection (pending [infrastructure-i18n.md](infrastructure-i18n.md)); migration mechanics from legacy code.

## Considered Options

1. **Slack Bolt for Python, Socket Mode default, HTTP Events supported (chosen).** First-party Python framework; Socket Mode requires no per-deployment URL configuration and behaves identically across local dev, staging, and production.
2. **Slack Bolt for Python, HTTP Events default.** Same SDK; requires per-deployment Slack URL configuration and per-event signing-secret verification.
3. **Lower-level `slack_sdk` only (no Bolt).** Maximum control; rejected — reimplements Bolt's middleware, handler registration, and Socket Mode handler at high cost.
4. **Continue with `infrastructure/platforms/` unified-platform abstraction.** Already rejected by the corpus.

## Decision Outcome

**Chosen: Option 1 — Slack Bolt for Python, Socket Mode default, HTTP Events supported.**

Socket Mode initiates the WebSocket outbound using the app-level token — no per-deployment Slack URL configuration, no per-environment Slack app URL maintenance, identical behaviour across local development and production. HTTP Events mode is selected via `socket_mode=false` for deployments that have a stable public URL.

### Developer-facing surface

Feature handlers receive an initialized `SlackService` injected by Bolt middleware. They call its methods with the same argument syntax as `AsyncWebClient`. The shield wrapping — retry, per-call budget, `OperationResult` classification — is invisible.

**Injection — shielded Bolt callables.** A Bolt middleware registered at app startup replaces every listener-injected callable that makes outbound Slack wire calls with a shielded equivalent before any handler runs. The mechanism is reliable: `BoltContext` is a plain `dict` subclass ([`base_context.py`](https://github.com/slackapi/bolt-python/blob/main/slack_bolt/context/base_context.py)); property getters for `say`, `respond`, and `client` check `if "key" not in self` before constructing the default ([`async_context.py` lines 95-114](https://github.com/slackapi/bolt-python/blob/main/slack_bolt/context/async_context.py)); middleware writes these keys before the property fires; `async_utils.py` line 52 calls `request.context.say` (the property), which returns the already-stored shielded value.

```python
async def shield_listener_callables(
    context: BoltContext, next: Callable
) -> None:
    context["say"] = ShieldedSay(          # chat_postMessage with implicit channel from context
        slack_service, channel=context.channel_id, thread_ts=context.thread_ts
    )
    context["respond"] = ShieldedRespond(  # response_url POST with implicit URL from context
        slack_service, response_url=context.response_url
    )
    context["client"] = slack_service      # all other Web API calls via SlackService
    await next()

app.middleware(shield_listener_callables)
```

`ShieldedSay` and `ShieldedRespond` are thin wrappers in `app/infrastructure/slack/` that preserve Bolt's native call signatures (`say(text, blocks, thread_ts, ...)`, `respond(text, replace_original, ...)`) while routing through `SlackShield` and returning `OperationResult`.

**Handler pattern.** Handlers use native Bolt parameter names — `say`, `respond`, `client` — with shield wrapping completely invisible. `ack` is the only Bolt callable that is *not* shielded: it is a framework-managed in-process signal with no network failure surface and must be the first `await` in every interactive handler.

```python
@hookimpl
async def register_slack_listeners(app: SlackApp) -> None:
    app.command("/sre")(handle_sre_command)
    app.action("approve")(handle_approve)

async def handle_sre_command(
    ack: Ack,
    say,                   # ShieldedSay — same call syntax; returns OperationResult
    client: SlackService,  # SlackService — all Web API methods; returns OperationResult
    context: BoltContext,  # request metadata: user_id, team_id, channel_id, response_url, etc.
    body: dict,
) -> None:
    await ack()                            # always first; NOT shielded — in-process only
    await say(text="Processing...")        # shield invisible — OperationResult returned
    result = await client.views_open(      # shield invisible — OperationResult returned
        trigger_id=body["trigger_id"],
        view=View(type="modal", title=PlainTextObject(text="SRE"), blocks=[...]),
    )

async def handle_approve(
    ack: Ack,
    respond,               # ShieldedRespond — posts to response_url; returns OperationResult
    context: BoltContext,
) -> None:
    await ack()
    await respond(text="Approved.", replace_original=True)  # shield invisible
```

**Bolt context metadata.** `BoltContext` carries per-request metadata: `user_id`, `team_id`, `channel_id`, `enterprise_id`, `bot_id`, `response_url`, `is_enterprise_install`, `actor_*` fields, `thread_ts`. Handlers access it by declaring `context: BoltContext`. It is unaffected by the shield. ([Bolt context reference](https://docs.slack.dev/tools/bolt-python/reference/context/))

**Workflow Step callables.** Bolt injects `complete`, `fail`, and several AI/Assistant callables (`set_status`, `set_title`, `set_suggested_prompts`, `get_thread_context`, `save_thread_context`) for Workflow Step and Assistant listeners. These follow the same middleware override pattern and must be shielded when the application adopts those listener types. They are not in scope for the current feature set and are not included in `shield_listener_callables` until needed. ([Bolt listener arguments](https://docs.slack.dev/tools/bolt-python/concepts/listener-arguments/))

### Module placement

| Concern | Path | Contents |
| --- | --- | --- |
| Raw vendor SDK access | `app/integrations/slack/` | Authenticated factories constructing `AsyncApp`, `AsyncWebClient`, `AsyncSocketModeHandler`; signing-secret verification utility (HMAC-SHA256); `SlackShield` (per [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md)); no business logic. |
| Composed infrastructure service | `app/infrastructure/slack/` | `SlackService` Protocol and concrete implementation; context-injection middleware; inbound adapter (verification → correlation binding → pluggy dispatch); connection lifecycle; `parsing.py`; `formatter.py` (`OperationResult` → Block Kit); `help.py`; `lifecycle.py`; `settings.py` (`SlackSettings`); `models.py` (Slack-shaped value types); `providers.py` (DI providers); `__init__.py` (re-exports `SlackService`, `SlackApp`, `SlackInteractionContext`). |

Feature adapters import only from `app.infrastructure.slack`. `app/integrations/slack/` is forbidden to feature code per [import-governance.md](import-governance.md).

View and block construction in feature adapters uses `slack_sdk.models.blocks` and `slack_sdk.models.views` directly. These are typed classes with client-side validation; `AsyncWebClient` auto-converts them at the boundary. No manual `.to_dict()` required.

### `SlackService` Protocol surface

`SlackService` is a curated facade over `SlackShield`. Each method matches the corresponding `AsyncWebClient` signature, takes the same keyword arguments, and returns `OperationResult[SlackResponse]`. The `**kwargs` passthrough preserves the full SDK surface without requiring a new Protocol method for every SDK flag.

Current operations (extended as features need more):

| Method | Web API | Notes |
| --- | --- | --- |
| `chat_postMessage(*, channel, text, blocks, thread_ts, **kwargs)` | `chat.postMessage` | Primary message delivery. |
| `chat_postEphemeral(*, channel, user, text, blocks, **kwargs)` | `chat.postEphemeral` | Visible only to the target user. |
| `views_open(*, trigger_id, view, **kwargs)` | `views.open` | Modal presentation; `trigger_id` expires in 3 seconds. |
| `views_update(*, view_id, hash, view, **kwargs)` | `views.update` | Update an open modal. |
| `views_push(*, trigger_id, view, **kwargs)` | `views.push` | Push a new modal onto the stack. |
| `conversations_info(*, channel, **kwargs)` | `conversations.info` | Channel membership/metadata check. |
| `conversations_join(*, channel, **kwargs)` | `conversations.join` | Bot joins a channel. |
| `conversations_archive(*, channel, **kwargs)` | `conversations.archive` | Archive a channel. |
| `users_lookupByEmail(*, email, **kwargs)` | `users.lookupByEmail` | Resolve email → Slack user. |
| `respond(*, response_url, text, blocks, replace_original, **kwargs)` | `response_url` webhook | Wraps `AsyncWebhookClient`; uses webhook classification table. Used directly in background/programmatic contexts; in listeners use the Bolt-injected shielded `respond` instead. |

For any Slack Web API method not on this list, use the raw shield escape hatch (`shield.execute(shield.web.<method>(...))`) as an interim step, then promote it to a Protocol method on the next PR.

### Authentication and credentials

| Field | Slack designation | Purpose |
| --- | --- | --- |
| `bot_token` | `xoxb-…` | Bot token; every Web API call. |
| `app_token` | `xapp-…` | App-level token; **Socket Mode only**. |
| `signing_secret` | hex string | **HTTP Events only**; HMAC-SHA256 per-event verification. |
| `enabled` | boolean (default `false`) | Gates the entire Slack platform. |
| `socket_mode` | boolean (default `true`) | Selects delivery mode. |

`SlackSettings(BaseSettings)` in `app/infrastructure/slack/settings.py` declares all five. Missing values when `enabled=true` cause fail-fast at the configuration phase.

### Resilience wiring

Outbound resilience is wired at `AsyncWebClient` construction. No project-local retry loop wraps Slack calls per [outbound-retry-policy.md](outbound-retry-policy.md) Shape A.

| Handler | Purpose |
| --- | --- |
| `AsyncConnectionErrorRetryHandler` | Transport-level connection failures. |
| `AsyncRateLimitErrorRetryHandler` | `ratelimited` responses, honoring `Retry-After` up to 30-second cap. |
| `AsyncServerErrorRetryHandler` | HTTP 5xx responses with jittered exponential backoff. |

Full shield mechanics are in [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md). The two Slack-specific classification tables follow.

**Web API classification** (`AsyncWebClient` + all `SlackService` methods except `respond`):

| `SlackApiError.response.data["error"]` | `OperationResult.status` |
| --- | --- |
| `channel_not_found`, `user_not_found`, `message_not_found`, `view_not_found` | `NOT_FOUND` |
| `not_authed`, `invalid_auth`, `account_inactive`, `token_revoked`, `token_expired`, `missing_scope` | `UNAUTHORIZED` |
| `ratelimited` (post-retry) | `TRANSIENT_ERROR` with `retry_after` |
| `fatal_error`, `internal_error`, `service_unavailable` (post-retry) | `TRANSIENT_ERROR` |
| Any other Slack error code | `PERMANENT_ERROR` with the code in `error_code` |
| `asyncio.TimeoutError` (per-call budget) | `TRANSIENT_ERROR` |
| Any other exception | `PERMANENT_ERROR` |

**Webhook classification** (`SlackService.respond` / `AsyncWebhookClient`):

| Condition | `OperationResult.status` |
| --- | --- |
| HTTP 200 | `SUCCESS` |
| HTTP 404 (invalid or expired `response_url`) | `PERMANENT_ERROR` |
| HTTP 429 | `TRANSIENT_ERROR` with `retry_after` from header |
| HTTP 5xx | `TRANSIENT_ERROR` |
| `asyncio.TimeoutError` | `TRANSIENT_ERROR` |
| `ValueError` (missing `response_url`, wrong type) | `PERMANENT_ERROR` |
| Any other exception | `PERMANENT_ERROR` |

Both tables live in `app/integrations/slack/shield.py`.

`response_url` is valid for 30 minutes and accepts at most 5 responses per interaction — a multi-call quota the shield cannot enforce per call. Handlers calling `respond` more than once per interaction are responsible for tracking the quota.

### Delivery mode and inbound dispatch

Both modes share the same inbound-adapter phase (verification → correlation binding → pluggy dispatch):

**Socket Mode (default).** `AsyncSocketModeHandler` is started during the lifespan transport phase. No signing-secret verification — the WebSocket is pre-authenticated. Each event opens a fresh correlation context per [cross-channel-correlation.md](cross-channel-correlation.md). One connection per process; Bolt manages reconnection.

**HTTP Events.** `SlackRequestHandler` mounts onto the FastAPI app at a configured path (`/slack/events`). Each inbound POST is verified against the signing secret (HMAC-SHA256, 5-minute timestamp window) before reaching Bolt dispatch; failures return `401`.

### Hookspec catalogue

The Slack platform contributes one hookspec:

```python
@hookspec
async def register_slack_listeners(app: SlackApp) -> None:
    """Register all Slack listeners for this feature against the Bolt AsyncApp."""
```

Features call Bolt's native listener-registration methods directly against the `AsyncApp` instance. The single hookspec covers the full Bolt listener surface (`command`, `event`, `message`, `action`, `shortcut`, `view`, `options`, `function`, `assistant`, `middleware`, `error`). No new hookspec is needed when Bolt adds a listener type.

### Slash command argument parsing

`app/infrastructure/slack/parsing.py` provides a Pydantic-model-driven argument parser:

- Feature declares its argument schema as a Pydantic `BaseModel` per [type-boundaries.md](type-boundaries.md).
- Parser supports flags (`--managed`), options with values (`--role OWNER`), positional arguments, multi-value options, required/optional validation, and default substitution.
- Parse failures map to `PERMANENT_ERROR` with a feature-displayable message.
- Help text is derived from the argument schema.

### Help text and `OperationResult` rendering

`app/infrastructure/slack/help.py` renders slash command help into Block Kit from each command's Pydantic argument schema. Text is localized via I18nService.

`app/infrastructure/slack/formatter.py` is the only location that constructs Block Kit from `OperationResult`. It renders `SUCCESS` payloads into feature-defined success blocks, and error statuses into standard error blocks surfacing `error_code`, `message`, and `request_id`. Feature adapters that construct their own views use `slack_sdk.models` directly — the formatter is not involved in arbitrary view construction.

### 3-second acknowledgement discipline

Slack requires interactive payloads to be acknowledged within **3 seconds**.

- `ack()` must be the first `await` in every interactive handler.
- `ack()` is a framework-managed in-process signal — it is **never** routed through `SlackService`.
- Fast handlers: `await ack()` then work, optionally `await ack(response)`.
- Slow handlers: `await ack()` immediately, continue work asynchronously, deliver result via `SlackService.chat_postMessage` or `SlackService.views_update`.
- `trigger_id` values (for `views_open`) expire in 3 seconds and are single-use. Call `slack.views_open` before any slow work.
- Long-running work exceeding the `response_url` 30-minute window is delivered via `chat_postMessage`, not `respond`.

### Internationalization

Slack outbound text is localized through the I18nService Protocol. The formatter and help renderer accept a `Locale` parameter resolved from `BoltContext` (locale hint available via `context` or the user's profile). The current custom translation utility is pending deprecation per [infrastructure-i18n.md](infrastructure-i18n.md); the integration pattern is unchanged by that swap.

### Plugin discovery

When `SlackSettings.enabled=false`:

- `SlackService`, `SlackShield`, and the context-injection middleware are not constructed.
- The host applies `pm.set_blocked("<feature>")` on every Slack-only feature plugin before `load_setuptools_entrypoints()`. Features targeting multiple platforms continue to load.

## Consequences

**Positive:**

- Handlers use native Bolt parameter names (`say`, `respond`, `client`) with the same call syntax as the raw SDK. The shield is completely invisible at call sites — no `execute()` ceremony, no `try/except SlackApiError`.
- `OperationResult` is the only exception surface above the service boundary. Handlers pattern-match on status; they never import or handle SDK exception classes.
- `slack_sdk.models` provides typed Block Kit construction with client-side validation — no inline dict literals, full IDE completion.
- Bolt's full listener surface is available via the single `register_slack_listeners` hookspec. Adding a new interaction type requires no ADR change.
- `SLACK_ENABLED=false` produces a genuinely absent platform.
- Socket Mode default removes per-deployment URL requirements; switching delivery modes is a settings change.

**Tradeoffs accepted:**

- The `SlackService` Protocol surface is a curated facade — adding a new Slack API method requires a small PR. The `**kwargs` passthrough mitigates this; the full SDK surface is accessible via the shield escape hatch as an interim step.
- Workflow Step / AI Assistant callables (`complete`, `fail`, `set_status`, etc.) are not shielded until the application adopts those listener types. The middleware pattern is the same when they are added.
- Hard dependency on Bolt for Python. Acceptable given Bolt's maturity and Slack's investment in it.

**Risks:**

- A handler bypasses the shield by directly awaiting `SlackShield.web.<method>(...)` or importing `slack_sdk` in a handler file. Mitigation: lint rule in [import-governance.md](import-governance.md) flags `slack_sdk.*` transport imports in handler files; code review.
- A handler uses a Workflow Step or AI/Assistant callable (`complete`, `fail`, etc.) before `shield_listener_callables` is updated to shield them. Mitigation: `shield_listener_callables` is the single place to add shielding; the Confirmation test suite asserts all outbound callables route through `OperationResult`.
- Slack or Bolt API changes requiring `SlackService` surface changes. Mitigation: the Protocol is shaped by what the application uses; the `**kwargs` passthrough absorbs new optional parameters without method changes.

## Confirmation

- **Repository structure.** `app/integrations/slack/` contains raw Bolt/Web-API factory code and `SlackShield` only. `app/infrastructure/slack/` contains `service.py`, `lifecycle.py`, `parsing.py`, `formatter.py`, `help.py`, `models.py`, `settings.py`, `providers.py`, `__init__.py`. No `app/infrastructure/platforms/` or `app/infrastructure/clients/slack/`.
- **Import contract.** `import-linter` forbids `slack_bolt.*`, `slack_sdk.web.*`, `slack_sdk.socket_mode.*`, `slack_sdk.errors.*` in handler and feature files. `slack_sdk.models.*` is permitted everywhere.
- **Handler pattern.** Every interactive handler: (1) `await ack()` as first statement — never shielded; (2) uses `say`, `respond`, `client` from Bolt's injected parameters — all shielded by `shield_listener_callables` middleware; (3) never imports or awaits `slack_sdk.*` transport modules directly; (4) never calls `shield.execute(...)` directly in handler code.
- **Settings.** `SlackSettings` defines `bot_token`, `app_token`, `signing_secret`, `enabled`, `socket_mode`. Missing values when `enabled=true` cause fail-fast at configuration phase.
- **Tests.** Boot test asserts `SlackService` starts/stops with `enabled=true` and is absent with `enabled=false`. Handler test asserts the inbound adapter opens a correlation context per event. Formatter test asserts each `OperationStatus` renders to the correct Block Kit shape. Shield executor tests cover each error code in both classification tables.

## Source References

1. Slack — Bolt for Python
   - URL: <https://docs.slack.dev/tools/bolt-python/>
   - Accessed: 2026-05-08
   - Relevance: First-party Python framework; canonical listener registration surface.

2. Slack — Bolt for Python: Context
   - URL: <https://docs.slack.dev/tools/bolt-python/reference/context/>
   - Accessed: 2026-05-13
   - Relevance: Documents `BoltContext` fields (`user_id`, `team_id`, `channel_id`, `enterprise_id`, `response_url`, etc.) and the context-injection mechanism (`context["key"] = value` in middleware, resolved by parameter name in handlers). Grounds the `inject_slack_service` middleware and the `context: BoltContext` handler parameter.

3. Slack — Bolt for Python: Acknowledging requests
   - URL: <https://docs.slack.dev/tools/bolt-python/concepts/acknowledge/>
   - Accessed: 2026-05-13
   - Relevance: 3-second deadline; `ack()` is an in-process signal (the framework flushes the HTTP 200). Grounds `ack()` exclusion from the shield.

4. Slack — Comparing HTTP Events API and Socket Mode
   - URL: <https://docs.slack.dev/apis/events-api/comparing-http-socket-mode>
   - Accessed: 2026-05-08
   - Relevance: Socket Mode preferred when no public URL is required; grounds the Socket Mode default.

5. Slack — Using Socket Mode
   - URL: <https://docs.slack.dev/apis/events-api/using-socket-mode>
   - Accessed: 2026-05-08
   - Relevance: `xapp-` token, `apps.connections.open`, pre-authenticated WebSocket, no per-event verification.

6. Slack — Verifying Requests from Slack
   - URL: <https://docs.slack.dev/authentication/verifying-requests-from-slack>
   - Accessed: 2026-05-08
   - Relevance: HMAC-SHA256 signing-secret scheme for HTTP Events; 5-minute replay window.

7. Slack — Handling User Interaction
   - URL: <https://docs.slack.dev/interactivity/handling-user-interaction>
   - Accessed: 2026-05-08
   - Relevance: 3-second ack deadline; `trigger_id` 3-second expiry; `response_url` 5-call / 30-minute constraints.

8. Slack — Bolt for Python: Listener arguments
   - URL: <https://docs.slack.dev/tools/bolt-python/concepts/listener-arguments/>
   - Accessed: 2026-05-13
   - Relevance: Canonical list of all Bolt-injected listener parameters. Outbound callables include `say` (calls `chat_postMessage`), `respond` (posts to `response_url`), `client` (raw `AsyncWebClient`), and Workflow/AI callables (`complete`, `fail`, `set_status`, etc.). All bypass the shield if used unmodified. Grounds the `shield_listener_callables` middleware scope.

9. Slack — Bolt for Python: Listener context source
   - URL: <https://github.com/slackapi/bolt-python/tree/main/slack_bolt/context>
   - Accessed: 2026-05-13
   - Relevance: `BoltContext` extends `dict` (`base_context.py`); property getters for `say`/`respond`/`client` check `if "key" not in self` before constructing defaults (`async_context.py` lines 95-114). Middleware that writes `context["say"]` before the property fires installs the shielded version. `async_utils.py` line 52 calls `request.context.say` (the property), returning the middleware-set value. Grounds the mechanism behind `shield_listener_callables`.

10. Slack Web API — Rate Limits
   - URL: <https://docs.slack.dev/apis/web-api/rate-limits/>
   - Accessed: 2026-05-08
   - Relevance: 429 with `Retry-After`; shared per-channel quota for both Web API and `response_url` webhook paths.

11. Slack Python SDK — `slack_sdk.models` (Block Kit and view classes)
    - URL: <https://docs.slack.dev/tools/python-slack-sdk/reference/models/blocks/>
    - Accessed: 2026-05-13
    - Relevance: Typed classes with PEP 604 annotations and `@JsonValidator` validation; `AsyncWebClient` auto-converts instances at the boundary. Grounds the model-class import carve-out.

12. Pydantic — Models
    - URL: <https://docs.pydantic.dev/latest/concepts/models/>
    - Accessed: 2026-05-08
    - Relevance: Slash command argument schemas as `BaseModel` subclasses; validated at the parsing boundary.

## Change Log

- 2026-05-08: Created as placeholder.
- 2026-05-08: Clarified Socket-Mode-default rationale.
- 2026-05-08: Finalized with SDK selection, Socket Mode default, five hookspecs with `SlackHandlerRegistry`, authentication, Pydantic argument parser, ack discipline, formatter, i18n, `SLACK_ENABLED=false` blocking.
- 2026-05-12: Replaced five hookspecs and `SlackHandlerRegistry` with single `register_slack_listeners(app: SlackApp)`. Removed `routing.py`.
- 2026-05-12: Added Resilience wiring subsection — three SDK-native retry handlers; `SlackShield` executor applies per-call budget and Web API error-code classification.
- 2026-05-13: Partial amendment — added webhook-path classification table; explicit `ack()` exclusion; `slack_sdk.models.*` carve-out; handler snippet with shape α/β callables. (Superseded by 2026-05-13 rewrite below.)
- 2026-05-13: **Full rewrite.** Grounded in `BoltContext` injection research confirming that `say`/`respond`/`client` cannot be overridden by middleware (`all_available_args` guard). Established `inject_slack_service` middleware pattern injecting `SlackService` as `context["slack"]`; handlers declare `slack: SlackService` by parameter name. `say` is prohibited in handlers (bypasses shield). `respond` is a first-class `SlackService` method wrapping `AsyncWebhookClient`, accepting `response_url` from `context.response_url`. `client` is blocked by convention and lint. `BoltContext` documented as the carrier of per-request metadata. `SlackService` Protocol surface expanded. Shield mechanics delegated to [client-sdk-shield-pattern.md](client-sdk-shield-pattern.md). (Superseded by same-day amendment below.)

- 2026-05-13: **Amended — corrected `say`/`respond`/`client` override behaviour.** Deep source inspection of `BoltContext` (`base_context.py`, `async_context.py` lines 95-114, `async_utils.py` line 52) confirmed that `BoltContext` is a plain `dict` subclass; property getters check `if "key" not in self`; middleware writing `context["say"]` before the property fires installs the shielded value which `async_utils.py` line 52 then reads. **The previous rewrite's claim that `say`/`respond`/`client` cannot be overridden was wrong.** Replaced `inject_slack_service` with `shield_listener_callables` middleware that replaces `say` → `ShieldedSay`, `respond` → `ShieldedRespond`, `client` → `SlackService`. Handlers now use native Bolt parameter names (`say`, `respond`, `client`) with shield wrapping invisible — same call syntax as unshielded Bolt. Documented Workflow Step / AI/Assistant callables (`complete`, `fail`, `set_status`, etc.) as following the same override pattern, not yet in scope. Added Bolt listener arguments reference. Removed `say`-prohibition rule; removed `respond`-as-SlackService-only rule.

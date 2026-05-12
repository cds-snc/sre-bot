---
title: "Slack Transport"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [api, architecture, plugins]
constrained_by: [layered-architecture.md, dependency-injection.md, configuration-ownership.md, application-lifecycle.md, plugin-registration-discovery.md, feature-package-structure.md, cross-channel-correlation.md, multi-transport-architecture.md, feature-handler-standard.md, operation-result-pattern.md, client-module-placement.md, type-boundaries.md, infrastructure-i18n.md, package-management.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Slack Transport

## Context and Problem Statement

Slack is a first-class platform the application integrates with. Slack delivers inbound interactions through several native categories — slash commands, events (channel messages, app mentions, member-joined, etc.), block actions (Block Kit interactive components), shortcuts (global and message), and view interactions (modal submissions and closures). The application speaks back to Slack through Slack's Web API (`chat.postMessage`, `views.open`, `views.update`, `users.lookupByEmail`, and others) and must select among Slack's two distinct delivery modes — HTTP Events API (Slack POSTs to a public URL) or Socket Mode (the application opens an outbound persistent WebSocket and receives events on it).

This record fills in the per-platform slots that the multi-transport pattern leaves open for Slack:

1. **SDK selection.** Which Python SDK does the application use to talk to Slack?
2. **Delivery mode default.** HTTP Events API or Socket Mode? When does each apply?
3. **Module placement.** Where does the raw vendor SDK access live, and where does the composed `SlackService` live, given the corpus's `app/integrations/<vendor>/` and `app/infrastructure/<service>/` rules?
4. **Hookspec catalogue.** What categories of Slack interactions can features register handlers for, and what does each hookspec receive?
5. **Inbound dispatch and verification.** Where does signing-secret verification fire (HTTP mode only) and where does the inbound adapter dispatch into pluggy hookspecs?
6. **`SlackService` Protocol surface.** What outbound operations does the infrastructure service expose for features and other infrastructure to consume?
7. **Authentication and credentials.** Which tokens and secrets does Slack require, where do they live in settings, and how do they reach the SDK without contaminating feature code?
8. **Slash command argument parsing.** Slack delivers a slash command's arguments as one text blob; the application extracts structured arguments from it.
9. **Help text and i18n.** Slack-rendered help messages and localized outbound text.
10. **Settings-driven enablement.** When `SLACK_ENABLED=false`, the platform is not loaded at all; feature plugins targeting Slack are blocked at the plugin manager.

**Constraints:**

- The application's FastAPI surface already exposes public endpoints when its features are enabled (HTTP API routes, webhook receivers for other integrations, etc.). The choice between Slack's two delivery modes is therefore *not* about whether the application has any public surface; it is about whether the **Slack channel specifically** requires a deployment-known public URL that Slack must be configured against. Socket Mode initiates the connection outbound from the application using an app-level token, so Slack does not need to know any deployment URL; HTTP Events mode requires Slack to be configured with a public URL per deployment and adds per-event signing-secret verification at that endpoint.
- Feature code (under `app/packages/<feature>/`) does not import vendor SDK types per the import-governance rules. The Slack platform's runtime types (Bolt App, Web API client, Bolt request objects) are exposed through the `app/infrastructure/slack/` module's Protocol surface — feature code imports from there.
- Vendor credentials live in `BaseSettings` in the infrastructure layer per the configuration-ownership rules; vendor clients receive scalar credentials via constructor, never the `BaseSettings` instance.
- Top-level `app/integrations/slack/` is the home for raw, authenticated vendor SDK access (per the client-module-placement decision). The composed service lives in `app/infrastructure/slack/`. The legacy nested layout (`app/infrastructure/clients/slack/`) is not used; it predates the corpus's current rules.
- The application uses Pluggy for plugin discovery and dispatch. Each platform exposes its own platform-shaped hookspec catalogue per the multi-transport pattern; this record names Slack's catalogue.
- HTTP Events mode requires verification of every inbound POST against the signing secret per Slack's documented HMAC-SHA256 scheme with a 5-minute replay-protection window. Socket Mode does not require per-event verification — the WebSocket is pre-authenticated.

**Non-goals:**

- This record does not specify per-feature Slack handler implementations or per-feature command schemas. Each feature owns its handlers per the feature-package-structure and feature-handler-standard rules; the hookspec catalogue this record establishes is what features register against.
- This record does not generalize to other platforms. Teams' integration is owned by `transport-teams.md`. Even where the patterns rhyme (a tokens, an SDK, a hookspec catalogue), the specifics are platform-shaped and never shared via a unifying abstraction.
- This record does not redefine the `OperationResult` envelope, the per-handler discipline, or the correlation-binding rules — those are inputs from the upstream records this one is constrained by.
- This record does not specify the i18n library; per the infrastructure-i18n record, that selection is pending. The integration-pattern rule (Slack outbound formatters consume the I18nService Protocol) is established here; the library swap will be a configuration-only change once finalized.
- This record does not define migration mechanics for moving the existing legacy implementation (`app/integrations/slack/`, `app/infrastructure/platforms/`) to the target shape. It pins the target; the migration is a code task that follows acceptance.

## Considered Options

**Option 1 — Slack Bolt for Python (canonical SDK), Socket Mode default, HTTP Events supported.** The application uses Slack's first-party Python framework. Socket Mode is the default for the Slack channel because it requires no per-deployment Slack URL configuration and behaves identically in local development as in production; HTTP Events is supported via a settings flag for deployments that prefer it (e.g., when a public Slack-events URL is available, stable, and operationally convenient). Hookspecs are platform-shaped per Slack's native interaction categories.

**Option 2 — Slack Bolt for Python, HTTP Events default.** Same SDK; HTTP Events as the default mode. Requires Slack to be configured with a deployment-specific public URL that accepts the Slack-events route; per-event signing-secret verification fires at that endpoint. Adds per-deployment configuration step and per-environment Slack-app URL maintenance.

**Option 3 — Lower-level `slack_sdk` (no Bolt framework).** Use only the official `slack-sdk` package for outbound Web API; build inbound dispatching from primitives (FastAPI route for HTTP Events, custom WebSocket client for Socket Mode). Maximum control; high reimplementation cost; loses Bolt's middleware and decorator ergonomics.

**Option 4 — Continue with `infrastructure/platforms/` unified-platform abstraction.** Keep the rejected unified-platform design (`PlatformProvider`, formatters under a base class, registry across platforms). Already rejected by the corpus.

## Decision Outcome

**Chosen: Option 1 — Slack Bolt for Python, Socket Mode default, HTTP Events supported.**

Slack Bolt for Python is Slack's first-party Python framework for building Slack apps; it provides the application initialization, decorator-based handler registration, middleware pipeline, and Socket Mode handler that the application would otherwise reimplement on top of `slack-sdk`. Socket Mode is the default for the Slack channel because (a) it does not require Slack to be configured with a deployment-specific URL — the application initiates the WebSocket outbound using its app-level token, so the same code runs unchanged across local development, staging, and production; (b) it removes per-environment Slack-app URL maintenance from the deployment workflow; (c) the inbound Slack channel does not need to be publicly addressable specifically for Slack, even though the application's other features may already expose public endpoints. HTTP Events mode is supported and selected via the `socket_mode=false` setting for deployments that have a stable, deployment-known public URL and prefer the synchronous request-response model.

### Module placement

| Concern | Path | Contents |
| --- | --- | --- |
| Raw vendor SDK access | `app/integrations/slack/` | Authenticated factories that construct Slack SDK objects (`AsyncApp` from `slack_bolt`, `AsyncWebClient` from `slack_sdk`, `AsyncSocketModeHandler` from `slack_bolt.adapter.socket_mode.async_handler`); a small signing-secret verification utility (HMAC-SHA256 per Slack's documented scheme); no settings, no business logic, no application-state. |
| Composed infrastructure service | `app/infrastructure/slack/` | The `SlackService` Protocol and concrete implementation; the inbound adapter (verification → correlation binding → pluggy dispatch); the connection lifecycle (Socket Mode start/stop or HTTP Events mount); the Slack-specific helpers — `parsing.py` (slash command argument parsing), `formatter.py` (`OperationResult` → Block Kit rendering), `help.py` (slash command help text), `lifecycle.py` (start/stop sequence), `settings.py` (`SlackSettings`), `models.py` (Slack-shaped value types), `providers.py` (DI providers), `__init__.py` (public surface; re-exports `SlackApp` type alias for `AsyncApp`). |

The `app/infrastructure/slack/` package re-exports the Slack-specific Protocol surface (`SlackService`, `SlackApp` type alias, `SlackInteractionContext` value types); feature code imports only from there. Feature code never imports from `app/integrations/slack/` (forbidden by the import contract) or from `slack_bolt.*` / `slack_sdk.*` directly.

`SlackApp` is a re-export alias for `slack_bolt.async_app.AsyncApp` declared in `app/infrastructure/slack/__init__.py`. Features receive it via the hookspec argument; they never import from `slack_bolt.*` in their own module imports. The import contract remains statically enforceable: only `app/integrations/slack/` and `app/infrastructure/slack/` may import from `slack_bolt.*`.

### Authentication and credentials

Three values authenticate the application against Slack. They are declared in `app/infrastructure/slack/settings.py` as fields of `SlackSettings(BaseSettings)`:

| Field | Slack designation | Purpose |
| --- | --- | --- |
| `bot_token` | `xoxb-…` | Bot token; identifies the application's Slack bot user; used for every Web API call (`chat.postMessage`, etc.). |
| `app_token` | `xapp-…` | App-level token; **Socket Mode only**; used to open the WebSocket via the `apps.connections.open` Web API method. Distinct from the bot token. |
| `signing_secret` | hex string | **HTTP Events mode only**; used to verify the HMAC-SHA256 signature on every inbound POST per Slack's verification scheme. |

Per the configuration-ownership rule, the credentials live in this `BaseSettings` subclass; the `app/infrastructure/slack/providers.py` module reads them and calls factories in `app/integrations/slack/` with **scalar** values. Vendor clients in `app/integrations/slack/` receive primitives (the token string, the secret string) — never a `BaseSettings` instance.

A fourth setting, `enabled` (boolean, default `false` for safety), gates the entire Slack platform. When `enabled=false`, the host applies `pm.set_blocked()` on every Slack-targeted feature plugin during the plugin-discovery phase per the plugin-registration-discovery rules, and the SlackService is not constructed.

A fifth setting, `socket_mode` (boolean, default `true` for production), selects the delivery mode. `socket_mode=true` means the SlackService starts the Socket Mode handler in the transport phase; `socket_mode=false` means the SlackService mounts an HTTP Events endpoint into the application's FastAPI app instead.

### Delivery mode and inbound dispatch

The two delivery modes share the same logical inbound-adapter phase (verification → correlation binding → dispatch into hookspecs) but differ in **physical layer**:

**Socket Mode (default).** The SlackService constructs a Bolt `AsyncApp` with the bot token; constructs an `AsyncSocketModeHandler` with the app token; starts the handler during the lifespan's transport phase. Slack delivers events on the pre-authenticated WebSocket — there is no signing-secret verification step (Slack documents this explicitly). The handler dispatches each delivered event to Bolt's middleware and decorator-registered handlers; the SlackService's inbound adapter wraps Bolt's dispatch so that each event opens a fresh correlation context (a new `request_id`) per the cross-channel-correlation rules. Up to 10 concurrent WebSocket connections are supported by Slack; the SlackService runs one connection per process, restarting the connection if disconnected.

**HTTP Events.** The SlackService constructs a Bolt `AsyncApp` and mounts its `SlackRequestHandler` onto the application's FastAPI app at a configured path (e.g., `/slack/events`). On each inbound POST: the inbound adapter (a FastAPI middleware or dependency on the mounted route) verifies the request against the signing secret using Slack's HMAC-SHA256 scheme with a 5-minute timestamp window; on failure, the request is rejected with `401`. Verified requests proceed through Bolt's dispatch pipeline; the inbound adapter opens a fresh correlation context as in Socket Mode.

### `SlackService` Protocol surface

`app/infrastructure/slack/__init__.py` exports a `SlackService` Protocol that names the outbound operations the application uses. The Protocol is the contract feature code consumes via dependency injection; the concrete implementation is hidden behind providers per the dependency-injection rules.

The Protocol surface is **shaped by the operations the application actually performs**, not by Slack's full Web API. Initial operations (extended as features need more):

- `post_message(channel: str, blocks: list[dict] | None = None, text: str | None = None, thread_ts: str | None = None) -> SlackMessageReference` — `chat.postMessage`.
- `update_message(channel: str, ts: str, blocks: list[dict] | None = None, text: str | None = None) -> None` — `chat.update`.
- `open_view(trigger_id: str, view: dict) -> SlackViewReference` — `views.open`.
- `update_view(view_id: str | None = None, hash: str | None = None, view: dict) -> SlackViewReference` — `views.update`.
- `push_view(trigger_id: str, view: dict) -> SlackViewReference` — `views.push`.
- `lookup_user_by_email(email: str) -> SlackUser | None` — `users.lookupByEmail`.

The concrete implementation in `app/infrastructure/slack/service.py` wraps Slack's `AsyncWebClient` from `app/integrations/slack/`, translates exceptions per the client-adapter-responsibilities rules into `OperationResult` envelopes where the operation can fail recoverably, and returns plain value types (`SlackMessageReference`, `SlackViewReference`, etc.) for typed outputs.

### Hookspec catalogue

The Slack platform contributes a single hookspec to the host's plugin namespace:

```python
@hookspec
async def register_slack_listeners(app: SlackApp) -> None:
    """Register all Slack listeners for this feature against the Bolt AsyncApp."""
```

`SlackApp` is the `AsyncApp` re-export from `app.infrastructure.slack`. The hookspec receives the live `AsyncApp` instance; features call any of Bolt's native listener-registration methods directly against it:

```python
# app/packages/<feature>/__init__.py
@hookimpl
async def register_slack_listeners(app: SlackApp) -> None:
    app.command("/example")(commands.handle_example)
    app.event("app_mention")(events.handle_mention)
    app.action("approve_button")(actions.handle_approve)
    app.view("my_modal")(views.handle_submit)
    app.message(":wave:")(events.handle_wave)
    app.options("priority_menu")(commands.handle_options)
```

This gives features access to the full `AsyncApp` listener surface — `command`, `event`, `message`, `action`, `block_action`, `shortcut`, `global_shortcut`, `message_shortcut`, `view`, `view_submission`, `view_closed`, `options`, `function`, `assistant`, `middleware`, `error` — without requiring a new hookspec when Bolt adds a new listener type. Feature plugins implement only this hookspec for all Slack listener registration; unused listener types produce no calls.

The hookspec is added to the host's central hookspec module per the plugin-registration-discovery rules. `app/infrastructure/slack/__init__.py` may re-export `TYPE_CHECKING`-guarded type aliases (`SlackCommandPayload`, `SlackBlockActionPayload`, etc.) so that handlers that want type annotations import them from `app.infrastructure.slack`, not from `slack_bolt`.

### Slash command argument parsing

Slack delivers a slash command's arguments as a single text blob (the part after `/command`). The application provides a Pydantic-model-driven argument parser at `app/infrastructure/slack/parsing.py`:

- A feature declares its command's argument schema as a Pydantic `BaseModel` (per the type-boundaries rules — `BaseModel` is the trust-boundary type).
- The parser performs quote-aware tokenization, supports flags (`--managed`), options with values (`--role OWNER`), positional arguments, multi-value options (`--role OWNER,MEMBER`), required/optional validation, and default value substitution.
- The parser surfaces parse failures as a typed exception inside the SlackService boundary; the SlackService maps the parse failure to an `OperationResult` of `PERMANENT_ERROR` with a feature-displayable message (rendered via the formatter).
- Help text for a command is derived from its argument schema (the parser generates a usage string from the Pydantic model's fields).

The parser itself is platform-shared infrastructure (one parser for all features); the argument schemas are feature-defined.

### Help text rendering

`app/infrastructure/slack/help.py` renders slash command help into Block Kit format. Help is derived from each command's Pydantic argument schema and may be augmented by feature-supplied descriptions. The user-facing help text is localized via the I18nService (see below).

### `OperationResult` rendering and the rendering helper

The Slack-specific rendering helper translates `OperationResult` envelopes into Slack outbound shapes (Block Kit messages, modal updates) per the feature-handler-standard's slot-5 rule. The helper:

- For `SUCCESS`, renders the payload into a Block Kit message (success blocks defined per feature; defaults provided for common shapes — confirmation, list rendering, etc.).
- For `NOT_FOUND` / `UNAUTHORIZED` / `PERMANENT_ERROR`, renders an error block with the `error_code`, the `message`, and the `request_id` (so users can quote it to operators).
- For `TRANSIENT_ERROR`, renders a "try again later" block; surfaces `retry_after` if useful (Slack does not have an `Retry-After` header equivalent, so the value is informational only).

The helper lives at `app/infrastructure/slack/formatter.py` and is the only location that constructs Block Kit JSON from `OperationResult`. Feature handlers call the helper rather than constructing Block Kit inline.

### 3-second acknowledgement discipline

Slack requires interactive payloads (slash commands, block actions, view submissions, shortcuts) to be acknowledged within **3 seconds**. The pattern:

- A handler that can complete its work in under 3 seconds calls `ack()` after the work is done, with the result body.
- A handler whose work cannot complete in 3 seconds calls `ack()` **early** (typically with no body or with an interim message), and continues the work asynchronously, sending the result via `chat.postMessage` or `views.update` once the service returns.

The `ack()` discipline is owned by feature handlers per the feature-handler-standard rules; this record establishes that Slack's 3-second deadline applies, names the early-ack pattern, and notes that long-running work that exceeds Bolt's `response_url` 30-minute window must be published via the standard `chat.postMessage` rather than the response URL.

`trigger_id` values (used to open modals via `views.open`) expire in 3 seconds and are single-use. Handlers that need to open a modal in response to a user action must do so before the trigger expires.

### Internationalization integration

Slack outbound text — formatter-rendered messages, help text, error messages — is localized through the I18nService Protocol exposed by the infrastructure-i18n record. The Slack formatter and help renderer accept a `Locale` parameter (resolved per-request from Slack's user-language hints) and call the I18nService for translations.

The current custom translation utility under `app/infrastructure/i18n/` is to be deprecated per the infrastructure-i18n record. Slack's integration pattern is unchanged by that swap — the formatter consumes the same `I18nService` Protocol regardless of which library backs it.

### Plugin discovery interaction

When `SlackSettings.enabled=false`, no Slack feature is loaded:

- The SlackService is not constructed (its provider is conditional on `enabled`).
- The host applies `pm.set_blocked("<feature>")` on every feature whose plugin's hookspecs are Slack-only, before `load_setuptools_entrypoints()` runs in the plugin-discovery phase. Features that target multiple platforms continue to load (their non-Slack hookspecs run; their Slack hookspecs are no-ops because no Slack registration provider is constructed to receive them).

## Consequences

**Positive:**

- The Slack integration uses the canonical Bolt SDK; the application's plumbing is thin and follows Bolt's documented patterns. Future Bolt updates can be adopted without reimplementing inbound dispatch.
- Socket Mode default removes the public-endpoint requirement; production deployments do not need a public URL or its security infrastructure.
- The two delivery modes share one inbound-adapter phase; switching modes (e.g., for a workspace that requires HTTP Events) is a configuration change, not a code change.
- The `SlackService` Protocol surface is shaped by the operations the application performs — small, stable, and grow-by-need. Features consume the Protocol; concrete vendor types stay out of feature code.
- The single `register_slack_listeners` hookspec gives features direct access to Bolt's full `AsyncApp` listener surface. Adding a new interaction type (e.g., `assistant`, `function`, `options`) requires no ADR change and no new hookspec — features call whichever `AsyncApp` method they need.
- `SLACK_ENABLED=false` produces a genuinely-absent platform: no SlackService, no listening Socket Mode handler, no Slack-targeted feature plugins. Useful for environments that don't want or have Slack credentials.
- The slash command argument parser plus Pydantic schemas give feature authors typed, validated command arguments without each feature reimplementing tokenization or validation.

**Tradeoffs accepted:**

- The application takes a hard dependency on Bolt for Python. The dependency is well-supported (Slack's first-party SDK) and the abstraction below it (Slack's Web API) is stable. A future swap to a different SDK would be a substantial migration; the cost is acceptable given Bolt's maturity.
- Socket Mode's pre-authenticated WebSocket means the application does not see signing-secret verification on every event. The mode is intentionally trusted; the WebSocket connection itself is the verified channel. HTTP Events mode reinstates the per-event verification.
- Features receive the live `AsyncApp` instance via the hookspec argument. The import contract (no `slack_bolt.*` imports in feature modules) is upheld by passing the app at runtime, not by a wrapping Protocol. The re-export of `SlackApp` from `app.infrastructure.slack` is the single allowed import point; the statically-enforceable rule is unchanged.
- Slack-specific value types (`SlackMessageReference`, `SlackViewReference`, etc.) and the parser's argument schemas are project code that must be maintained; not all of them are exact mirrors of Slack's API shapes.

**Risks:**

- Slack's API or Bolt's framework changes in a way that requires SlackService surface changes. Mitigation: the Protocol surface is defined by what the application uses, not by Bolt's full API; non-breaking SDK changes are absorbed by the `app/integrations/slack/` factory layer; breaking changes are deliberate updates to this record's Protocol.
- A feature handler imports from `slack_bolt.*` directly to access a runtime type. The vendor-import contract should catch this at lint time; if it does not, code review does. Mitigation: the `app/infrastructure/slack/` re-exports cover the type-annotation cases that tempt the bypass.
- The legacy `app/infrastructure/platforms/` and `app/integrations/slack/` code remains until the migration is complete. Mitigation: migration is a code task that follows acceptance; the new shape this record establishes is the target; the legacy code is not blessed by the corpus and is not extended.
- Socket Mode's connection drops periodically (Slack documents a ~10-second pre-disconnect warning). The SlackService must handle reconnection. Mitigation: Bolt's `AsyncSocketModeHandler` handles reconnect by default; the lifecycle module monitors connection state and logs reconnects.

## Confirmation

Compliance is verified by:

- **Repository structure.** `app/integrations/slack/` exists with raw Bolt/Web-API factory code only; `app/infrastructure/slack/` exists with `service.py`, `lifecycle.py`, `routing.py`, `parsing.py`, `formatter.py`, `help.py`, `models.py`, `settings.py`, `providers.py`, and `__init__.py`. `app/infrastructure/platforms/` is being deprecated (or has been removed); `app/integrations/slack/` is being deprecated (or has been removed). The legacy `app/infrastructure/clients/slack/` nesting is not reintroduced.
- **Import contract.** `import-linter` (or the equivalent rule) forbids feature-code imports from `slack_bolt.*`, `slack_sdk.*`, and `app.clients.slack.*`. Feature code imports the `SlackService` Protocol and `SlackApp` type alias from `app.infrastructure.slack` only. Only `app/integrations/slack/` and `app/infrastructure/slack/` may import from `slack_bolt.*`.
- **Code review.** A PR adding a Slack handler in a feature is reviewed against (1) the feature-handler-standard's five-step shape, (2) the hookspec (`register_slack_listeners` receiving `SlackApp`; listeners registered via native `AsyncApp` methods), (3) the `ack()` discipline (early-ack for slow handlers; in-time-ack for fast handlers). PRs that import from `slack_bolt.*` directly are rejected.
- **Settings.** `SlackSettings` defines `bot_token`, `app_token`, `signing_secret`, `enabled`, `socket_mode`. The settings are loaded at boot per the configuration-ownership rules; missing values when `enabled=true` cause fail-fast at the configuration phase.
- **Tests.** A boot test asserts the SlackService starts and stops cleanly with `enabled=true` and is absent with `enabled=false`. A handler test asserts the inbound-adapter phase opens a correlation context per delivered event. A formatter test asserts the helper renders each `OperationStatus` to a Block Kit shape per this record's mapping.

## Source References

1. Slack — Bolt for Python (Official Documentation)
   - URL: <https://docs.slack.dev/tools/bolt-python/>
   - Accessed: 2026-05-08
   - Relevance: Documents Bolt for Python as the framework for building Slack apps "with the latest Slack platform features" and names the canonical decorator-based handler registration surface (`@app.command`, `@app.event`, `@app.action`, `@app.view`, `@app.shortcut`). Grounds the SDK selection and the hookspec catalogue's category names.

2. Slack — Comparing HTTP Events API and Socket Mode
   - URL: <https://docs.slack.dev/apis/events-api/comparing-http-socket-mode>
   - Accessed: 2026-05-08
   - Relevance: Documents the two delivery modes, the rule that Socket Mode "allows your app to use the Events API and interactive features without exposing a public HTTP Request URL," and the recommendation that Socket Mode is preferred for environments where exposing a public endpoint is not viable. Grounds the Socket Mode default for production.

3. Slack — Using Socket Mode
   - URL: <https://docs.slack.dev/apis/events-api/using-socket-mode>
   - Accessed: 2026-05-08
   - Relevance: Documents the WebSocket-based event delivery, the app-level token (`xapp-`) and its purpose (distinct from the bot token), the `apps.connections.open` Web API method, the up-to-10-concurrent-connections rule, and the "no need to verify or validate inbound events, because you're receiving the events over a pre-authenticated WebSocket" guarantee. Grounds the no-verification-in-Socket-Mode rule and the `app_token` settings field.

4. Slack — Verifying Requests from Slack
   - URL: <https://docs.slack.dev/authentication/verifying-requests-from-slack>
   - Accessed: 2026-05-08
   - Relevance: Documents the HMAC-SHA256 signing-secret verification scheme used in HTTP Events mode: signature computation (`v0:<timestamp>:<body>` hashed with the signing secret, hex-encoded, prefixed `v0=`), `X-Slack-Request-Timestamp` and `X-Slack-Signature` headers, and the 5-minute replay-protection window. Grounds the HTTP-mode verification step and the `signing_secret` settings field.

5. Slack — Handling User Interaction
   - URL: <https://docs.slack.dev/interactivity/handling-user-interaction>
   - Accessed: 2026-05-08
   - Relevance: Documents the 3-second acknowledgement deadline ("This must be sent within 3 seconds of receiving the payload. If your app doesn't do that, the Slack user who interacted with the app will see an error message"), the interactive-payload categories (`block_actions`, `shortcut`, `message_actions`, `view_submission`, `view_closed`), and the `trigger_id`'s 3-second single-use expiry. Grounds the ack discipline rule and the hookspec catalogue's view-submission/closure categories.

6. Pydantic — Models
   - URL: <https://docs.pydantic.dev/latest/concepts/models/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that `pydantic.BaseModel` is the canonical Python construct for typed, validated data structures with field-level constraints, used at trust boundaries. Grounds the rule that slash command argument schemas are Pydantic `BaseModel` subclasses, validated at the parsing boundary.

## Change Log

- 2026-05-08: Created as placeholder.
- 2026-05-08: Clarified the Socket-Mode-default rationale. The earlier wording implied the application has no public HTTP endpoints, which is incorrect — the application's FastAPI surface already exposes public endpoints when its features are enabled. The correct rationale: Socket Mode does not require Slack to be configured with a deployment-specific public URL (the application initiates the WebSocket outbound via the app-level token), removes per-environment Slack-app URL maintenance, and behaves identically in local development as in production. The decision is unchanged — Socket Mode default; HTTP Events supported via the `socket_mode=false` setting; mode is settings-managed.
- 2026-05-08: Finalized. Selects Slack Bolt for Python as the SDK; pins Socket Mode as the production default with HTTP Events supported via a settings flag; pins module placement as `app/clients/slack/` (raw Bolt/Web-API factories, signing-secret utility) plus `app/infrastructure/slack/` (composed `SlackService` Protocol with a small, application-shaped surface — `post_message`, `update_message`, `open_view`, `update_view`, `push_view`, `lookup_user_by_email` — extended as features need more); names the five Slack hookspecs (`register_slack_command`, `register_slack_event`, `register_slack_action`, `register_slack_shortcut`, `register_slack_view`), each receiving a `SlackHandlerRegistry` Protocol that wraps Bolt's decorator surface so feature code never imports from `slack_bolt.*`. Pins authentication via `bot_token` (xoxb-), `app_token` (xapp-, Socket Mode only), and `signing_secret` (HTTP Events only) declared in `SlackSettings(BaseSettings)` in the infrastructure layer with scalar injection to clients per the configuration-ownership rules. Pins the slash command argument parser as Pydantic-driven, living at `app/infrastructure/slack/parsing.py`, with each feature declaring its command's argument schema as a `BaseModel`. Establishes that `SlackSettings.enabled=false` blocks every Slack-targeted feature plugin via `pm.set_blocked()` before `load_setuptools_entrypoints()` and prevents `SlackService` construction. Establishes the 3-second `ack()` discipline (early-ack for slow handlers), the `trigger_id` 3-second single-use expiry, and the rule that long-running work past the 30-minute `response_url` window must be sent via standard Web API methods. Pins outbound `OperationResult` rendering at `app/infrastructure/slack/formatter.py` as the only construction site for Block Kit JSON in response to feature operations. Slack-outbound text is localized through the I18nService Protocol per the infrastructure-i18n record; the current custom translation utilities are flagged as pending deprecation. Notes that the legacy `app/infrastructure/platforms/` and `app/integrations/slack/` code is being deprecated; the `feat/intra-slackbot-service` branch's infrastructure-side structure is a starting point but its `app/infrastructure/clients/slack/` nesting must move to top-level `app/clients/slack/` per the client-module-placement decision.
- 2026-05-12: Revised hookspec catalogue. Replaced the five category-specific hookspecs (`register_slack_command`, `register_slack_event`, `register_slack_action`, `register_slack_shortcut`, `register_slack_view`) and the `SlackHandlerRegistry` wrapper Protocol with a single hookspec `register_slack_listeners(app: SlackApp)` that passes the live `AsyncApp` instance directly. Features call whichever native `AsyncApp` listener methods they need (`command`, `event`, `message`, `action`, `shortcut`, `view`, `options`, `function`, `assistant`, etc.) without requiring a new hookspec or ADR change per Bolt capability. `SlackApp` is a re-export alias for `AsyncApp` declared in `app/infrastructure/slack/__init__.py`; the import contract (no `slack_bolt.*` in feature modules) is unchanged. Removed `routing.py` from the infrastructure module list; `SlackHandlerRegistry` is retired.

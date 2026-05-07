---
adr_id: ADR-0067
title: "Slack Transport Integration Decision"
status: Accepted
decision_type: Integration Decision
tier: Tier-4
primary_domain: Transport and API
secondary_domains:
  - Runtime and Lifecycle
  - Package and Plugin Architecture
date_created: 2026-04-30
last_updated: 2026-05-06
  last_reviewed: 2026-05-05
  next_review_due: 2026-09-01
owners:
  - SRE Team
constrained_by:
  - ADR-0044
  - ADR-0046
  - ADR-0057
  - ADR-0058
  - ADR-0059
  - ADR-0065
  - ADR-0078
impacts: []
supersedes:
  - ADR-0014
superseded_by: []
related_records:
  - ADR-0055
  - ADR-0056
  - ADR-0061
  - ADR-0064
  - ADR-0080
related_packages:
  - app/infrastructure/platforms/providers
  - app/infrastructure/configuration/infrastructure
review_state: current
---
# Slack Transport Integration Decision

## Context

- Problem statement: The application integrates with Slack via the Bolt Python SDK using Socket Mode (WebSocket transport). Legacy ADR-0014 established the daemon-thread Socket Mode pattern but predates the canonical lifecycle model (ADR-0046), graceful shutdown contract (ADR-0057), platform services architecture (ADR-0078), and feature interaction boundaries (ADR-0059). The current implementation works but lacks explicit lifecycle phase alignment, shutdown budget compliance, and codified feature registration semantics. Long-term, Slack transport must support both Socket Mode and HTTP Events API mode via configuration without feature-level code changes.
- Business/operational drivers: Slack is the primary real-time interaction transport for SRE operations (incident management, access requests, operational commands). Reliable startup, deterministic shutdown, and structured observability for the Slack connection are operational necessities.
- Constraints:
  - Must operate within ADR-0046 sequential phase model (Socket Mode connects in Transport phase after all feature hookimpls register handlers).
  - Must comply with ADR-0057 shutdown timeout budget (≤5 s for Transport phase).
  - Must follow ADR-0078 concrete `SlackPlatformProvider` pattern (no abstract Protocol).
  - Must use ADR-0059 pluggy hookspec registration for feature command/action/view registration.
  - Socket Mode requires `SLACK_APP_TOKEN` (xapp-…) and `SLACK_BOT_TOKEN` (xoxb-…).
  - Application runs in ECS with 30 s stop timeout (ADR-0057 S2).
- Non-goals:
  - This record does not redesign the Block Kit formatting or presenter layer.
  - This record does not govern legacy module migration (frozen zones thaw under Phase 3 Tier-4 ADRs).
  - This record does not define feature-specific Slack command semantics (those belong in per-feature Tier-4 ADRs).
  - This record does not require immediate migration to HTTP Events API mode. Socket Mode remains the current default transport; long-term support for both transport modes is tracked through settings-driven provider behavior.
  - This record does not govern SRE Bot webhooks (`POST /hook/{webhook_id}`). Webhooks are a platform-agnostic ingress feature with their own DynamoDB registry, payload validation, and action routing. Today most webhook actions post to Slack channels, but the webhook subsystem is not coupled to Slack — it is an independent feature that consumes the Slack provider as one possible output channel. Webhook architecture belongs in a future Tier-4 ADR when `modules/webhooks` thaws (Wave 8).

## Decision

- Chosen approach: Codify `SlackPlatformProvider` as the single Slack integration surface, wrapping Slack Bolt Python SDK with Socket Mode as the current default and HTTP Events API as a planned alternate mode. Provider lifecycle aligns to ADR-0046 phases; shutdown complies with ADR-0057 budget; feature registration uses ADR-0059 hookspec injection.
- Why this approach:
  - Socket Mode eliminates public HTTPS endpoint requirements for Slack event delivery, simplifying network security in private VPC deployments.
  - Bolt SDK provides a well-maintained, officially supported abstraction over Slack's WebSocket and Web API surfaces.
  - Concrete provider pattern (ADR-0078 S1) preserves Slack-native type signatures and avoids lossy abstraction.
  - Hookspec registration (ADR-0059 S3) decouples feature command ownership from infrastructure transport lifecycle.
- Principles established:
  - Slack SDK lifecycle is infrastructure-owned; feature packages consume capabilities, never construct or manage the transport connection.
  - Socket Mode connection is a Transport-phase resource with bounded startup and shutdown windows.
  - Any feature or subsystem running within the ASGI lifespan (ADR-0080 P3) that needs to send Slack messages (including webhooks, incident notifications, or background jobs) consumes the provider's message-sending API. The provider exposes capability; it does not own routing or dispatch logic. Infrastructure components deployed independently of the FastAPI process (e.g., Lambda alerting functions) that send Slack messages do so through their own Slack API integration and are not governed by this ADR.

## Alternatives Considered

1. **Slack Events API over HTTP (webhook-based ingress):**
   - Pros: Stateless; no persistent WebSocket connection to manage; scales horizontally without connection-per-task concerns.
   - Cons: Requires public HTTPS endpoint with Slack request signature verification; adds ALB/WAF exposure surface; challenge-response verification adds startup complexity.
   - Why not chosen: Private VPC deployment without public ingress is a hard constraint. Socket Mode satisfies this without additional infrastructure.

2. **Abstract `TransportProvider` Protocol wrapping Slack and Teams:**
   - Pros: Uniform transport interface for multi-platform features.
   - Cons: ADR-0078 S1 explicitly prohibits abstract Protocol for platform services — Slack Bolt's functional model (`ack()`, `say()`, command parameters) and Teams Bot Framework's class-based TurnContext model are fundamentally incompatible. Abstraction would be lossy.
   - Why not chosen: Violates ADR-0078 S1. Concrete per-platform providers are the canonical pattern.

3. **Feature-owned Socket Mode lifecycle (each feature manages its own connection):**
   - Pros: Maximum feature autonomy.
   - Cons: Violates ADR-0078 S4 (infrastructure ownership of platform services); multiplies WebSocket connections; makes shutdown coordination intractable.
   - Why not chosen: Violates foundational architecture. Single provider, single connection.

## Standards

### S1 — SlackPlatformProvider Lifecycle Phases

The `SlackPlatformProvider` lifecycle aligns to ADR-0046 sequential phases:

| ADR-0046 Phase | Slack Provider Action |
|---|---|
| Phase 1 — Configuration | `SlackPlatformSettings` loaded and validated. If `SLACK_ENABLED` is false or credentials missing, provider construction skipped entirely (ADR-0078 S2). |
| Phase 2 — Infrastructure | No Slack-specific action. |
| Phase 3 — Discovery/Registration | Provider instantiated. `initialize_app()` creates Bolt `App(token=BOT_TOKEN)` and prepares `SocketModeHandler(app, APP_TOKEN)`. Hookspec `register_slack_interactions(provider)` fired — features register commands, actions, views, and shortcuts. Registries frozen after phase completes (ADR-0046 I5). |
| Phase 4 — Feature Activation | No Slack-specific action. |
| Phase 5 — Transport | `start()` spawns daemon thread running `handler.connect()`. Connection established only after all feature handlers are registered. |
| Phase 6 — Background | No Slack-specific action. Background jobs that send Slack messages use the provider's `client` property; they do not manage the connection. |

**Rules:**

- R1: Socket Mode connection must not be established before phase 5. Feature hookimpls must complete registration in phase 3 before the transport connects.
- R2: If `SLACK_ENABLED` is false, no Slack objects are constructed. Hookspec `register_slack_interactions` does not fire. Features run HTTP-only.
- R3: If `SLACK_ENABLED` is true but credentials are invalid (missing `APP_TOKEN` or `BOT_TOKEN`), `initialize_app()` must return a failing `OperationResult` and startup must fail fast (ADR-0046 I3). Slack is not a degraded-start service.
- R4: Provider emits structured lifecycle log events at each phase transition: `slack_provider_settings_loaded`, `slack_provider_app_initialized`, `slack_provider_handlers_registered`, `slack_provider_transport_started`, `slack_provider_transport_connected` (ADR-0046 I6).

### S2 — Socket Mode Connection Management

The Socket Mode WebSocket connection is managed by a single daemon thread owned by `SlackPlatformProvider`.

**Rules:**

- R1: The daemon thread name must be `slack-socket-mode`. Thread must be created with `daemon=True`.
- R2: The thread runs `SocketModeHandler.connect()` (blocking call). The handler manages WebSocket reconnection internally (Bolt SDK built-in retry).
- R3: The `SocketModeHandler` and thread reference are stored in provider instance state (not directly in `app.state`). The provider itself is accessible via `app.state` through the `PlatformService`.
- R4: Only one Socket Mode connection exists per process. Slack supports up to 10 simultaneous connections per app-token for load balancing and graceful restarts, but this application uses a single connection per process for operational simplicity — shutdown coordination, message ordering predictability, and avoiding handler dispatch ambiguity across connections. The application runs multiple ECS tasks (`desired_count = 2`), so Slack distributes inbound events across the resulting connections automatically with no duplication. Horizontal scaling (increasing ECS task count, up to 10) is the preferred throughput strategy; multi-connection per process is not planned.
- R5: The provider must not install custom signal handlers. Signal handling is uvicorn's responsibility (ADR-0057 S1).

### S3 — Graceful Shutdown Contract

Shutdown follows ADR-0057 reverse-phase ordering. The Transport phase shutdown budget is ≤5 s.

**Rules:**

- R1: `stop()` calls `SocketModeHandler.close()` to initiate WebSocket graceful close, then joins the daemon thread with a 5 s timeout.
- R2: If the thread does not terminate within the timeout, `stop()` logs a warning (`slack_socket_mode_shutdown_timeout`) and returns. The daemon thread will be terminated when the process exits.
- R3: `stop()` must be idempotent — calling it when the provider was never started or was already stopped must be safe (no-op with debug log).
- R4: `stop()` must not raise exceptions. Errors during shutdown are logged (`slack_shutdown_error`) and swallowed (ADR-0057 S3).
- R5: Shutdown observability events: `slack_shutdown_initiated` → `slack_socket_mode_close_requested` → `slack_socket_mode_thread_joined` (or `slack_socket_mode_shutdown_timeout`) → `slack_shutdown_complete(duration_seconds=X)`.
- R6: In-flight Slack interactions (commands/actions/views currently being processed by feature handlers) are allowed to complete during the request-draining window (ADR-0057 Phase A, ≤10 s) before Transport phase shutdown begins. The provider does not forcibly cancel in-flight handlers.

### S4 — Feature Registration via Hookspec

Feature packages register Slack capabilities through the pluggy hookspec defined in ADR-0059 S3.

**Rules:**

- R1: The hookspec signature is `register_slack_interactions(provider: SlackPlatformProvider) -> None`. The parameter type is the concrete class, not a Protocol (ADR-0078 S1).
- R2: Feature hookimpls call provider registration methods to declare commands, actions, view submissions, and shortcuts. The provider translates these into Bolt SDK handler registrations.
- R3: Registration methods on `SlackPlatformProvider` must validate inputs eagerly (during phase 3). Invalid registrations (duplicate command names, missing handler callables) raise immediately — they are startup-fatal per ADR-0046 I3.
- R4: After phase 3 completes, the command/action/view registry is frozen (ADR-0046 I5). Dynamic registration during request handling is prohibited.
- R5: Features must not import or reference `SocketModeHandler`, `slack_bolt.App`, or any Bolt SDK type directly. All Slack interaction is mediated through `SlackPlatformProvider` methods.

### S5 — Slack Settings Schema

Slack configuration follows ADR-0055 dissolution model with a partitioned `SlackPlatformSettings` class.

**Rules:**

- R1: `SlackPlatformSettings` is a Pydantic `BaseModel` (I/O boundary — environment variables are untrusted input per ADR-0065 P3).
- R2: Required fields when `SLACK_ENABLED` is true: `SLACK_BOT_TOKEN` (xoxb-…), `SLACK_APP_TOKEN` (xapp-…). Optional: `SLACK_SIGNING_SECRET` (only needed if HTTP webhook verification is added in future).
- R3: Validation must reject startup if `SLACK_ENABLED` is true but required tokens are missing or malformed (cross-field validation via Pydantic `model_validator`).
- R4: Settings are consumed by `SlackPlatformProvider` constructor as the narrowest slice needed (ADR-0055 pattern). The provider does not receive root settings.
- R5: `SLACK_SOCKET_MODE` is the transport-mode selector and defaults to `True`. When true, the provider uses Socket Mode (`SocketModeHandler` + daemon thread). When false, the provider runs in HTTP Events API mode with request-signature verification using `SLACK_SIGNING_SECRET`. Feature handlers remain unchanged across transport modes.
- R6: New dual-mode transport behavior (Socket + HTTP) must be implemented in the upcoming SlackPlatform service under `app/infrastructure/slack/`, not by adding new transport logic to deprecated `app/infrastructure/platforms/` packages.

### S6 — Outbound Message Delivery

Features send Slack messages through `SlackPlatformProvider` methods, not through direct SDK calls.

**Rules:**

- R1: The provider exposes `client` property returning the Bolt SDK `WebClient`. Features and infrastructure notification channels use this client for `chat_postMessage`, `chat_update`, and similar Web API calls.
- R2: The provider exposes message-sending capability only. Routing decisions (which channel, which message format, whether to send at all) are the calling feature's responsibility per ADR-0059 S6. The provider has no knowledge of callers' domain logic.
- R3: Outbound message failures must not propagate as unhandled exceptions to callers. The provider's `client` may raise `SlackApiError`; callers must handle this within their own error boundaries.
- R4: Legacy `SlackClientManager` (in `app/integrations/slack/client.py`) is superseded by `SlackPlatformProvider.client`. New code must not import from `app/integrations/slack/`. Migration of existing consumers occurs during Phase 3 module thaw, not in this decision's scope.

### S7 — Observability Contract

All Slack transport events use structured logging via `structlog` (ADR-0054).

**Rules:**

- R1: Log events use the `slack_` prefix for namespace consistency.
- R2: Mandatory startup events: `slack_provider_settings_loaded`, `slack_provider_app_initialized`, `slack_provider_handlers_registered(command_count=N)`, `slack_provider_transport_started`, `slack_provider_transport_connected`.
- R3: Mandatory shutdown events: `slack_shutdown_initiated`, `slack_socket_mode_close_requested`, `slack_socket_mode_thread_joined(duration_seconds=X)` or `slack_socket_mode_shutdown_timeout(budget_seconds=5)`, `slack_shutdown_complete(duration_seconds=X)`.
- R4: Runtime events: `slack_command_received(command=X)`, `slack_action_received(action_id=X)`, `slack_view_submitted(callback_id=X)`. These are emitted by the provider's middleware layer, not by feature handlers.
- R5: No sensitive data in log events. Token values, user PII, and message content must never appear in logs. Log command names, action IDs, and callback IDs only.

### S8 — Slack User Identity Resolution

> **Added 2026-05-05** — Governs resolution of a Slack `user_id` to a canonical `User`. Introduced to close the gap identified during the ADR-0061 amendment: `IdentityService` is narrowed to JWT/HTTP auth only; Slack-specific user resolution is a Category C responsibility of `SlackPlatformProvider`.

Slack commands and interactions carry a `user_id` in the Bolt event payload, delivered over the Socket Mode WebSocket connection. In Socket Mode, trust is established at the connection level via `SLACK_APP_TOKEN` — individual event messages are **not** HMAC-signed (signing secrets apply only to HTTP Events API mode, which this application does not use; see S5-R2 and S5-R5). The `user_id` is trusted because it arrives over the authenticated Socket Mode tunnel managed by the Bolt SDK. When a feature handler requires a canonical `User`, `SlackPlatformProvider` resolves the `user_id` via the Slack `users.info` API.

**Rules:**

- R1: Slack user identity resolution is a Category C capability of `SlackPlatformProvider` (ADR-0078). It must NOT be routed through `IdentityService` (which is scoped to JWT/HTTP auth only, per ADR-0061 Standard 3).
- R2: The provider exposes a `resolve_user(user_id: str, team_id: Optional[str] = None) -> User` method. The return type is the canonical `User` model from `infrastructure.identity.models` with `source=IdentitySource.SLACK`.
- R3: The method calls Slack `users.info` API via the existing `WebClient`. Failures must be returned as `OperationResult` with appropriate status (ADR-0050 Standard 1 — external service boundary rule applies).
- R4: The resolved `user_id` (canonical key) is the user's email address from the Slack profile. If the Slack profile has no email, resolution fails with `OperationResult.permanent_error()`.
- R5: Resolution results may be cached per request context but must not be cached across requests (Slack profile data can change; no TTL-based shared cache).
- R6: Feature handlers that receive a `user_id` from a Slack event must call `provider.resolve_user(user_id)` to obtain the canonical `User`. Direct use of the Slack `user_id` as a business key is prohibited.

## Derivation from Higher-Tier ADRs

### Constraint Derivation Table

| Source ADR | Source Norm | Constraint Applied | ADR-0067 Standard |
|---|---|---|---|
| ADR-0046 I2 | Sequential Phase Execution | Socket Mode connects in phase 5 (Transport), after phase 3 registration completes | S1 R1 |
| ADR-0046 I3 | Fail-Fast Startup | Invalid Slack credentials → startup failure, not degraded start | S1 R3 |
| ADR-0046 I5 | Immutable Registries After Startup | Command/action/view registry frozen after phase 3 | S4 R4 |
| ADR-0046 I6 | Structured Lifecycle Observability | Phase transition log events for Slack provider | S1 R4, S7 |
| ADR-0057 S1 | Signal-to-Lifespan Contract | No custom signal handlers; daemon thread cooperates with uvicorn | S2 R5 |
| ADR-0057 S2 | Shutdown Timeout Budget | Transport phase ≤5 s; thread join with timeout | S3 R1, S3 R2 |
| ADR-0057 S3 | Resource Cleanup Obligation | `stop()` method idempotent, exception-safe, logs errors | S3 R3, S3 R4 |
| ADR-0057 S5 | Shutdown Observability | Structured shutdown events with duration | S3 R5, S7 R3 |
| ADR-0058 S1 | Colocated Worker Model | Socket Mode thread shares process with FastAPI; must not starve event loop | S2 R1 |
| ADR-0059 S1 | HTTP-First Bridge | Business logic testable via HTTP; Slack handlers are thin adapters | (architectural constraint — not restated) |
| ADR-0059 S3 | Hookspec Contract | `register_slack_interactions(provider: SlackPlatformProvider)` concrete type | S4 R1 |
| ADR-0059 S5 | Platform Transport Lifecycle | Transport connects only after handler registration completes | S1 R1 |
| ADR-0059 S6 | Outbound Notification Routing | Features own routing; provider exposes sending capability only | S6 R2 |
| ADR-0065 P3 | Pydantic at I/O Boundaries | Settings class is `BaseModel` (env vars are untrusted) | S5 R1 |
| ADR-0078 S1 | Concrete Per-Platform Services | `SlackPlatformProvider` is concrete class, not Protocol | S4 R1, S4 R5 |
| ADR-0078 S2 | Settings-Driven Availability | `SLACK_ENABLED` gates construction | S1 R2 |
| ADR-0078 S4 | Infrastructure Ownership | Provider lives in infrastructure layer; features do not construct it | S4 R5 |

### Feature-Specific Decisions (Not Governed by Higher Tiers)

| Decision | Rationale | Standard |
|---|---|---|
| Socket Mode as exclusive Slack transport (no HTTP Events API) | Private VPC constraint; eliminates public endpoint requirement | S2 (entire) |
| Single daemon thread named `slack-socket-mode` | Bolt SDK `SocketModeHandler.connect()` is blocking; single connection per process chosen for operational simplicity. Slack supports up to 10 connections; horizontal scaling via ECS tasks (currently 2) provides multi-connection distribution without per-process complexity | S2 R1, S2 R4 |
| `SLACK_SOCKET_MODE` field defaulting to true with future HTTP mode path | Forward-compatible settings schema without current complexity | S5 R5 |
| Provider-mediated SDK access (features must not import Bolt types) | Prevents coupling to SDK internals; enables future SDK version migration without feature changes | S4 R5 |
| `slack_` log event prefix namespace | Avoids collision with platform-level and feature-level event names | S7 R1 |
| Fail-fast on invalid credentials (not degraded-start) | Slack is a primary interaction transport; running without it masks configuration errors in production | S1 R3 |

## Consequences

- Positive impacts:
  - Deterministic startup and shutdown lifecycle for Slack transport, aligned to platform-wide phase model.
  - Explicit shutdown budget compliance prevents Slack connection teardown from blocking process termination.
  - Feature registration via hookspec decouples command ownership from transport lifecycle — features can be added/removed without modifying infrastructure.
  - Structured observability enables operational monitoring of Slack connection health.
- Tradeoffs accepted:
  - Fail-fast on invalid Slack credentials means a misconfigured deployment cannot serve HTTP-only traffic. This is deliberate — Slack is a primary transport, not optional.
  - Features cannot use Bolt SDK types directly, adding a thin indirection layer. This is accepted for SDK version isolation.
- Risks introduced:
  - Single daemon thread is a single point of failure for all Slack interactions within a task. Bolt SDK's built-in reconnection mitigates transient WebSocket failures.
  - 5 s shutdown budget may be insufficient if Slack's WebSocket close handshake is slow. Mitigation: timeout-based forced termination with warning log.
- Mitigations:
  - Bolt SDK reconnection handles transient network failures automatically.
  - Shutdown timeout logging enables alerting when budget is consistently exceeded.
  - `SLACK_SOCKET_MODE` enables intentional dual-mode operation as the system evolves toward first-class support for both Socket Mode and HTTP Events API mode.

## Compliance and Boundaries

- Package/infrastructure boundary impact:
  - Current implementation remains in `app/infrastructure/platforms/providers/`, but new dual-mode transport work (Socket + HTTP) must be implemented in the upcoming SlackPlatform service under `app/infrastructure/slack/` instead of extending deprecated `app/infrastructure/platforms/` packages.
  - `SlackPlatformSettings` remains in `app/infrastructure/configuration/infrastructure/`.
  - Feature packages consume via hookspec injection only.
- Type boundary impact (Protocol/dataclass/BaseModel/TypedDict):
  - `SlackPlatformSettings`: Pydantic `BaseModel` (I/O boundary — ADR-0065 P3).
  - `SlackPlatformProvider`: concrete class (ADR-0078 S1 — no Protocol).
  - Feature registration parameters: plain Python types (command names as `str`, handler callables as `Callable`).
- Startup/plugin registration impact:
  - No import-time side effects. Provider constructed during lifespan phase 3.
  - `register_slack_interactions` hookspec fired during phase 3 discovery/registration.
  - Socket Mode daemon thread spawned during phase 5 transport.
- Settings partitioning impact:
  - `SlackPlatformSettings` is a partitioned settings class (ADR-0055). Not aggregated into root settings.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, web validation completed: N/A
- Validation summary: All constraints derived from Accepted ADRs (0044, 0046, 0057, 0058, 0059, 0065, 0078). Feature-specific decisions validated against current codebase implementation and Slack Bolt SDK documentation.
- Follow-up actions:
  - Review when Slack Bolt SDK releases major version changes that affect Socket Mode lifecycle.
  - Re-evaluate fail-fast vs. degraded-start if operational evidence shows false-positive startup failures in staging.

## Source References

1. Source title: Slack Bolt for Python — Socket Mode
   - URL: <https://docs.slack.dev/tools/bolt-python/concepts/socket-mode>
   - Publisher/maintainer: Slack Technologies / Salesforce
   - Accessed date (YYYY-MM-DD): 2026-04-30
   - Relevance summary: Authoritative documentation for SocketModeHandler lifecycle, connect/close semantics, and daemon thread usage patterns.
2. Source title: Slack API — Socket Mode
   - URL: <https://docs.slack.dev/apis/events-api/using-socket-mode>
   - Publisher/maintainer: Slack Technologies / Salesforce
   - Accessed date (YYYY-MM-DD): 2026-04-30
   - Relevance summary: Socket Mode protocol specification, app-level token requirements, connection limit enforcement (one connection per app-token).
3. Source title: Slack Bolt for Python — Middleware and Listeners
   - URL: <https://docs.slack.dev/tools/bolt-python/concepts/middleware>
   - Publisher/maintainer: Slack Technologies / Salesforce
   - Accessed date (YYYY-MM-DD): 2026-04-30
   - Relevance summary: Bolt middleware model (ack(), say(), command parameters) that defines the handler signatures feature hookimpls interact with.
4. Source title: Current SlackPlatformProvider implementation
   - URL: app/infrastructure/platforms/providers/slack.py
   - Publisher/maintainer: Application Engineering
   - Accessed date (YYYY-MM-DD): 2026-04-30
   - Relevance summary: Existing implementation largely aligned with this ADR; validates feasibility of codified standards.

## Implementation Guidance

- Required changes:
  - Audit `SlackPlatformProvider` against S1–S7 rules. Current implementation is largely compliant; gaps are in observability events (S7) and explicit phase-alignment documentation.
  - Add missing structured log events per S7 R2 and S7 R3.
  - Verify `stop()` idempotency and exception safety per S3 R3 and S3 R4.
  - Ensure no feature package imports Bolt SDK types directly (S4 R5) — audit `from slack_bolt` and `from slack_sdk` imports in `app/packages/`.
- Validation and quality gates:
  - mypy
  - flake8
  - black --check .
  - pytest app/tests --ignore=app/tests/smoke
- Test strategy and acceptance criteria impact:
  - Provider lifecycle tests: verify `initialize_app()` returns failing `OperationResult` when tokens missing.
  - Shutdown tests: verify `stop()` is idempotent, does not raise, completes within timeout.
  - Registration tests: verify duplicate command registration raises during phase 3.
  - No Slack Socket Mode connection in tests (credentials not available). Test registration and lifecycle methods with mocked Bolt SDK.

## Change Log

- 2026-04-30: Authored as Draft. Supersedes ADR-0014 (Slack Socket Mode). Codifies SlackPlatformProvider lifecycle alignment, shutdown contract, feature registration hookspec, settings schema, and observability contract.
- 2026-04-30: R1 challenge review → REVISE. Corrected S2 R4: Slack supports up to 10 simultaneous connections (not 1 as originally claimed). Single connection retained as design choice for operational simplicity. Updated source reference URLs to current docs.slack.dev domain.
- 2026-04-30: R1 revision applied. S2 R4 expanded: documented multi-task ECS deployment (desired_count=2) as the horizontal scaling model. Slack distributes events across task connections with no duplication. Multi-connection per process not planned. Feature-Specific Decisions table updated to match.
- 2026-04-30: R2 challenge review → PASS. Status changed from Draft to Accepted. ADR-0014 superseded and moved to `adr/superseded/`. Wave 6 gate closed.
- 2026-05-06: Amendment added to track long-term dual transport support (Socket Mode + HTTP Events API) via `SLACK_SOCKET_MODE`, with implementation target in upcoming `app/infrastructure/slack/` SlackPlatform service rather than deprecated `app/infrastructure/platforms/` packages.
- 2026-05-01: Scope clarification amendment (editorial, ADR-0080 follow-up). Clarified "any feature or subsystem" is scoped to code running within the ASGI lifespan per ADR-0080 P3. Infrastructure components deployed independently (e.g., Lambda alerting) are explicitly excluded. Added ADR-0080 to `related_records`.

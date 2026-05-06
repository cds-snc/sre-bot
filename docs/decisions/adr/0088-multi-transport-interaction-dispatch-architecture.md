---
adr_id: ADR-0088
title: "Multi-Transport Interaction Dispatch Architecture"
status: Draft
decision_type: Architecture
tier: Tier-2
governance_domain: application
primary_domain: Transport and API
secondary_domains:
  - Package and Plugin Architecture
  - Dependency and Composition
owners:
  - SRE Team
date_created: 2026-05-06
last_updated: 2026-05-06
last_reviewed: 2026-05-06
next_review_due: 2026-09-02
constrained_by:
  - ADR-0044
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0063
  - ADR-0078
impacts:
  - ADR-0049
  - ADR-0059
  - ADR-0063
  - ADR-0078
supersedes: []
superseded_by: []
review_state: current
related_records:
  - ADR-0045
  - ADR-0048
  - ADR-0049
  - ADR-0059
  - ADR-0063
  - ADR-0067
  - ADR-0078
  - ADR-0085
  - ADR-0086
  - ADR-0087
related_packages:
  - app/packages/access
  - app/packages/geolocate
  - app/infrastructure/platforms
  - app/infrastructure/hookspecs
---

# Multi-Transport Interaction Dispatch Architecture

## Context

- Problem statement: The codebase supports two live interaction transports (FastAPI HTTP
  endpoints and Slack Bolt in websocket mode) and has stub support for two additional
  platforms (Teams, Discord). As Teams support moves from stub to production, the absence
  of a governing architectural model for multi-transport dispatch is becoming a concrete
  problem: there is no rule that defines how a feature package makes a single piece of
  business logic available on multiple transports, how new transports are added without
  modifying existing feature code, or where the boundary between transport-specific
  adaptation and transport-agnostic business logic must be drawn.

  **What "transport" means in this codebase:**

  | Transport | Mechanism | Direction | Current status |
  |-----------|-----------|-----------|----------------|
  | FastAPI HTTP | HTTP/REST via Uvicorn | Inbound request → response | Live |
  | Slack Bolt | Persistent websocket to Slack API | Inbound slash command / event → response | Live |
  | Teams | HTTP webhook (Teams calls the app endpoint) | Inbound command / event → response | Stub — no handlers implemented |
  | Discord | HTTP webhook (Discord calls the app endpoint) | Inbound slash command → response | Stub — no handlers implemented |

  HTTP, Teams, and Discord are all inbound HTTP, but they differ in authentication
  (JWT bearer vs. HMAC signing vs. Slack signing secret), payload format, and response
  format. Slack Bolt adds a persistent websocket connection managed by the Bolt SDK.
  "Transport" and "platform" therefore partially overlap but are not synonymous:
  Slack/Teams/Discord are *platforms* (ADR-0059, ADR-0078) with their own command
  vocabularies and output formats; HTTP is a generic transport used by both the REST API
  and the Teams/Discord webhook endpoints.

  **The current interaction file pattern:**

  Feature packages implement per-transport interaction files under an `interactions/`
  or `platforms/` sub-directory:

  | Package | Interaction files | Transport covered |
  |---------|------------------|-------------------|
  | `access/sync` | `interactions/http.py`, `interactions/slack.py`, `interactions/ingress.py` | HTTP, Slack |
  | `access/request` | `interactions/http.py` | HTTP only |
  | `access/catalog` | `interactions/http.py` | HTTP only |
  | `geolocate` | `routes.py` (HTTP), `platforms/slack.py`, `platforms/teams.py` (stub), `platforms/discord.py` (stub) | HTTP, Slack, Teams-stub, Discord-stub |

  `access/sync` introduced a transport-agnostic ingress layer (`interactions/ingress.py`)
  that separates the enabled-check, idempotency-lock, and job spawn logic from the
  transport-specific parsing and response formatting:

  ```python
  # interactions/ingress.py — transport-neutral admission logic
  def enqueue_user_sync(coordinator, idempotency, settings, user_email, ...) -> EnqueuedJob:
      ...

  # interactions/http.py — HTTP transport adapter
  result = enqueue_user_sync(coordinator, idempotency, settings, user_email=...)
  return SyncJobResponse(...)   # HTTP-specific response

  # interactions/slack.py — Slack transport adapter
  result = enqueue_user_sync(coordinator, idempotency, settings, user_email=...)
  say(format_slack_message(result))   # Slack-specific response
  ```

  This is the correct vertical separation pattern: transport-agnostic logic in
  `ingress.py`, transport-specific parsing and formatting in the per-transport file.
  However, this pattern exists only in `access/sync` and is not documented as the
  canonical architecture. The `geolocate` package duplicates the business logic call
  (`geolocate_ip(...)`) directly in each of its per-transport files without a
  shared ingress layer:

  ```python
  # platforms/slack.py
  result = geolocate_ip(ip_address, maxmind_client)

  # routes.py (HTTP)
  result = geolocate_ip(ip_address, maxmind_client)
  ```

  For a thin function like `geolocate_ip` this is not a risk, but as more platforms are
  added and business logic grows, the absence of a mandatory ingress layer creates the
  risk of transport-specific divergence.

  **The hookspec registration model and its relationship to transport dispatch:**

  Platforms are registered via pluggy hookspecs:

  ```python
  # infrastructure/hookspecs/features.py
  @hookspec
  def register_slack_commands(provider: "SlackPlatformProvider") -> None: ...

  @hookspec
  def register_teams_commands(provider: "TeamsPlatformProvider") -> None: ...

  @hookspec
  def register_discord_commands(provider: "DiscordPlatformProvider") -> None: ...
  ```

  Each feature package implements the relevant hookimpls in its `__init__.py`. This
  means:

  1. A feature that supports Slack implements `register_slack_commands`.
  2. A feature that supports Teams implements `register_teams_commands`.
  3. A feature that does not support a platform simply does not implement that hookspec.

  Adding a new transport (e.g., Discord going live) requires:
  - Adding a `register_discord_commands` hookspec (already exists).
  - Adding `@hookimpl def register_discord_commands(provider)` to each feature's
    `__init__.py`.
  - Adding a `platforms/discord.py` (or `interactions/discord.py`) to each feature.

  There is no governing rule that constrains or validates this flow. Questions without
  answers include:
  - Must every transport hookspec always be implemented by a feature, or is it optional?
  - Should a feature that supports Slack automatically receive Teams support when Teams
    goes live, or does each transport require explicit opt-in per feature?
  - Is the hookspec-per-platform model the correct mechanism for transport dispatch, or
    should transport registration be decoupled from the plugin lifecycle hookspecs?

  **The `CommandPayload` / `CommandResponse` abstraction layer:**

  `infrastructure/platforms/models.py` defines transport-agnostic `CommandPayload` and
  `CommandResponse` dataclasses. Each per-platform handler (Slack, Teams, Discord)
  receives or constructs a `CommandPayload` and returns a `CommandResponse`. The
  platform provider translates between the native platform format and these models.

  This is structurally correct: the shared model prevents business logic from importing
  Slack-specific types. But the contract between "what a command handler receives" and
  "what a platform provider expects" is not formally specified as a Protocol or typed
  interface — it is conventional. There is no ADR that defines `CommandPayload` and
  `CommandResponse` as the stable boundary types for multi-transport dispatch, nor one
  that defines what the typed callable contract for a command handler is.

  **The ADR-0059 and ADR-0078 gap:**

  ADR-0059 governs "feature interaction boundaries": it defines the `interactions/`
  sub-directory structure and the principle that interaction files are transport adapters.
  ADR-0078 governs "platform services architecture": it defines how Slack, Teams, and
  Discord platform providers are implemented and injected as infrastructure services.

  Neither ADR defines:
  - What a multi-transport feature looks like end-to-end (from hookimpl registration
    to transport-agnostic ingress to platform provider dispatch).
  - How a feature adds support for a new transport without modifying its business logic
    layer.
  - Whether a transport-agnostic ingress layer (like `access/sync/interactions/ingress.py`)
    is required, recommended, or optional.
  - What the typed contract is for a command handler callable (the type signature that
    `provider.register_command(handler=...)` expects and that platform files must
    conform to).

  **The Slack-specific startup concern:**

  Slack Bolt runs in websocket mode, which means it establishes a persistent connection
  at startup. FastAPI, Teams, and Discord use inbound HTTP (stateless per-request).
  This architectural difference means that the startup and lifecycle management of
  transport connections is not uniform. Whether a future ADR should unify transport
  lifecycle management (all transports start/stop together under a single abstraction)
  or keep per-transport lifecycle management explicit is not governed.

  **Relationship to ADR-0085, ADR-0086, ADR-0087:**

  ADR-0085 governs what the infrastructure barrel exports (structural).
  ADR-0086 governs how features consume infrastructure services at each call boundary.
  ADR-0087 governs what a vertically isolated feature package looks like.
  This ADR governs how a feature package's interaction layer is structured to support
  multiple input transports and how new transports are added to the system without
  modifying feature business logic. The four ADRs address the same system from different
  angles and are mutually consistent, but each has an independent decision scope.

- Business/operational drivers:
  - Teams support is moving from stub to production. Before the first Teams command
    handler is implemented, a governing model must exist so that Teams integration does
    not accumulate the same ad-hoc structure that Slack integration accumulated.
  - Discord integration is planned but not yet prioritized. The governing model must be
    capable of accommodating it without changes to feature code.
  - The `access/sync` ingress pattern is the only multi-transport feature in the codebase
    and is not documented as the canonical pattern. If it is the right model, it must be
    ratified so all future features follow it; if it is not, it must be amended before it
    is replicated.
  - As the `packages/` tree grows, a clear model for "how does a feature go from HTTP-only
    to multi-transport" prevents each team from inventing an independent solution.

- Constraints:
  - ADR-0049: transport registration must happen through pluggy hookspecs (`register_slack_commands`,
    `register_teams_commands`, `register_discord_commands`). Any multi-transport dispatch
    model must be compatible with the hookimpl discovery and invocation model.
  - ADR-0059: the `interactions/` sub-directory is the governed home for interaction
    files. Any new model must extend, not contradict, this structure.
  - ADR-0063: HTTP route handlers must be thin adapters. The multi-transport model must
    enforce the same thinness constraint on Slack/Teams/Discord handlers — they must not
    contain business logic.
  - ADR-0078: platform providers (Slack, Teams, Discord) are infrastructure services.
    Feature packages receive providers as arguments to hookimpl functions; they must not
    construct providers directly.
  - ADR-0065: `CommandPayload` and `CommandResponse` are defined as dataclasses
    (`@dataclass`). The type boundary rules apply to multi-transport interaction models.
  - Slack Bolt's websocket mode and Teams/Discord webhook modes have different startup
    and lifecycle characteristics. The governing model must either unify this or
    explicitly acknowledge the split.
  - `app/modules/` is frozen and must not be touched.

- Non-goals:
  - This record does not govern the output channel for platform notifications (proactive
    messages sent to users) — that is governed by ADR-0059 and ADR-0078.
  - This record does not define the internal structure of platform provider
    implementations inside `infrastructure/platforms/` (governed by ADR-0078).
  - This record does not govern the authentication and authorization model for HTTP
    endpoints (governed by ADR-0064).
  - This record does not define the barrel structure of `infrastructure/services/`
    (governed by ADR-0085).
  - This record does not govern package-level isolation rules (governed by ADR-0087).

- Research required before Decision:
  - **Ingress layer mandatory vs optional:** Whether a transport-agnostic ingress layer
    (like `access/sync/interactions/ingress.py`) should be mandatory for all features
    that support more than one transport, or optional when the shared business logic is
    trivially thin (like `geolocate_ip`), requires research into vertical slice
    architecture literature, FastAPI multi-transport integration patterns, and
    production examples of Python applications that support multiple input channels
    (REST + chat platform + webhook). The decision also depends on the governing answer
    in ADR-0087 (what a vertically isolated package must contain). Online research must
    be completed before this sub-question can be decided.
  - **Per-platform hookspecs vs unified transport registry:** Whether the current model
    (one hookspec per platform: `register_slack_commands`, `register_teams_commands`,
    `register_discord_commands`) should be retained, or replaced with a unified transport
    registry pattern (one hookspec through which a feature declares support for named
    transports), requires research into pluggy multi-hookspec patterns, examples of
    pluggy-based multi-transport dispatch in Python projects, and the maintainability
    tradeoffs of explicit per-transport hookspecs vs a generic registry. The current
    per-platform model was not designed to handle four or more transports; whether it
    scales gracefully or becomes unwieldy at that size is an open empirical question
    that online research must inform before the Decision section can be written.
  - **Command handler typed contract:** Whether `CommandPayload` / `CommandResponse`
    are sufficient as the stable multi-transport boundary types, or whether a formal
    `Protocol` for the command handler callable signature is needed, requires research
    into typed dispatch patterns in Python (structural subtyping via `Protocol`,
    `Callable[[CommandPayload], CommandResponse]` type aliases) and FastAPI + pluggy
    integration conventions.

## Decision

*TBD — pending Context review and author approval.*

## Alternatives Considered

*TBD*

## Consequences

*TBD*

## Compliance and Boundaries

*TBD*

## Best-Practice Revalidation

*TBD*

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: No
- Validation summary: Draft record. Context under author review. Decision not yet written.
- Follow-up actions:
  - Confirm Context with author.
  - Proceed to Decision section once Context is approved.
  - Challenge review (Round 1) after Decision section is complete.

## Source References

*TBD*

## Implementation Guidance

*TBD*

## Change Log

- 2026-05-06: Created as Draft. Governs multi-transport interaction dispatch architecture:
  how feature packages register handlers for multiple input transports, how the
  transport-agnostic ingress pattern is extended, and how new transports are added
  without modifying feature business logic. Companion to ADR-0085, ADR-0086, ADR-0087.

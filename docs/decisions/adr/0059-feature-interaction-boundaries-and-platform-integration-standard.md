---
adr_id: ADR-0059
title: "Feature Interaction Boundaries and Platform Integration Standard"
status: Accepted
decision_type: Standard
tier: Tier-2
primary_domain: Package and Plugin Architecture
secondary_domains:
 - Dependency and Composition
 - Transport and API
owners:
 - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-27
constrained_by:
 - ADR-0044
 - ADR-0055
 - ADR-0056
 - ADR-0076
 - ADR-0077
impacts:
 - ADR-0071
supersedes:
 - ADR-0028
superseded_by: []
review_state: current
related_records:
 - ADR-0045
 - ADR-0046
 - ADR-0047
 - ADR-0048
 - ADR-0049
 - ADR-0050
 - ADR-0054
 - ADR-0058
 - ADR-0078
related_packages:
 - app/infrastructure/hookspecs
 - app/infrastructure/services
 - app/packages/access/sync/interactions
---

# Feature Interaction Boundaries and Platform Integration Standard

## Context

- **Problem statement:** Collaboration platforms (Slack, Teams, HTTP API) expose rich interactive capabilities — commands, views/modals, actions, and messaging — but no unified standard governs how feature packages register for and consume these capabilities. The existing `app/infrastructure/commands/` subsystem (ADR-0025 era) only covers command dispatch and uses a narrow per-provider JSON configuration model (`COMMAND_PROVIDERS`). Views, actions, and messaging remain ad-hoc per feature. ADR-0028 defined feature-side interaction directory structure but predates the pluggy registration model and concrete per-platform service types.

- **Business/operational drivers:**
 - Multi-platform parity: features must be deployable across Slack, Teams, and HTTP API without duplicating business logic.
 - Testability: feature business logic must be independently testable without platform SDK dependencies.
 - Migration path: `app/infrastructure/commands/` must be retirable (ADR-0071) once this standard provides the successor architecture.
 - Plugin composability: new platforms must be addable without modifying existing feature code.

- **Constraints:**
 - Platform services are Category C infrastructure implementation details (ADR-0077). No Protocol contract required. See ADR-0078 for platform service architecture.
 - Provider composition must follow the three-file DI ceremony where applicable (ADR-0056 Standard 1, Standard 4).
 - Settings must follow the dissolution model with independent singleton providers (ADR-0055).
 - Intra-infrastructure imports must respect layer isolation rules (ADR-0076).
 - Fallible operations must return `OperationResult[T]` (ADR-0050).

- **Non-goals:**
 - This record does not define platform-specific SDK integration details (Slack Bolt, Teams Bot Framework). Those belong in Integration Decision records (Tier-4).
 - This record does not govern generic provider composition plumbing — that is ADR-0056's scope.
 - This record does not define background execution or worker isolation for async interaction processing — that is ADR-0058's scope.
 - This record does not govern Discord platform support. Discord exists as a stub with a hookspec (`register_discord_commands`) and a `DiscordPlatformProvider` placeholder, but has no production implementation. Discord governance will be addressed if and when a concrete implementation is built.
 - This record does not define platform service types, classification, or construction — that is ADR-0078's scope.

## Decision

### Standard 1: HTTP-First Bridge Pattern

Business logic is exposed through FastAPI HTTP endpoints (`interactions/http.py`) as the primary testable interface. Platform-specific handlers (Slack, Teams) call the service layer directly — they do **not** make internal HTTP requests.

```
HTTP Request -> interactions/http.py -> ingress.py -> service.py -> presenter -> JSON
Slack Event -> interactions/slack.py -> ingress.py -> service.py -> presenter -> Block Kit
Teams Event -> interactions/teams.py -> ingress.py -> service.py -> presenter -> Adaptive Card
```

All transport paths share the same service invocation. Channel-specific formatting belongs exclusively in presenters, not in service logic.

**Rules:**
- H1: HTTP endpoints are the primary test surface. If a feature works via HTTP, the business logic works for all platforms.
- H2: Platform handlers (Slack, Teams) are thin adapters that translate platform payloads into service invocations and format responses using presenters.
- H3: Presenter unit tests are expected complements to HTTP route tests — they validate Block Kit / Adaptive Card output structure independently.

### Standard 2: Feature-Side Interaction Boundary

Feature packages organize inbound interaction handling in a dedicated `interactions/` directory. This supersedes ADR-0028's directory standard and aligns with pluggy registration and concrete per-platform service types (ADR-0078).

```
packages/<feature>/
├── __init__.py          # Pluggy hooks (@hookimpl)
├── domain.py            # Internal frozen dataclass models
├── service.py           # Business logic (channel-agnostic)
├── providers.py         # @lru_cache DI factory functions
├── schemas.py           # Pydantic request/response models (I/O boundary)
├── presenters.py        # Channel-specific response formatting
├── adapters/            # Outbound: Protocol-defined external integrations
│   ├── __init__.py
│   └── <provider>.py
└── interactions/        # Inbound: channel-specific request handlers
    ├── ingress.py       # Shared admission logic (enabled-check, lock-check)
    ├── http.py          # FastAPI route handlers (primary testable surface)
    ├── slack.py         # Slack command/view/action handlers
    └── teams.py         # Teams command/card handlers
```

**Reference implementation:** `app/packages/access/sync/interactions/` demonstrates this structure with `ingress.py` (shared admission), `http.py` (FastAPI routes), and `slack.py` (Slack handlers).

**Rules:**
- B1: `service.py` must never import from `interactions/` — dependency flows inward only.
- B2: `interactions/http.py` is the canonical test surface; Slack/Teams handlers are thin adapters.
- B3: `ingress.py` contains shared admission logic (feature-enable checks, concurrency guards). Admission logic is feature-specific because it involves domain state (sync locks, platform-specific configurations, feature preconditions), not generic boolean flags.
- B4: Presenters map domain results to channel-specific formats; they do not contain business logic.
- B5: Features implement platform handlers only for platforms they support. There is no mandate that all features support all platforms.

### Standard 3: Hookspec Contract for Multi-Platform Registration

Feature packages register interaction capabilities via pluggy hookspecs defined in `app/infrastructure/hookspecs/features.py`. Registration uses per-platform hooks with **concrete** platform service types to preserve platform-native type signatures.

**Actual hookspec definitions (from codebase):**

```python
# app/infrastructure/hookspecs/features.py

@hookspec
def register_slack_commands(provider: "SlackPlatformProvider") -> None:
    """Register Slack commands with the provider."""

@hookspec
def register_teams_commands(provider: "TeamsPlatformProvider") -> None:
    """Register Teams commands with the provider."""

@hookspec
def register_routes(app: "FastAPI") -> None:
    """Register HTTP routes with the FastAPI application."""
```

**Feature-side hookimpl example (from `app/packages/access/sync/__init__.py`):**

```python
@hookimpl
def register_slack_commands(provider: "SlackPlatformProvider") -> None:
    from .interactions.slack import register
    register(provider)

@hookimpl
def register_routes(app: "FastAPI") -> None:
    from .interactions.http import router
    app.include_router(router)
```

Per-platform hooks are preferred over a single unified hook because platform handler signatures genuinely differ:
- **Slack Bolt:** Functional middleware — `ack()`, `say()`, `command` parameters. Requires explicit `ack()` within 3 seconds.
- **Teams Bot Framework:** Class-based — `TeamsActivityHandler` with `TurnContext` carrying conversation state.
- A unified hookspec would erase these type differences, forcing `Callable[..., Any]` signatures and `if platform == "slack"` branches.

**Rules:**
- K1: Hookspec parameter types are concrete (e.g., `SlackPlatformProvider`), not abstract Protocols. Platform APIs are asymmetric — no shared Protocol is appropriate (ADR-0078).
- K2: Features that do not support a platform simply omit the hookimpl. If a hookspec fires, the platform is available; if it does not fire for a feature, that feature runs on HTTP + background jobs only.
- K3: Registration is startup-driven via pluggy. No import-time side effects (ADR-0046).
- K4: Hookimpls should use lazy imports (deferred to function body) to avoid circular import issues and minimize startup cost for disabled features.

### Standard 4: Platform Service Construction Governance

Platform service availability is determined entirely by settings. This standard defines the rules; ADR-0078 defines the service types and architecture.

**Rules:**
- C1: If a platform is enabled in settings (e.g., `SLACK_ENABLED=true`) and required credentials are present, the platform service is constructed and warmed up during lifespan. If not, the platform is skipped entirely — no service instance, no hookspec calls, no transport connection.
- C2: Platform settings follow the dissolution model (ADR-0055) with independent singleton providers per settings domain. See ADR-0055 Standard 3 and ADR-0078 Standard 2 for authoritative settings location governance.
- C3: No "provider discovery" pattern for platforms. Platform wiring is explicit, based on configuration.
- C4: Platform services receive the narrowest settings slice needed (ADR-0055), not the root settings object.

### Standard 5: Platform Transport Lifecycle

The startup and shutdown sequence for platform connections follows a deterministic ordering.

**Lifecycle sequence:**
1. **Settings check** — skip platform if disabled in configuration.
2. **Service construction** — inject narrowest settings slice; construct the platform service instance.
3. **Handler registration** — fire per-platform hookspecs (`register_slack_commands`, `register_teams_commands`, `register_routes`).
4. **Transport connection** — start Socket Mode / Bot Framework endpoint / HTTP server binding.
5. **Graceful shutdown** — drain in-flight handlers, close connections, join threads with timeout. Follows ADR-0057 shutdown obligations.

**Rules:**
- L1: Steps 1–4 execute during the FastAPI lifespan startup phase (ADR-0046).
- L2: Transport connections must not be established until handler registration is complete — no messages should arrive before handlers are ready.
- L3: Shutdown must follow ADR-0057 resource cleanup obligations — close transport connections, drain in-flight work, join daemon threads with a timeout budget.

### Standard 6: Outbound Notification Routing

Features own their outbound notification routing logic. There is no centralized notification router.

**Rules:**
- N1: When a feature needs to send a notification (e.g., "access sync completed"), the feature determines which platform/channel to target based on its own configuration and context.
- N2: Features import the concrete platform service (e.g., `SlackPlatformProvider`) when they need to send outbound messages. Features configure their notification targets in their own settings (e.g., `ACCESS_SYNC_NOTIFICATION_CHANNEL`).
- N3: No centralized `NotificationRouter` or `NotificationChannel` Protocol. If a cross-cutting pattern emerges later (3+ features with identical routing logic), extract a shared abstraction then.

---

- **Why this approach:** Consolidates feature-side interaction governance (ADR-0028) with platform integration patterns under a single coherent standard that respects the pluggy-registered, dissolution-settings architecture established by Wave 3 ADRs. The HTTP-first pattern ensures all feature business logic is testable without platform SDK dependencies. Per-platform hookspecs with concrete types avoid forcing artificial abstraction leaks where platform semantics genuinely differ. Platform service architecture is delegated to ADR-0078.

- **Principles established:**
 1. Service layer is channel-agnostic: all channel-specific concerns live in `interactions/` and `presenters.py`.
 2. HTTP is the primary test surface: if a feature works via HTTP, the business logic works for all platforms.
 3. Registration is startup-driven: pluggy hookspecs, never import-time side effects.
 4. Concrete types over abstract Protocols: per-platform services preserve type safety; no `Callable[..., Any]` erasure.
 5. Features own their pace: each feature implements platform support independently, with no mandate for all-platform coverage.
 6. Settings gate everything: platform availability is a config concern, not a code concern (ADR-0078).

## Alternatives Considered

1. **Unified InteractionProvider Protocol (rejected):**
 - Pros: Single abstraction across all platforms; capability matrix enables runtime feature degradation.
 - Cons: Platform interaction models are asymmetric (Slack `ack()` vs. Teams `TurnContext`). A unified Protocol erases type safety (`Callable[..., Any]`) and creates a leaky abstraction. Violates the “Rule of Three” — abstract only after three concrete implementations prove a shared pattern.
 - Why not chosen: The Platform Services Assessment (2026-04-29) empirically validated that concrete per-platform services preserve type safety and platform-native semantics. See ADR-0078.

2. **Single unified hookspec for all platforms:**
 - Pros: Simpler hookspec surface; one registration point per feature.
 - Cons: Forces artificial abstraction over genuinely different platform semantics (Slack `ack` vs. Teams turn context). Leaky abstraction leads to `if platform == "slack"` branches inside handlers.
 - Why not chosen: Per-platform hooks better preserve platform-native interaction patterns while the shared service layer handles business logic uniformly.

2. **Internal HTTP calls from platform handlers to FastAPI routes:**
 - Pros: Maximizes route reuse; platform handlers are pure HTTP clients.
 - Cons: Adds network latency, error surface, and serialization overhead for in-process calls. Breaks structured logging context propagation. Creates circular dependency between interaction layer and HTTP layer.
 - Why not chosen: Direct service invocation is simpler, faster, and maintains request context.

3. **Keep ADR-0028 as a separate active record:**
 - Pros: Less change; no supersession chain to manage.
 - Cons: ADR-0028 predates pluggy registration and concrete per-platform service types. Overlapping, stale guidance creates ambiguity.
 - Why not chosen: Consolidation removes ambiguity and provides a single authoritative reference.

4. **Centralized notification router:**
 - Pros: Single point for outbound notification routing logic.
 - Cons: Premature — no repeated pattern has been observed across 3+ features yet. Features calling `platform_provider.send_message(channel, content)` directly is the simplest approach that works.
 - Why not chosen: Features own their notification targets in their own settings. If a cross-cutting pattern emerges later, extract a shared abstraction then.

## Consequences

- **Positive impacts:**
 - Single authoritative reference for feature-side interaction architecture.
 - Clear migration target for `app/infrastructure/commands/` retirement (ADR-0071).
 - Feature packages gain a testable, channel-agnostic service pattern from day one.
 - New platforms require only a hookspec method + platform service implementation — no feature code changes.

- **Tradeoffs accepted:**
 - Per-platform hookspecs mean each new platform adds a hookspec method (low cost, high clarity). With 3 platforms currently (Slack, Teams, Discord stub), this is manageable.
 - Feature hookimpls are coupled to concrete platform types. If a platform type is renamed, all features must update. This coupling is intentional for Category C services.

- **Risks introduced:**
 - Implementation complexity: the full capability surface (commands + views + actions + messaging) is broader than the current command-only infrastructure.
 - Migration duration: existing direct platform SDK calls in legacy modules must be incrementally migrated.

- **Mitigations:**
 - Phased implementation: start with command registration (parity with current infrastructure), then extend to views/actions/messaging.
 - Legacy modules can coexist with the new pattern during migration — the dissolution model (ADR-0055) supports dual settings chains.

- **Supersession effects:**
 - ADR-0028 (Feature Interaction Layer Isolation): directory structure and boundary rules are superseded by Standard 2 here, updated for pluggy registration and concrete per-platform service types.
 - ADR-0025 (Interaction Providers Concept): superseded by ADR-0078 (Platform Services Architecture), not by this record.
 - ADR-0018 (Service Wrapper Pattern): superseded by ADR-0056 + ADR-0077, not by this record. DI ceremony governance belongs in those standards.



## Compliance and Boundaries

- **Package/infrastructure boundary impact:** Concrete per-platform services (`SlackPlatformProvider`, `TeamsPlatformProvider`) live in `app/infrastructure/platforms/providers/`. Features receive them via hookspec injection during startup, not through DI aliases. ADR-0078 governs platform service types and architecture.
- **Type boundary impact:** Platform services are Category C infrastructure implementation details (ADR-0077). No Protocol contract. Feature-side schemas use Pydantic `BaseModel` at I/O boundaries; domain entities use `@dataclass(frozen=True)`.
- **Startup/plugin registration impact:** All interaction registration is startup-driven via pluggy hookspecs. No import-time side effects (ADR-0046).
- **Settings partitioning impact:** Platform settings follow the dissolution model (ADR-0055) with independent singleton providers per settings domain. Platform availability is settings-driven (ADR-0078).

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: N/A
- Validation summary: Accepted. Challenge review R1 (2026-04-29) returned REVISE — body revision completed. R2 (2026-04-29) returned APPROVE — all conditions resolved.
- Follow-up actions: None. Next review due 2026-08-27.

## Source References (Required)

1. ADR-0028 - Feature Interaction Layer Isolation (this repository):
 - URL: docs/decisions/adr/superseded/0028-platform-feature-isolation.md
 - Publisher/maintainer: SRE Team
 - Accessed date: 2026-04-29
 - Relevance summary: Feature-side `interactions/` directory standard being superseded; provides package structure and boundary rules updated here for pluggy registration.

2. ADR-0056 - Provider Discovery and Composition Standard (this repository):
 - URL: docs/decisions/adr/0056-provider-discovery-and-composition-standard.md
 - Publisher/maintainer: SRE Team
 - Accessed date: 2026-04-29
 - Relevance summary: Constraining standard for DI ceremony, provider graph shape, and composition rules.

3. ADR-0077 - Infrastructure Service Contract Standard (this repository):
 - URL: docs/decisions/adr/0077-infrastructure-service-contract-standard.md
 - Publisher/maintainer: SRE Team
 - Accessed date: 2026-04-29
 - Relevance summary: Constraining standard for service classification. Platform services are Category C (infrastructure implementation details). See ADR-0078.

4. ADR-0078 - Platform Services Architecture (this repository):
 - URL: docs/decisions/adr/0078-platform-services-architecture.md
 - Publisher/maintainer: SRE Team
 - Accessed date: 2026-04-29
 - Relevance summary: Companion standard defining platform service types, construction, classification, and settings-driven availability.

5. Pluggy Documentation - Plugin Management and Hook System:
 - URL: https://pluggy.readthedocs.io/en/stable/
 - Publisher/maintainer: pytest-dev
 - Accessed date: 2026-04-29
 - Relevance summary: Authoritative reference for hookspec/hookimpl patterns used in Standard 3.

6. FastAPI Dependency Injection - Depends and Annotated patterns:
 - URL: https://fastapi.tiangolo.com/tutorial/dependencies/
 - Publisher/maintainer: Sebastian Ramirez (tiangolo)
 - Accessed date: 2026-04-29
 - Relevance summary: Authoritative reference for DI alias pattern used in HTTP route handler injection.

7. Slack Bolt Python - Commands, Actions, and Views:
 - URL: https://docs.slack.dev/tools/bolt-python/
 - Publisher/maintainer: Slack Technologies
 - Accessed date: 2026-04-29
 - Relevance summary: Authoritative reference for Slack's `ack()` pattern and handler signatures that justify per-platform hookspecs.

8. Microsoft Teams Bot Framework - Activity Handlers:
 - URL: https://learn.microsoft.com/en-us/microsoftteams/platform/bots/bot-concepts
 - Publisher/maintainer: Microsoft
 - Accessed date: 2026-04-29
 - Relevance summary: Authoritative reference for Teams' `TeamsActivityHandler` and `TurnContext` patterns that differ fundamentally from Slack's functional middleware model.

## Implementation Guidance

- **Required changes:**
 1. Migrate existing command registration from `app/infrastructure/commands/providers/` to per-platform hookimpl pattern per Standard 3.
 2. Update `app/packages/` feature packages to use `interactions/` directory structure per Standard 2 where not already adopted.
 3. Update ADR-0028 `superseded_by` field to reference ADR-0059.
 4. Future: Refactor `SlackPlatformProvider` to `SlackService` and `TeamsPlatformProvider` to `TeamsService` per ADR-0078 target naming. Update hookspec parameter types accordingly.

- **Validation and quality gates:**
 - All existing command tests must pass through the new registration path before `app/infrastructure/commands/` is retired.
 - Black, flake8, mypy, and pytest quality gates must remain green throughout migration.

- **Test strategy and acceptance criteria impact:**
 - Unit tests: HTTP route tests are the primary coverage surface (Standard 1). Presenter unit tests validate Block Kit / Adaptive Card output structure.
 - Integration tests: End-to-end command registration and dispatch through per-platform hookspecs.
 - Feature tests: Platform-specific handler tests (Slack `ack()` behavior, Teams response formatting) are supplementary but expected for production features.

## Change Log

- 2026-04-29: Initial draft created during ADR governance review.
- 2026-04-29: Scope revision mandated by Platform Services Assessment. InteractionProvider Protocol, Capability Matrix, and PlatformService facade rejected.
- 2026-04-29: **Full body revision completed per challenge review findings.** Removed rejected Standards 1-3. Renumbered kept Standards 4-6 to Standards 1-3. Added Standards 4-6 (platform service construction governance, transport lifecycle, outbound notification routing). Rewrote all sections to remove InteractionProvider/PlatformService references. Updated hookspec examples to match actual codebase definitions (`register_slack_commands`, `SlackPlatformProvider`). Removed ADR-0018 from `supersedes` — ADR-0018 is superseded by ADR-0056+ADR-0077, not by this record. Added explicit Discord non-goal. Added presenter testing recommendation. Resolved PlatformService classification as Category C (ADR-0077). Added ADR-0078 as source reference.
- 2026-04-29: Corrected `ITurnContext<T>` (C#/.NET) to `TurnContext` (Python SDK) per ADR-0078 challenge review findings. Updated stale Slack Bolt and Teams Bot Framework documentation URLs.

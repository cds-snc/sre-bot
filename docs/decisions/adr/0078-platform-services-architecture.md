---
adr_id: ADR-0078
title: "Platform Services Architecture"
status: Draft
decision_type: Standard
tier: Tier-2
primary_domain: Dependency and Composition
secondary_domains:
 - Transport and API
 - Package and Plugin Architecture
owners:
 - SRE Team
date_created: 2026-04-29
last_updated: 2026-04-29
last_reviewed: 2026-04-29
next_review_due: 2026-08-29
constrained_by:
 - ADR-0044
 - ADR-0045
 - ADR-0046
 - ADR-0048
 - ADR-0055
 - ADR-0056
 - ADR-0076
 - ADR-0077
impacts:
 - ADR-0059
 - ADR-0067
 - ADR-0071
supersedes:
 - ADR-0025
superseded_by: []
review_state: current
related_records:
 - ADR-0046
 - ADR-0049
 - ADR-0055
 - ADR-0056
 - ADR-0057
 - ADR-0059
 - ADR-0076
 - ADR-0077
related_packages:
 - app/infrastructure/platforms/providers
 - app/infrastructure/hookspecs
---

# Platform Services Architecture

## Context

- **Problem statement:** The SRE Bot supports multiple collaboration platforms (Slack, Teams, potentially others) as optional, independently-configurable interaction surfaces. ADR-0025 proposed a unified `InteractionProvider` Protocol to abstract all platforms behind a single contract. Analysis revealed this abstraction is premature, leaky, and type-unsafe — the platforms' interaction models are fundamentally incompatible at the handler signature level. Slack Bolt uses functional middleware with `ack()`, `say()`, and `command` parameters; Teams Bot Framework uses class-based `TeamsActivityHandler` with `ITurnContext<T>`. A unified Protocol would require `Callable[..., Any]` type erasure, defeating mypy enforcement.

- **Business/operational drivers:**
- Platform services must be independently configurable — a deployment may run Slack-only, Teams-only, or both.
- Type safety: platform handler signatures must be fully typed for mypy enforcement.
- Simplicity: no premature abstraction until three concrete implementations prove a shared pattern exists (Rule of Three).
- Migration path: the existing `SlackPlatformProvider` pattern is correct and proven in production.

- **Constraints:**
- Platform services are Category C infrastructure implementation details (ADR-0077 Standard 1). No Protocol contract required.
- Provider composition must follow ADR-0056 patterns where applicable; simpler patterns are permitted for infrastructure-internal services.
- Settings must follow the dissolution model (ADR-0055) with independent singleton providers per settings domain.
- Intra-infrastructure imports must respect layer isolation rules (ADR-0076).
- Transport lifecycle must follow lifespan startup/shutdown ordering (ADR-0046).

- **Non-goals:**
- This record does not govern feature-side interaction handling (directory structure, ingress patterns, HTTP-first testing). That is ADR-0059's scope.
- This record does not define platform-specific SDK integration details (Slack Bolt configuration, Teams Bot registration). Those belong in Integration Decision records (Tier-4, e.g., ADR-0067).
- This record does not govern Discord. Discord exists as a stub (`DiscordPlatformProvider`) with no production implementation.

## Decision

### Standard 1: Concrete Per-Platform Services

Infrastructure provides concrete, typed platform services — not abstract Protocols. Each service wraps the platform SDK with a resilient, ergonomic API that preserves platform-native capabilities and type signatures.

**Current services:**

- `SlackPlatformProvider` — wraps Slack Bolt Python SDK. Lives in `app/infrastructure/platforms/providers/slack.py`.
- `TeamsPlatformProvider` — wraps Teams Bot Framework SDK. Lives in `app/infrastructure/platforms/providers/teams.py`.
- `DiscordPlatformProvider` — stub, no production implementation. Lives in `app/infrastructure/platforms/providers/discord.py`.

**Target naming** (future refactoring): `SlackService`, `TeamsService` at `app/infrastructure/slack/service.py`, `app/infrastructure/teams/service.py`.

**Rules:**

- S1: No unified `InteractionProvider` Protocol. Each platform's API surface is fundamentally different — no shared Protocol is appropriate.
- S2: Platform services are Category C infrastructure implementation details (ADR-0077). They are not abstracted behind a Protocol because there is exactly one implementation per platform.
- S3: Service method signatures preserve platform-native types. No `Callable[..., Any]` type erasure.
- S4: Platform services are infrastructure-owned. Features do not construct or configure platform services directly.

### Standard 2: Settings-Driven Platform Availability

Whether a platform is available is determined entirely by settings. There is no "provider discovery" pattern.

**Mechanism:**

1. Platform settings live in `app/infrastructure/configuration/integrations/` (e.g., `slack.py` with `SlackSettings`).
2. Lifespan checks settings: if `SLACK_ENABLED=true` and required credentials are present, the `SlackPlatformProvider` is constructed.
3. If settings indicate a platform is disabled or credentials are missing, the platform is skipped entirely — no service instance, no hookspec calls, no transport connection.

**Rules:**

- A1: Platform availability is a configuration concern, not a code concern. No conditional imports or runtime feature flags for platform enablement.
- A2: Platform settings follow the dissolution model (ADR-0055) with independent singleton providers per settings domain.
- A3: Platform services receive the narrowest settings slice needed, not the root settings object.

### Standard 3: Hookspec-Based Feature Consumption

Features consume platform services via pluggy hookspec injection during startup. Features do not import or construct platform services directly.

**Registration flow:**

1. Lifespan constructs the platform service (settings-driven, per Standard 2).
2. Lifespan calls `pm.hook.register_slack_commands(provider=slack_provider)`.
3. Each feature's `@hookimpl` receives the provider and registers its handlers.
4. Features that don't implement the hookimpl are simply unaffected.

**Rules:**

- F1: Features never check whether a platform is enabled. If the hookspec fires, the platform is available. If it doesn't fire, the feature runs on HTTP + background jobs only.
- F2: Hookspec parameter types are concrete (`SlackPlatformProvider`, not `InteractionProvider`). See ADR-0059 Standard 3 for hookspec definitions.
- F3: For outbound messaging, features may import the platform service directly (e.g., `SlackPlatformProvider`) when they need to send notifications outside of the hookspec registration context.

### Standard 4: Infrastructure Ownership

Platform services are owned by the infrastructure layer. Features are consumers, not owners.

**Rules:**

- O1: Platform service source code lives in `app/infrastructure/platforms/providers/` (current) or `app/infrastructure/<platform>/service.py` (target).
- O2: Platform service construction happens in the lifespan or in infrastructure provider functions — never in feature packages.
- O3: Platform services may depend on other infrastructure services (e.g., `StorageService` for retry state), following ADR-0076 import rules.
- O4: Per-platform services may use simpler provider patterns than the three-file DI ceremony (ADR-0056) since they are infrastructure-internal (Category C). Full DI ceremony is not required for services that features access through hookspec injection rather than `Annotated[..., Depends()]` aliases.

---

- **Why this approach:** The codebase already has a working pattern in `app/packages/access/sync/interactions/` that demonstrates the correct architecture: feature-owned, platform-specific interaction handlers receiving concrete platform services via hookspec injection. This standard codifies that proven pattern rather than introducing a premature abstraction.

- **Principles established:**

 1. No premature abstraction: concrete services until three platforms prove a shared pattern exists.
 2. Settings gate everything: platform availability is a config concern, not a code concern.
 3. Type safety preserved: platform-specific handler signatures remain fully typed. No `Callable[..., Any]` erasure.
 4. Infrastructure owns transport, features own interaction: features decide how to interact; infrastructure provides reliable platform connections.
 5. Hookspecs for registration: features receive platform services via hookspec injection. No lookup, no discovery.

## Alternatives Considered

1. **Unified InteractionProvider Protocol (ADR-0025 approach):**

- Pros: Single abstraction across all platforms; capability matrix enables runtime feature degradation; new platforms transparently available to all features.
- Cons: Platform interaction models are asymmetric (Slack `ack()` vs. Teams `ITurnContext`). A unified Protocol requires `Callable[..., Any]` for handler signatures — erasing all type safety. The capability matrix assumes symmetric platform surfaces that don't exist. Adding a capability query layer adds indirection without enabling meaningful platform-neutral code (handlers still need platform-specific formatting).
- Why not chosen: The Rule of Three applies — abstract only after three concrete implementations prove a shared pattern. With two platforms in production (Slack active, Teams experimental), abstraction is premature. The Platform Services Assessment (2026-04-29) empirically validated this finding.

1. **PlatformService facade (centralized dispatch):**

- Pros: Single entry point for all platform interactions; centralized registration and capability querying.
- Cons: Adds an indirection layer that doesn't provide meaningful value when features already receive platform services directly via hookspec injection. The facade would either pass through to concrete services (no value) or abstract them (type erasure). DI ceremony overhead for a service consumed through hookspecs, not `Depends()`.
- Why not chosen: Features calling `provider.register_command(...)` directly is simpler and more type-safe than routing through a facade.

1. **Provider discovery pattern:**

- Pros: Platforms register themselves dynamically; zero configuration for adding platforms.
- Cons: Discovery adds startup complexity and non-determinism. With 2-3 platforms, explicit configuration is clearer than automatic discovery. Settings-driven availability (Standard 2) provides equivalent flexibility with deterministic behavior.
- Why not chosen: Explicit settings-gated construction is simpler and more predictable.

## Consequences

- **Positive impacts:**
- Platform services are fully typed — mypy enforces handler signatures per platform.
- Configuration-driven availability simplifies deployment — disable a platform by unsetting one env var.
- No premature abstraction — the architecture is ready for a future shared Protocol if three platforms ever justify one.
- Clear ownership boundary — infrastructure owns transport, features own interaction logic.

- **Tradeoffs accepted:**
- Feature hookimpls are coupled to concrete platform types. If `SlackPlatformProvider` is renamed to `SlackService`, all feature hookimpls must update. This is intentional for Category C services — the coupling is mechanical and easily refactored.
- Each new platform requires a new hookspec method in `app/infrastructure/hookspecs/features.py` and feature hookimpls to match. This is O(1) per platform — manageable at current scale.

- **Risks introduced:**
- If platform count grows significantly (5+), the per-platform hookspec surface may become unwieldy. Mitigation: consolidate per Standard 3's opt-in arguments feature if needed.
- Concrete types mean no test-time substitution via Protocol mocking for platform services. Mitigation: hookspec injection provides natural test boundaries — tests that don't register a hookimpl naturally avoid platform service interaction.

- **Supersession effects:**
- ADR-0025 (Interaction Providers Concept): fully superseded. The unified `InteractionProvider` interface is rejected in favor of concrete per-platform services. ADR-0025 remains in `docs/decisions/adr/superseded/` for historical context.

## Compliance and Boundaries

- **Package/infrastructure boundary impact:** Platform services live in `app/infrastructure/platforms/providers/` (current) or `app/infrastructure/<platform>/` (target). Features access them only through hookspec injection or direct import for outbound messaging — never through construction.
- **Type boundary impact:** Platform services are Category C (ADR-0077). No Protocol contract. Each service's public API preserves platform-native types.
- **Startup/plugin registration impact:** Platform service construction and hookspec invocation occur during lifespan startup (ADR-0046). Transport connections start after handler registration completes.
- **Settings partitioning impact:** Platform settings follow the dissolution model (ADR-0055) — independent `SlackSettings`, `TeamsSettings` singletons, not nested in a root settings object.

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: N/A
- Validation summary: Initial draft. Requires challenge review before acceptance.
- Follow-up actions: Schedule challenge review.

## Source References (Required)

1. ADR-0025 - Interaction Providers Concept (this repository):

- URL: docs/decisions/adr/superseded/0025-platform-providers-concept.md
- Publisher/maintainer: SRE Team
- Accessed date: 2026-04-29
- Relevance summary: Superseded predecessor. Defined the unified `InteractionProvider` interface concept that this record replaces with concrete per-platform services.

1. ADR-0077 - Infrastructure Service Contract Standard (this repository):

- URL: docs/decisions/adr/0077-infrastructure-service-contract-standard.md
- Publisher/maintainer: SRE Team
- Accessed date: 2026-04-29
- Relevance summary: Constraining standard for service classification. Platform services are Category C (infrastructure implementation details).

1. ADR-0059 - Feature Interaction Boundaries and Platform Integration Standard (this repository):

- URL: docs/decisions/adr/0059-feature-interaction-boundaries-and-platform-integration-standard.md
- Publisher/maintainer: SRE Team
- Accessed date: 2026-04-29
- Relevance summary: Companion standard governing feature-side interaction boundaries, hookspec contracts, and HTTP-first bridge patterns. This record governs platform-side architecture; ADR-0059 governs feature-side consumption.

1. Platform Services Assessment (2026-04-29):

- URL: tmp/platform-services-assessment-2026-04-29.md
- Publisher/maintainer: SRE Team
- Accessed date: 2026-04-29
- Relevance summary: Authoritative assessment that rejected the unified InteractionProvider Protocol and established the concrete per-platform services architecture codified here.

1. Slack Bolt Python Documentation:

- URL: <https://tools.slack.dev/bolt-python/>
- Publisher/maintainer: Slack Technologies
- Accessed date: 2026-04-29
- Relevance summary: Slack Bolt's `ack()` pattern and functional middleware model — demonstrates why a unified Protocol erases platform-native type safety.

1. Microsoft Teams Bot Framework Documentation:

- URL: <https://learn.microsoft.com/en-us/microsoftteams/platform/bots/bot-basics>
- Publisher/maintainer: Microsoft
- Accessed date: 2026-04-29
- Relevance summary: Teams' `TeamsActivityHandler` and `ITurnContext<T>` — fundamentally different from Slack's model, validating per-platform concrete types.

## Implementation Guidance

- **Required changes:**

 1. Author this ADR (current step).
 2. Future: Refactor `SlackPlatformProvider` to `SlackService` at `app/infrastructure/slack/service.py`. Refactor `TeamsPlatformProvider` to `TeamsService` at `app/infrastructure/teams/service.py`. Update hookspec parameter types.
 3. Simplify lifespan: ensure settings-gated platform construction follows Standards 2 and 3.
 4. Update all feature hookimpls if parameter names/types change during refactoring.

- **Validation and quality gates:**
- mypy must pass after any type renaming.
- All existing platform handler tests must pass.
- Black, flake8, and pytest quality gates must remain green.

- **Test strategy and acceptance criteria impact:**
- Platform service construction: test that service is constructed when settings enable it and skipped when disabled.
- Hookspec invocation: test that hookspecs fire only for enabled platforms.
- Feature hookimpls: test that feature handlers register correctly with the concrete provider.

## Change Log

- 2026-04-29: Initial draft created. Supersedes ADR-0025 (Interaction Providers Concept). Mandated by Platform Services Assessment (2026-04-29) and ADR-0059 challenge review findings. Establishes concrete per-platform services as Category C infrastructure implementation details.

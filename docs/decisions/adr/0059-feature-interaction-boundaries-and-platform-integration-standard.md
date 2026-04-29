---
adr_id: ADR-0059
title: "Feature Interaction Boundaries and Platform Integration Standard"
status: Draft
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
 - ADR-0018
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
 - app/infrastructure/commands
 - app/infrastructure/services
 - app/packages/access/sync/interactions
---

# Feature Interaction Boundaries and Platform Integration Standard

> ** SCOPE REVISION NOTICE (2026-04-29 - Platform Services Assessment)**
>
> This Draft is **pending a major revision**. The Platform Services Assessment (the 2026-04-29 Platform Services Assessment findings) rejected the unified `InteractionProvider` Protocol, `PlatformService` facade, and capability matrix (Standards 1-3 below). The revised ADR-0059 will cover:
>
> - **(A)** Feature-side interaction boundaries (`interactions/` directory, `ingress.py`, `http.py`, platform handlers)
> - **(B)** HTTP-first bridge pattern (Standards 4-5 below - kept)
> - **(C)** Hookspec contracts with **concrete** platform service types (`SlackService`, `TeamsService`) - not abstract Protocols
> - **(D)** Platform service construction governance (settings-driven, config-gated, no discovery)
> - **(E)** Platform transport lifecycle (startup ordering, graceful shutdown)
> - **(F)** Outbound notification routing (feature-owned, feature-configured, no centralized router)
>
> **ADR-0025 is NO LONGER superseded by this record.** ADR-0025 is superseded by ADR-0078 (Platform Services Architecture).
> Platform services are **Category C** infrastructure implementation details (ADR-0077), not Category A Protocol services.
>
> **Standards 1-3 below are REJECTED and will be removed in the revision. Standards 4-6 are kept with modifications.**
> Until the revision is complete, use the 2026-04-29 Platform Services Assessment findings and ADR-0078 as the authoritative position.

## Context

- **Problem statement:** Collaboration platforms (Slack, Teams, Discord, HTTP API) expose rich interactive capabilities - commands, views/modals, actions, and messaging - but no unified abstraction governs how feature packages register for and consume these capabilities. The existing `app/infrastructure/commands/` subsystem (ADR-0025 era) only covers command dispatch and uses a narrow per-provider JSON configuration model (`COMMAND_PROVIDERS`). Views, actions, and messaging remain ad-hoc per feature. ADR-0025 mixed provider-layer governance (now covered by ADR-0056) with the domain-specific interaction provider concept. ADR-0018 established service wrapper patterns now superseded by ADR-0077 Protocol contracts. ADR-0028 defined feature-side interaction directory structure but predates the pluggy registration model and Protocol-first service contracts.

- **Business/operational drivers:**
 - Multi-platform parity: features must be deployable across Slack, Teams, and HTTP API without duplicating interaction logic.
 - Testability: feature business logic must be independently testable without platform SDK dependencies.
 - Migration path: `app/infrastructure/commands/` must be retirable (ADR-0071) once this standard provides the successor architecture.
 - Plugin composability: new platforms (e.g., Discord) must be addable without modifying existing feature code.

- **Constraints:**
 - **~~InteractionProvider and PlatformService are Category A Protocol services (ADR-0077 Standard 2).~~** REVISED (2026-04-29): Platform services are Category C infrastructure implementation details. No Protocol contract required. See ADR-0078.
 - Provider composition must follow the three-file DI ceremony (ADR-0056 Standard 1, Standard 4).
 - Settings must follow the dissolution model with independent singleton providers (ADR-0055).
 - Intra-infrastructure imports must respect layer isolation rules (ADR-0076).
 - Fallible operations must return `OperationResult[T]` (ADR-0050).

- **Non-goals:**
 - This record does not define platform-specific SDK integration details (Slack Bolt, Teams Bot Framework). Those belong in Integration Decision records (Tier-4).
 - This record does not govern generic provider composition plumbing - that is ADR-0056's scope.
 - This record does not define background execution or worker isolation for async interaction processing - that is ADR-0058's scope.

## Decision

### Standard 1: InteractionProvider Protocol

Define a `@runtime_checkable` Protocol that represents the full capability surface of a collaboration platform. All platform implementations must structurally satisfy this Protocol.

```python
# app/infrastructure/interactions/protocol.py
from __future__ import annotations
from typing import Protocol, runtime_checkable, Callable, Any
from app.infrastructure.types import OperationResult

@runtime_checkable
class InteractionProvider(Protocol):
 """Platform-agnostic interaction capability surface."""

 @property
 def platform_id(self) -> str:
 """Unique identifier for this platform (e.g., 'slack', 'teams', 'http')."""
 ...

 def register_command(
 self, namespace: str, name: str, handler: Callable[..., Any]
 ) -> OperationResult[None]:
 """Register a command handler in the given namespace."""
 ...

 def register_view(
 self, view_id: str, handler: Callable[..., Any]
 ) -> OperationResult[None]:
 """Register a view/modal submission handler."""
 ...

 def register_action(
 self, action_id: str, handler: Callable[..., Any]
 ) -> OperationResult[None]:
 """Register an interactive action handler (button, menu, etc.)."""
 ...

 async def send_message(
 self, channel: str, content: dict[str, Any]
 ) -> OperationResult[None]:
 """Send an outbound message to a channel."""
 ...
```

**Rules:**
- P1: Must be `@runtime_checkable` for test assertions; mypy is the primary enforcement mechanism.
- P2: Fallible operations return `OperationResult[T]` per ADR-0050.
- P3: Protocol must not expose backing-service-specific types (no `SlackResponse`, no `TeamsActivity`).
- P4: Protocol definition lives in `app/infrastructure/interactions/protocol.py` - ownership follows code.
- P5: Method names describe capability, not implementation (`register_command`, not `slack_add_command`).

### Standard 2: Platform Capability Matrix

Each InteractionProvider implementation declares its supported capabilities. Feature packages query the capability matrix rather than checking platform identity.

| Capability | Slack | Teams | HTTP API |
|------------|-------|-------|----------|
| Commands | Yes | Yes | Yes |
| Views/Modals | Yes | Yes | No |
| Actions | Yes | Yes | No |
| Messaging | Yes | Yes | Yes |
| File Upload | Yes | Yes | Yes |

Feature packages must not branch on `platform_id`. Instead, they check capability availability and degrade gracefully when a capability is unsupported.

### Standard 3: PlatformService Facade

A single `PlatformService` facade owns provider registration, capability dispatch, and outbound messaging. PlatformService is a Category A Protocol service (ADR-0077) with its own Protocol contract.

```python
# app/infrastructure/interactions/service.py
@runtime_checkable
class PlatformServiceProtocol(Protocol):
 """Facade for multi-platform interaction dispatch."""

 def get_provider(self, platform_id: str) -> OperationResult[InteractionProvider]: ...
 def get_active_providers(self) -> list[InteractionProvider]: ...
 async def broadcast_message(
 self, channel: str, content: dict[str, Any]
 ) -> OperationResult[None]: ...
```

**DI wiring** follows ADR-0056 three-file ceremony:
- `providers.py`: `@lru_cache(maxsize=1) def get_platform_service() -> PlatformServiceProtocol`
- `dependencies.py`: `PlatformServiceDep = Annotated[PlatformServiceProtocol, Depends(get_platform_service)]`
- `__init__.py`: re-export public symbols

PlatformService receives the narrowest settings slice needed (ADR-0055), not the root settings object.

### Standard 4: HTTP-First Bridge Pattern

Business logic is exposed through FastAPI HTTP endpoints (`interactions/http.py`) as the primary testable interface. Platform-specific handlers (Slack, Teams) call the service layer directly - they do **not** make internal HTTP requests.

```
HTTP Request -> interactions/http.py -> ingress.py -> service.py -> presenter -> JSON
Slack Event -> interactions/slack.py -> ingress.py -> service.py -> presenter -> Block Kit
Teams Event -> interactions/teams.py -> ingress.py -> service.py -> presenter -> Adaptive Card
```

All three paths share the same service invocation. Channel-specific formatting belongs exclusively in presenters, not in service logic.

### Standard 5: Feature-Side Interaction Boundary

Feature packages organize inbound interaction handling in a dedicated `interactions/` directory. This supersedes ADR-0028's directory standard and aligns with pluggy registration.

```
packages/<feature>/
|-- __init__.py # Pluggy hooks (@hookimpl)
|-- domain.py # Internal frozen dataclass models
|-- service.py # Business logic (channel-agnostic)
|-- providers.py # @lru_cache DI factory functions
|-- schemas.py # Pydantic request/response models (I/O boundary)
|-- presenters.py # Channel-specific response formatting
|-- adapters/ # Outbound: Protocol-defined external integrations
| |-- __init__.py
| \-- <provider>.py
\-- interactions/ # Inbound: channel-specific request handlers
 |-- ingress.py # Shared admission logic (enabled-check, lock-check)
 |-- http.py # FastAPI route handlers (primary testable surface)
 |-- slack.py # Slack command/view/action handlers
 \-- teams.py # Teams command/card handlers
```

**Rules:**
- B1: `service.py` must never import from `interactions/` - dependency flows inward only.
- B2: `interactions/http.py` is the canonical test surface; Slack/Teams handlers are thin adapters.
- B3: `ingress.py` contains shared admission logic (feature-enable checks, concurrency guards).
- B4: Presenters map domain results to channel-specific formats; they do not contain business logic.

### Standard 6: Hookspec Contract for Multi-Platform Registration

Feature packages register interaction capabilities via pluggy hookspecs. Registration uses per-platform hooks to accommodate platform-specific handler signatures while maintaining a unified capability model.

```python
# app/infrastructure/hookspecs/interactions.py
class InteractionHookSpec:
 @hookspec
 def register_slack_interactions(self, provider: InteractionProvider) -> None:
 """Register Slack-specific interaction handlers."""

 @hookspec
 def register_teams_interactions(self, provider: InteractionProvider) -> None:
 """Register Teams-specific interaction handlers."""

 @hookspec
 def register_http_routes(self, api_router: APIRouter) -> None:
 """Register FastAPI HTTP routes."""
```

Per-platform hooks are preferred over a single unified hook because platform handler signatures differ in their acknowledgment and response semantics (e.g., Slack `ack()` pattern vs. Teams turn context).

- **Why this approach:** Unifies three previously separate governance concerns (service wrappers, interaction providers, feature isolation) under a single coherent standard that respects the Protocol-first, pluggy-registered, dissolution-settings architecture established by Wave 3 ADRs. The HTTP-first pattern ensures all feature business logic is testable without platform SDK dependencies. Per-platform hookspecs avoid forcing artificial abstraction leaks where platform semantics genuinely differ.

- **Principles established:**
 1. One Protocol, multiple providers: `InteractionProvider` is the single abstraction for all platform capabilities.
 2. Capability matrix over platform branching: features query capabilities, never check platform identity.
 3. Service layer is channel-agnostic: all channel-specific concerns live in interactions/ and presenters.
 4. HTTP is the primary test surface: if a feature works via HTTP, it works on all platforms.
 5. Registration is startup-driven: pluggy hookspecs, never import-time side effects.

## Alternatives Considered

1. **Single unified hookspec for all platforms:**
 - Pros: Simpler hookspec surface; one registration point per feature.
 - Cons: Forces artificial abstraction over genuinely different platform semantics (Slack ack vs. Teams turn context). Leaky abstraction leads to `if platform == "slack"` branches inside handlers.
 - Why not chosen: Per-platform hooks better preserve platform-native interaction patterns while the shared service layer handles business logic uniformly.

2. **Internal HTTP calls from platform handlers to FastAPI routes:**
 - Pros: Maximizes route reuse; platform handlers are pure HTTP clients.
 - Cons: Adds network latency, error surface, and serialization overhead for in-process calls. Breaks structured logging context propagation. Creates circular dependency between interaction layer and HTTP layer.
 - Why not chosen: Direct service invocation is simpler, faster, and maintains request context.

3. **Keep ADR-0025, ADR-0018, and ADR-0028 as separate active records:**
 - Pros: Less change; no supersession chain to manage.
 - Cons: Three partially overlapping, stale records with inconsistent guidance. ADR-0025 mixes provider plumbing (now ADR-0056) with interaction domain concepts. ADR-0018 predates Protocol contracts. ADR-0028 predates pluggy registration.
 - Why not chosen: Consolidation removes ambiguity and provides a single authoritative reference.

## Consequences

- **Positive impacts:**
 - Single authoritative reference for all interaction architecture concerns.
 - Clear migration target for `app/infrastructure/commands/` retirement (ADR-0071).
 - Feature packages gain a testable, channel-agnostic service pattern from day one.
 - New platforms require only a new InteractionProvider implementation and hookspec - no feature code changes.

- **Tradeoffs accepted:**
 - Per-platform hookspecs mean each new platform adds a hookspec method (low cost, high clarity).
 - Superseding three records requires updating their `superseded_by` fields and any downstream references.

- **Risks introduced:**
 - Implementation complexity: the full capability surface (commands + views + actions + messaging) is broader than the current command-only infrastructure.
 - Migration duration: existing direct platform SDK calls in legacy modules must be incrementally migrated.

- **Mitigations:**
 - Phased implementation: start with command registration (parity with current infrastructure), then extend to views/actions/messaging.
 - Legacy modules can coexist with the new pattern during migration - the dissolution model (ADR-0055) supports dual settings chains.

- **Supersession effects:**
 - ADR-0018 (Service Wrapper Pattern): service wrapper DI guidance is superseded by ADR-0056 + ADR-0077 Protocol contracts. Feature-side interaction patterns are superseded by Standard 4 and Standard 5 here.
 - ~~ADR-0025 (Interaction Providers Concept): provider-layer composition is now governed by ADR-0056. The interaction domain concept (InteractionProvider Protocol, capability matrix, HTTP-first bridge) is formalized by Standards 1\u20134 here.~~ **REVISED (2026-04-29):** ADR-0025 is superseded by ADR-0078 (Platform Services Architecture), not by this record. This record no longer supersedes ADR-0025.
 - ADR-0028 (Feature Interaction Layer Isolation): directory structure and boundary rules are superseded by Standard 5 here, updated for pluggy registration and concrete per-platform service types.

## Compliance and Boundaries

> **\u26a0\ufe0f The Compliance section below is STALE and will be rewritten during the ADR-0059 revision.** InteractionProvider and PlatformService references are rejected. See the scope revision notice at the top of this document.

- **Package/infrastructure boundary impact:** ~~InteractionProvider Protocol and PlatformService live in `app/infrastructure/interactions/`.~~ REVISED: Concrete per-platform services (`SlackService`, `TeamsService`) live in `app/infrastructure/slack/`, `app/infrastructure/teams/`. Features receive via hookspec injection, not DI aliases.
- **Type boundary impact:** ~~InteractionProvider and PlatformServiceProtocol are `Protocol` types (ADR-0077 Category A).~~ REVISED: Platform services are Category C (infrastructure implementation details, ADR-0077). No Protocol contract. Feature-side schemas use Pydantic `BaseModel` at I/O boundaries; domain entities use `@dataclass(frozen=True)`.
- **Startup/plugin registration impact:** All interaction registration is startup-driven via pluggy hookspecs. No import-time side effects (ADR-0046).
- **Settings partitioning impact:** Platform settings follow the dissolution model (ADR-0055) with independent singleton providers per settings domain. Platform availability is settings-driven (ADR-0078).

## Freshness Review

- Record age at review time (days): 0
- Is record older than 120 days: No
- If Yes, status set to stale: N/A
- Validation summary: Initial draft. Requires challenge review before acceptance.
- Follow-up actions: Schedule challenge review; validate Protocol surface against existing `app/infrastructure/commands/` capabilities.

## Source References (Required)

1. ADR-0025 - Interaction Providers Concept (this repository):
 - URL: docs/decisions/adr/superseded/0025-platform-providers-concept.md
 - Publisher/maintainer: SRE Team
 - Accessed date: 2026-04-29
 - Relevance summary: Original interaction provider concept. **Superseded by ADR-0078 (Platform Services Architecture, 2026-04-29)**, not by this record. Provides historical context for InteractionProvider interface definition and platform capability matrix that were rejected by the Platform Services Assessment.

2. ADR-0028 - Feature Interaction Layer Isolation (this repository):
 - URL: docs/decisions/adr/0028-platform-feature-isolation.md
 - Publisher/maintainer: SRE Team
 - Accessed date: 2026-04-29
 - Relevance summary: Feature-side interactions/ directory standard being superseded; provides package structure and boundary rules updated here for pluggy registration.

3. ADR-0056 - Provider Discovery and Composition Standard (this repository):
 - URL: docs/decisions/adr/0056-provider-discovery-and-composition-standard.md
 - Publisher/maintainer: SRE Team
 - Accessed date: 2026-04-29
 - Relevance summary: Constraining standard for DI ceremony, provider graph shape, and composition rules that this standard must follow.

4. ADR-0077 - Infrastructure Service Contract Standard (this repository):
 - URL: docs/decisions/adr/0077-infrastructure-service-contract-standard.md
 - Publisher/maintainer: SRE Team
 - Accessed date: 2026-04-29
 - Relevance summary: Constraining standard for service classification. **Revised (2026-04-29):** Platform services are Category C (infrastructure implementation details), not Category A. No Protocol contract required for `SlackService`/`TeamsService`. See ADR-0078.

5. Pluggy Documentation - Plugin Management and Hook System:
 - URL: https://pluggy.readthedocs.io/en/stable/
 - Publisher/maintainer: pytest-dev
 - Accessed date: 2026-04-29
 - Relevance summary: Authoritative reference for hookspec/hookimpl patterns used in Standard 6.

6. FastAPI Dependency Injection - Depends and Annotated patterns:
 - URL: https://fastapi.tiangolo.com/tutorial/dependencies/
 - Publisher/maintainer: Sebastian Ramirez (tiangolo)
 - Accessed date: 2026-04-29
 - Relevance summary: Authoritative reference for the DI alias pattern used in PlatformService facade wiring.

7. Python typing.Protocol - Structural Subtyping:
 - URL: https://docs.python.org/3/library/typing.html#typing.Protocol
 - Publisher/maintainer: Python Software Foundation
 - Accessed date: 2026-04-29
 - Relevance summary: Authoritative reference for @runtime_checkable Protocol pattern mandated by Standard 1.

## Implementation Guidance

> ** The implementation guidance below is STALE and will be rewritten during the ADR-0059 revision.** The InteractionProvider Protocol, PlatformServiceProtocol, and capability matrix references are rejected. See the scope revision notice at the top of this document.

- **Required changes (revised direction):**
 1. ~~Create `app/infrastructure/interactions/` package with `protocol.py`, `service.py`.~~ REMOVED - no unified Protocol.
 2. ~~Define `InteractionProvider` Protocol and `PlatformServiceProtocol`.~~ REMOVED.
 3. Add per-platform interaction hookspecs to `app/infrastructure/hookspecs/` per Standard 6 (with concrete `SlackService`/`TeamsService` parameter types).
 4. Migrate existing command registration from `app/infrastructure/commands/providers/` to per-platform hookimpl pattern.
 5. Update `app/packages/` feature packages to use `interactions/` directory structure per Standard 5.
 6. Update ADR-0018 and ADR-0028 `superseded_by` fields to reference ADR-0059. ADR-0025 `superseded_by` references ADR-0078.

- **Validation and quality gates:**
 - mypy must pass with Protocol structural checks on all InteractionProvider implementations.
 - All existing command tests must pass through the new registration path before `app/infrastructure/commands/` is retired.
 - Black, flake8, and pytest quality gates must remain green throughout migration.

- **Test strategy and acceptance criteria impact:**
 - Unit tests: Protocol conformance tests for each InteractionProvider implementation.
 - Integration tests: End-to-end command registration and dispatch through PlatformService.
 - Feature tests: HTTP route tests remain the primary test surface (Standard 4); platform-specific handler tests are supplementary.

## Change Log

- 2026-04-29: Initial draft created during ADR governance review. Consolidates ADR-0018, ADR-0025, and ADR-0028 into unified interaction architecture standard aligned with Wave 3 constraints (ADR-0055, ADR-0056, ADR-0076, ADR-0077).
- 2026-04-29: **Scope revision mandated by Platform Services Assessment.** InteractionProvider Protocol (Standard 1), Capability Matrix (Standard 2), and PlatformService facade (Standard 3) are REJECTED. ADR-0025 supersession moved to ADR-0078 (Platform Services Architecture). Title changed to "Feature Interaction Boundaries and Platform Integration Standard". Metadata updated: supersedes reduced to ADR-0018 + ADR-0028 only; ADR-0078 added to related_records; constraints revised (platform services are Category C, not Category A). Full body revision is pending - this draft retains the rejected standards with revision notices until the full rewrite is performed.

# Platform Services Architecture: Decision Assessment

**Date:** 2026-04-29  
**Scope:** Collaboration platform service architecture, outbound notification routing, and interaction boundary governance  
**Related ADRs:** ADR-0025 (superseded), ADR-0059, ADR-0078

---

## Problem

The SRE Bot supports multiple collaboration platforms (Slack, Teams, potentially others) as optional, independently-configurable interaction surfaces. ADR-0025 proposed a unified `InteractionProvider` Protocol to abstract all platforms behind a single contract. Analysis revealed this abstraction is premature, leaky, and type-unsafe — the platforms' interaction models are fundamentally incompatible at the handler signature level:

- **Slack Bolt:** functional middleware with `ack()`, `say()`, and `command` parameters
- **Teams Bot Framework:** class-based `TeamsActivityHandler` with `TurnContext`

A unified Protocol would require `Callable[..., Any]` for handler signatures, erasing all type safety. The codebase already has a working pattern in `app/packages/access/sync/interactions/` that demonstrates the correct architecture: feature-owned, platform-specific interaction handlers calling channel-agnostic ingress logic.

---

## Decisions

### 1. Concrete per-platform services — no unified abstraction

Infrastructure provides `SlackService`, `TeamsService`, etc. — concrete, typed wrappers around each platform SDK. No unified `InteractionProvider` Protocol, no `PlatformService` facade, no capability matrix.

**Rationale:**

- Platform interaction models are asymmetric (Slack ack model / Block Kit vs. Teams turn context / Adaptive Cards). A unified Protocol creates a leaky abstraction.
- Concrete services preserve platform-native type signatures, enabling mypy enforcement (ADR-0077).
- The Rule of Three applies: abstract only after three concrete implementations prove a shared pattern, not before two.

### 2. Configuration-driven platform availability

Platform availability is determined entirely by settings. If `SLACK_ENABLED=true` and required credentials are present, the `SlackService` is constructed during lifespan. Otherwise, it's skipped entirely — no service instance, no hookspec calls, no transport connection.

- Platform settings live in `app/infrastructure/configuration/integrations/`.
- Lifespan checks settings → constructs service → fires per-platform hookspecs → starts transport.
- No "provider discovery" pattern. Explicit wiring based on config.

### 3. Feature-owned interaction logic, per-platform, at each feature's pace

Each feature package owns its interaction surface. A feature may support HTTP only, HTTP + Slack, HTTP + Slack + Teams, or any combination the feature team has implemented. There is no mandate that all features support all platforms.

**Canonical structure** (proven in `app/packages/access/sync/interactions/`):

```
packages/<feature>/
├── interactions/
│   ├── ingress.py     # Channel-agnostic admission logic
│   ├── http.py        # FastAPI routes (always present)
│   ├── slack.py       # Slack handlers (if feature supports Slack)
│   └── teams.py       # Teams handlers (if feature supports Teams)
├── service.py         # Business logic (never imports from interactions/)
├── presenters.py      # Channel-specific response formatting
└── __init__.py        # Pluggy hookimpls
```

**Registration:** Features register via pluggy hookspecs. Lifespan constructs the platform service → fires hookspecs → features that implement the hookimpl register their handlers. Features that don't implement the hookimpl are unaffected.

### 4. Outbound notification routing is feature-internal

Features own their outbound notification routing. When a feature sends a notification, it determines the platform/channel based on its own configuration and calls the concrete platform service directly (e.g., `slack_service.send_message(channel, content)`). No centralized `NotificationRouter` or `NotificationChannel` Protocol — premature until 3+ features show repeated routing patterns.

### 5. Infrastructure owns transport, features own interaction

Platform service source code lives in the infrastructure layer. Features are consumers, not owners. Platform services may use simpler provider patterns than the full DI ceremony (ADR-0056) since features access them through hookspec injection rather than `Annotated[..., Depends()]` aliases.

---

## Alternatives Rejected

| Alternative | Why Rejected |
|-------------|-------------|
| **Unified InteractionProvider Protocol** (ADR-0025) | Platform interaction models are asymmetric. A unified Protocol requires `Callable[..., Any]` type erasure, defeating mypy enforcement. The Rule of Three has not been met. |
| **PlatformService facade** (centralized dispatch) | Adds indirection without value — features already receive platform services directly via hookspec injection. The facade would either pass through (no value) or abstract (type erasure). |
| **Provider discovery pattern** | Discovery adds startup complexity and non-determinism. With 2–3 platforms, explicit configuration is clearer and more predictable. |

---

## Deferred Concerns

| Concern | Trigger for Revisit |
|---------|-------------------|
| Multi-platform identity correlation | When a feature concretely runs on both Slack and Teams |
| Complex feature workflow orchestration | Next architecture cycle, starting with access package |
| Slack async mode migration (sync Bolt → async Bolt) | When app async migration reaches transport layer |
| Outbound notification abstraction | When 3+ features show repeated routing patterns |

---

## Key Principles

1. **No premature abstraction.** Concrete services until three platforms prove a shared pattern exists.
2. **Settings gate everything.** Platform availability is a config concern, not a code concern.
3. **Features own interaction, infrastructure owns transport.** Features decide how to interact; infrastructure provides reliable connections.
4. **Hookspecs for registration.** Features receive platform services via hookspec injection. No lookup, no discovery.
5. **HTTP is the primary test surface.** Always present, always testable without platform SDKs.
6. **Outbound is feature-owned.** Each feature decides where notifications go, based on its own config.
7. **Type safety preserved.** Platform-specific handler signatures remain typed. No `Callable[..., Any]` erasure.

---

## ADR Outcomes

This assessment directly informed:

- **ADR-0078** (Platform Services Architecture) — codifies Decisions 1–5 as Tier-2 standards. Supersedes ADR-0025.
- **ADR-0059** (Feature Interaction Boundaries) — revised to remove Standards 1–3 (InteractionProvider Protocol, Capability Matrix, PlatformService facade) and add standards for platform transport lifecycle and notification routing.

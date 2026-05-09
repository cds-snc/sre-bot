---
title: "Multi-Transport Architecture"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [api, architecture]
constrained_by: [layered-architecture.md, dependency-injection.md, application-lifecycle.md, plugin-registration-discovery.md, feature-package-structure.md, cross-channel-correlation.md, api-design-error-mapping.md, operation-result-pattern.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Multi-Transport Architecture

## Context and Problem Statement

The application accepts inbound work from multiple platforms — HTTP requests, chat platforms (Slack, Microsoft Teams), and potentially others (queue consumers, scheduled webhooks, future channel integrations). Each platform exposes a different native model: a different set of method categories (Slack has slash commands, events, message actions, shortcuts, view submissions; Teams has bot messages, card actions, invokes, installation updates; HTTP has route methods), a different connection lifecycle (HTTP listens for short-lived requests; Slack Socket Mode opens a persistent outbound WebSocket; Teams receives Bot Framework HTTP POSTs), a different envelope shape on the wire, and a different SDK or wire-protocol contract.

Consumers and integrators looking at the codebase need a clear, durable answer to a question that recurs every time a new platform is considered: **how do platforms compose into the application — what does the host own, what does each feature own, and where does the boundary live — without forcing heterogeneous platforms into a synthetic shared abstraction that none of them naturally fit?** The answer determines:

1. Whether each platform is integrated by reading the same composition pattern and applying it with platform-specific contents, or whether every new platform reinvents the host plumbing from scratch.
2. Where verification, authentication, and rate limiting attach — at one inbound boundary per platform that every handler benefits from, or scattered across feature handlers.
3. How a feature's `OperationResult` return travels from its service layer to a platform-specific outbound response, without leaking platform types into the service layer or business logic into the platform adapter.
4. Whether platform-specific concerns (Slack's `ack()` deadline, Teams' invoke-response shape, HTTP's `Retry-After` semantics) can be respected per platform, or whether the application's plumbing flattens them into a lossy common envelope.

**Constraints:**

- Platforms are heterogeneous in their native models. A unified `Platform` Protocol that every transport implements would either lose information at the platform boundary (forcing Slack actions, Teams card invokes, and HTTP routes through a synthetic shared shape) or grow into a lowest-common-denominator surface that none of the platforms cleanly fits. Both outcomes have been rejected by other accepted records in the corpus.
- The host is a single Python application with a defined lifespan. Connection ownership, registration order, and shutdown cleanup are concerns of the lifespan record, not of any individual platform.
- Plugin registration and discovery are owned by a separate decision (entry-points, one feature per plugin). This record does not redefine those mechanics; it specifies *which categories of hookspecs the host's plugin manager dispatches per platform*, in the abstract.
- Each feature owns its handlers per platform; cross-feature coordination uses shared infrastructure or domain events. The feature-package layout is fixed: each platform a feature handles gets its own subdirectory under the feature, with internal files mirroring the platform's native categorization.

**Non-goals:**

- This record does not pick which platforms are supported today.
- This record does not enumerate Slack hookspecs, Teams hookspecs, or any platform's hookspec catalogue. Per-platform decisions live in `transport-slack.md`, `transport-teams.md`, and any future per-platform record.
- This record does not specify per-handler implementation discipline (entry-point shape, async/sync rules, what gets injected, where logging fires inside one handler). That is owned by `feature-handler-standard.md`.
- This record does not redefine the HTTP transport. HTTP fits the pattern this record establishes; its specifics (response shape, status mapping) are already covered by `api-design-error-mapping.md` and `feature-package-structure.md`.
- This record does not redefine the `OperationResult` envelope or its closed status set; it specifies *that* the envelope passes through unchanged from feature service to platform adapter, not its contents.
- This record does not specify per-platform verification, authentication, signing, or rate-limiting semantics. It specifies that those checks attach at the platform's inbound adapter boundary; the *content* of each check belongs to that platform's record.

## Considered Options

**Option 1 — Unified `Platform` Protocol abstraction.** A single `Platform` Protocol that every transport implements; features call methods against the abstraction without knowing which platform they are talking to. Forces platforms with different native models into a synthetic shared interface. Either lossy (Slack `ack()` deadline cannot be expressed in a Teams-compatible call) or surface-bloated (the union of every platform's methods, with most calls undefined per platform).

**Option 2 — Per-platform first-class adapters with no shared pattern.** Each platform is its own implementation, fully independent. No reuse of composition pattern; each transport's host plumbing is bespoke. High maintenance cost; common concerns (correlation binding, plugin dispatch, lifespan integration) get reinvented per platform.

**Option 3 — Per-platform first-class adapters with a shared composition pattern.** Each platform retains its native model, its own SDK, its own hookspec namespace, its own infrastructure service, and its own outbound response shape. The application provides a uniform *composition pattern* — what the host owns, where verification attaches, how the plugin manager dispatches, how `OperationResult` flows through, where correlation binding fires — that every platform's integration follows with platform-specific contents. The pattern is the contract; the abstraction is not.

**Option 4 — Generic event bus with platform-flattening envelope.** All inbound events from every platform are flattened into a single `Event` envelope and routed through a generic dispatcher. Loses platform fidelity (Slack action shapes, Teams invoke responses, HTTP request scopes do not survive flattening). Breaks platform-specific contracts (Slack expects an `ack` within 3 seconds; Teams expects an invoke-response shape; HTTP requires a synchronous response).

## Decision Outcome

**Chosen: Option 3 — per-platform first-class adapters with a shared composition pattern.**

Each platform is treated as a first-class transport adapter with its own native model preserved end-to-end: the SDK, the connection lifecycle, the hookspec catalogue, the infrastructure service, and the outbound response shape are platform-shaped. The application's contribution is a *uniform composition pattern* — a set of rules every platform's integration follows — not a synthetic Protocol that pretends platforms are interchangeable. Platform-specific decisions live in per-platform records (`transport-slack.md`, `transport-teams.md`, and similar). This record specifies the pattern; the per-platform records fill in the contents.

### The composition pattern

Every platform's integration follows the same five-part composition pattern. The pattern names the slots; each platform's own ADR fills them with platform-specific content.

#### 1. Connection lifecycle owned by the host

The host's lifespan opens, monitors, and closes each platform's connection. The connection is *not* owned by features. Concretely:

- **HTTP** — the ASGI server (Uvicorn) binds the listen socket during the lifespan's transport phase; the host shuts the listener at lifespan exit.
- **Persistent WebSocket** (e.g., Slack Socket Mode) — the platform's infrastructure service opens the WebSocket during the lifespan's transport phase, monitors disconnection, and closes the connection during the shutdown phase.
- **Webhook-style HTTP** (e.g., Teams Bot Framework) — the platform's inbound adapter mounts onto the same ASGI server as the application's other HTTP routes; the lifecycle of the listener is shared with HTTP's.

The connection lifecycle for any platform is owned at the lifespan record's transport phase. Features never construct, hold, or shut down a platform's connection.

#### 2. Inbound adapter owned by the host

For each platform, the host provides an inbound adapter — a logical phase of plumbing that:

- Receives the platform's raw inbound payload (an HTTP request, a Slack envelope, a Teams activity).
- Performs platform-specific verification (HMAC signature, JWT validation, IP allow-list — whatever the platform requires).
- Establishes the per-request correlation context per the cross-channel-correlation rules.
- Resolves the inbound payload to one of the platform's hookspec calls (e.g., a Slack envelope of type `slash_command` becomes a `register_slack_command(...)` dispatch).
- Invokes the plugin manager's matching hookspec; every registered feature handler for that hookspec runs.

**Where the adapter physically lives differs by platform.** HTTP and non-HTTP platforms use different homes for the same logical role:

- **HTTP.** The application is itself an HTTP server (FastAPI/ASGI). The inbound adapter is FastAPI's request pipeline plus the application's own ASGI middleware (correlation binding, etc.). It lives in `app/server/` — the host's framework module — alongside the lifespan and the application factory. There is no separate "Slack-equivalent" runtime to host because HTTP is the application's own protocol.
- **Non-HTTP (Slack, Teams, …).** Each platform's inbound adapter is a logical phase of that platform's infrastructure service (see slot 4 below). The platform's SDK runtime — Slack's Bolt `AsyncApp` and Socket Mode handler, Teams' Bot Framework or Microsoft 365 Agents adapter — is held by the infrastructure service, configured during the lifespan's feature-activation phase, and dispatches inbound payloads through pluggy hookspecs. There is no separate `app/server/transports/<platform>/` package; the inbound adapter is internal to `app/infrastructure/<platform>/`.

In both shapes, the inbound adapter is **host-owned plumbing**, not feature code. It is the slot where verification, rate limiting, and correlation binding attach for every handler on the platform. The physical location depends on whether the platform is HTTP (a protocol the application speaks natively, hosted under `app/server/`) or a vendor-specific platform (an integration the application owns, hosted under `app/infrastructure/<platform>/` because the SDK runtime is co-located with the outbound API in one cohesive service).

#### 3. Hookspec dispatch per platform

Each platform's hookspec catalogue is platform-shaped. Slack's hookspecs reflect Slack's native categories (commands, events, actions, shortcuts, views); Teams' hookspecs reflect Teams' (messages, card actions, invokes, installation updates); HTTP's reflects route registration. There is no symmetric `register_<platform>_event` family across platforms.

The hookspec catalogue for a platform is owned by that platform's own ADR. This record establishes only that:

- Each platform contributes its own hookspecs to the host's plugin namespace.
- The plugin manager calls those hookspecs from the platform's inbound adapter (host-side), not from feature code.
- Hookspec parameters use Protocol-typed dependencies and value types (per the type-boundaries decision); they do not pass concrete vendor types or SDK objects through the plugin contract — though a platform-specific runtime context (e.g., a Bolt request object, a Teams TurnContext) may be passed when the platform's native model requires it for the handler to function. The platform's own ADR documents what its handler signatures receive.
- Adding a new hookspec to a platform's catalogue is a deliberate, review-gated change in that platform's record.

#### 4. Per-platform infrastructure service

For each non-HTTP platform, the application owns one infrastructure service at `app/infrastructure/<platform>/` (e.g., `app/infrastructure/slack/`, `app/infrastructure/teams/`). The service is the **single home** for everything platform-specific that the host owns. It:

- Holds the platform's SDK runtime (e.g., Slack's Bolt `AsyncApp` and Socket Mode handler; Teams' Bot Framework or Microsoft 365 Agents adapter). Construction happens during the lifespan's infrastructure-composition phase; lifecycle (start, monitor, close) happens during the transport and shutdown phases.
- Hosts the inbound-adapter phase described in slot 2: the SDK runtime receives inbound payloads, the service performs platform-specific verification, establishes correlation context, and dispatches into pluggy hookspecs.
- Hosts the outbound API surface: a Protocol that names the operations the application uses against the platform (`chat.postMessage`, `views.open`, send Adaptive Card, etc.). Feature handlers consume the Protocol via dependency injection; concrete vendor classes are implementation detail behind providers.
- Is wired by the application's composition root (the lifespan's infrastructure-composition phase) per the dependency-injection rules: providers return Protocol types; concrete classes never appear in feature code.
- Imports raw vendor-SDK access exclusively from `app/clients/<platform>/` per `client-module-placement.md`. The vendor-SDK package contains only authenticated client construction and primitive verification utilities; the infrastructure service composes them into the application's Protocol surface.

Each platform's infrastructure service is **independent of every other platform's**. There is no "Platform" Protocol; `SlackService`, `TeamsService`, and any future `<Platform>Service` are unrelated Protocols with unrelated method sets reflecting their respective platforms' native operations. The platform's own ADR specifies the Protocol's surface, the SDK runtime's lifecycle, and the per-platform internal organization (whether to split formatters, parsing, routing, lifecycle, and the Protocol surface across separate modules inside the service or to keep them in one).

HTTP does not have a corresponding `app/infrastructure/http/` service because HTTP is not a vendor — it is the application's own protocol. HTTP outbound calls (when a feature calls a vendor over HTTP) go through that vendor's `app/clients/<vendor>/` and corresponding infrastructure service.

#### 5. `OperationResult` handoff to the platform's outbound shape

A feature's handler runs business logic via the feature's service layer (per the layered architecture and feature-package-structure rules), which returns an `OperationResult`. The handler then converts the envelope into the platform's outbound response. The conversion:

- Lives in a small per-platform helper (typically alongside the platform's inbound adapter or within the platform's infrastructure-service surface). Each handler calls the helper rather than constructing platform-specific outbound shapes inline.
- For HTTP, the conversion is governed by the API design and error-mapping decision (`OperationStatus → HTTP status` table, `application/problem+json` for errors, `Retry-After` on `503`, etc.).
- For non-HTTP platforms, the conversion is governed by that platform's own ADR (Slack's `chat.postMessage` shape, Teams' Adaptive Card refresh, etc.). The mapping from `OperationStatus` to the platform's outbound shape is *defined* there, but follows the same principle: the envelope passes through unchanged from the service to the adapter; the adapter is the only place that constructs platform-specific outbound forms.

The envelope itself does not change shape per platform. `OperationResult` is the canonical internal contract; per-platform rendering is the only platform-specific step.

### Host / feature responsibility split

The composition pattern partitions ownership cleanly:

| Concern | Owned by |
| --- | --- |
| Platform connection lifecycle (open, monitor, close) | Host (lifespan + per-platform infrastructure service) |
| Platform-side verification (signing, JWT, etc.) | Host (per-platform inbound adapter) |
| Per-request correlation context binding | Host (per-platform inbound adapter, per `cross-channel-correlation.md`) |
| Plugin manager construction and hookspec registration | Host (lifespan plugin-discovery phase) |
| Hookspec dispatch from inbound payloads | Host (per-platform inbound adapter) |
| Outbound API client construction | Host (per-platform infrastructure service via providers) |
| Per-platform handler **functions** for each hookspec | Feature (in `app/packages/<feature>/<platform>/<category>.py`) |
| Feature business logic | Feature (in `app/packages/<feature>/service.py`) |
| Outbound response construction (the `OperationResult` → platform-shape rendering) | Per-platform helper (host-provided), called from the handler |

Verification, rate limiting, and correlation binding attach **once per platform at the inbound adapter**, not per handler. A feature's handler arrives in a context where verification has passed, the correlation `request_id` is bound to `contextvars`, and any platform-specific runtime context (Bolt request, TurnContext) is available as the hookspec's documented parameter.

### Lifespan phase placement

The composition pattern fits the application's lifespan-phase model. Each platform's pieces land in known phases:

- **Configuration phase.** Per-platform settings (`SlackSettings`, `TeamsSettings`) are loaded and validated by their providers.
- **Infrastructure-composition phase.** Each platform's infrastructure service is constructed: vendor clients (from `app/clients/<platform>/`) wired against credentials from the settings; the service Protocol is exposed via its provider.
- **Plugin discovery and registration phase.** The plugin manager registers feature plugins (per the plugin-registration-discovery decision); each platform's hookspecs are part of the host's hookspec module.
- **Feature activation phase.** Each platform's hookspecs are called by the host plumbing to register the corresponding feature handlers (HTTP routes mounted, Slack handlers attached to the Bolt app, Teams handlers attached to the Bot Framework adapter, …).
- **Transport phase.** The HTTP server binds; persistent connections (Slack Socket Mode) open; webhook listeners are ready.
- **Shutdown.** Phases reverse, with bounded budgets per the lifespan record.

### What this record does *not* prescribe

- Which platforms the application supports.
- The names of any platform's hookspecs.
- The Protocol surface of any platform's infrastructure service.
- Per-handler implementation discipline (entry-point shape, error handling within one handler, what gets logged where) — that lives in `feature-handler-standard.md`.
- The internal categorization of any platform's handlers (which lives in the platform's own ADR and is reflected in feature-package layout).
- Any specific platform's verification mechanism, SDK, connection mode, or outbound API surface.

## Consequences

**Positive:**

- A new platform integrates by reading the composition pattern and creating one new per-platform ADR plus the corresponding host plumbing slots (inbound adapter, hookspec catalogue, infrastructure service, outbound rendering helper). The pattern is the same across platforms; the contents are platform-shaped.
- Each platform's native model is preserved end to end. Slack's `ack()` deadline, Teams' invoke-response shape, HTTP's request scope all live in their respective platforms' adapters without compromise.
- Verification, rate limiting, and correlation binding live at one boundary per platform. Adding a feature handler for an existing platform does not require re-implementing verification or correlation; those have already attached at the inbound adapter.
- The `OperationResult` envelope is the durable internal contract. Feature service layers do not branch on which platform invoked them; the platform-specific rendering happens at the boundary.
- The infrastructure-service split (`SlackService`, `TeamsService`, …) reflects how the platforms actually differ: as independent vendors with independent SDKs and operations, not as variants of a synthetic abstraction.

**Tradeoffs accepted:**

- Per-platform code is not maximally DRY. A feature that supports both Slack and Teams writes two handlers, one per platform, against two different infrastructure-service Protocols. The cost is platform-fidelity duplication; the benefit is that each platform's native model survives. Forcing the two through a unified abstraction would lose information at one or both ends.
- The pattern is a contract enforced by review and by the per-platform ADRs, not a Protocol enforced by the type system. A new platform that ignored the pattern (e.g., put verification in a feature handler instead of the inbound adapter) would compile and run, and would be caught at code review. Acceptable because the alternative — encoding the pattern as Python — would itself become a unified abstraction.
- Each platform requires its own ADR. The corpus grows with the number of supported platforms. This is exactly the desired property: each platform's heterogeneity is documented where it lives.

**Risks:**

- A per-platform ADR diverges from the composition pattern (e.g., places verification at the feature handler instead of the inbound adapter). The platform's records and feature handlers become harder to reason about; common concerns drift. Mitigation: this record is the framework against which per-platform ADRs are reviewed; deviations require explicit justification.
- A future cross-platform feature wants a shared abstraction (e.g., "send a notification to whichever platform the user prefers"). The temptation to introduce a thin unifying Protocol resurfaces. Mitigation: such cross-platform abstractions live as **feature-domain types** owned by the feature, not as transport-layer types. The transport layer remains heterogeneous; the feature owns its own dispatch logic above it.
- A platform changes its native model in a way that no longer fits the slots (e.g., a future platform's verification is asymmetric to its message dispatch). Mitigation: the composition pattern's slots are clearly named; a platform that does not fit gets a separate decision in its own ADR. The pattern is a default, not a straitjacket.

## Confirmation

Compliance is verified by:

- **Repository structure.** Each supported non-HTTP platform has (a) an authenticated raw-SDK client package at `app/clients/<platform>/` per `client-module-placement.md`; (b) an infrastructure service at `app/infrastructure/<platform>/` that holds the platform's SDK runtime, hosts the inbound-adapter phase (verification, correlation binding, hookspec dispatch), and exposes the outbound Protocol surface; (c) hookspecs declared in the host's central hookspec module; (d) feature handlers under `app/packages/<feature>/<platform>/<category>.py` per the feature-package-structure rules. HTTP's inbound adapter is FastAPI's request pipeline plus the application's ASGI middleware in `app/server/`; HTTP has no `app/clients/http/` or `app/infrastructure/http/` because HTTP is the application's own protocol, not a vendor. There is no unified `app/infrastructure/platforms/` (or equivalent) holding a shared abstraction across platforms; per-platform services are independent.
- **Code review.** A PR adding a new platform includes (1) a new per-platform ADR (`transport-<platform>.md`) covering SDK choice, hookspec catalogue, verification, infrastructure-service Protocol, and outbound rendering rules; (2) the host plumbing (inbound adapter, infrastructure service, hookspecs); (3) at least one feature handler exercising the platform end to end. PRs that add platform-specific verification or outbound rendering inside feature handlers are rejected.
- **Static checks.** The import contract enforces that feature code does not import from `app/clients/<platform>/` (vendor-import rule) and that platform-specific infrastructure services are reached only through their Protocols.
- **No unified Protocol.** A grep over the codebase finds no `Platform` (or equivalent) Protocol attempting to unify Slack, Teams, and HTTP. Per-platform Protocols (`SlackService`, `TeamsService`, …) exist and are unrelated to each other.

## Source References

1. Hexagonal Architecture (Ports and Adapters) — Alistair Cockburn
   - URL: <https://alistair.cockburn.us/hexagonal-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that each external interaction (a "driving" port from a UI/transport, a "driven" port to a vendor or store) is its own adapter at the application boundary. Grounds the per-platform first-class-adapter rule and the principle that the host owns the inbound adapter (the "driving" side) per platform, while the feature consumes the outbound side via Protocols.

2. Vertical Slice Architecture — Jimmy Bogard
   - URL: <https://jimmybogard.com/vertical-slice-architecture/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that features are vertical slices — each owns its end-to-end path from transport to data — and that cross-slice coupling is minimized. Grounds the rule that each feature owns its handlers per platform inside its own package, and that cross-feature platform handlers do not exist.

3. Modular Monolith Primer — Kamil Grzybek
   - URL: <https://www.kamilgrzybek.com/blog/posts/modular-monolith-primer>
   - Accessed: 2026-05-08
   - Relevance: Establishes that modules in a modular monolith are organized around business domains and encapsulated behind well-defined interfaces. Grounds the rule that each feature is one plugin and exposes platform handlers via the plugin contract, while platform-side concerns (connection, verification) are infrastructure-layer responsibilities.

4. Composition Root — Mark Seemann
   - URL: <https://blog.ploeh.dk/2011/07/28/CompositionRoot/>
   - Accessed: 2026-05-08
   - Relevance: Establishes that wiring happens at the application's entry point, not in arbitrary consumer modules. Grounds the rule that per-platform infrastructure services are wired at the lifespan's infrastructure-composition phase, that the inbound adapter receives services and the plugin manager via providers, and that no part of the platform integration short-circuits the composition root.

5. The Twelve-Factor App — Processes (Factor VI)
   - URL: <https://12factor.net/processes>
   - Accessed: 2026-05-08
   - Relevance: Establishes that the application runs as one or more stateless processes with state externalized to backing services. Grounds the rule that platform adapters do not hold session state across requests, that domain state lives in the application's data store (not in conversation state, not in adapter memory), and that re-creating a process produces an equivalent integration.

6. Architecture Patterns with Python (Cosmic Python), Chapter 13 — Bob Gregory and Harry Percival
   - URL: <https://www.cosmicpython.com/book/chapter_13_dependency_injection.html>
   - Accessed: 2026-05-08
   - Relevance: Demonstrates the composition-root / bootstrap pattern in Python: collect adapters, build the messagebus / dispatcher, expose configured handlers to the entry points. Grounds the rule that the host's plumbing assembles each platform's inbound adapter, infrastructure service, and plugin manager once at boot, and that handlers run in the configured runtime — never construct dependencies themselves.

## Change Log

- 2026-05-08: Created as placeholder.
- 2026-05-08: Scope reassessed and clarified. The record is **pattern-only and transport-agnostic**: it does not prescribe a unified platform abstraction, does not enumerate per-platform hookspec catalogues, and does not pick which platforms are supported. Each platform's hookspec catalogue, SDK choice, connection lifecycle, and infrastructure-service shape are owned by the platform's own ADR (`transport-slack.md`, `transport-teams.md`). HTTP is covered by `api-design-error-mapping.md` and `feature-package-structure.md` and does not need a dedicated platform record. The constrained-by list expanded to reflect the now-accepted records this pattern depends on: `application-lifecycle.md`, `plugin-registration-discovery.md`, `feature-package-structure.md`, `cross-channel-correlation.md`, `api-design-error-mapping.md`, `operation-result-pattern.md`.
- 2026-05-08: Finalized. Establishes a five-part composition pattern that every platform integration follows: (1) connection lifecycle owned by the host's lifespan; (2) inbound adapter owned by the host (verification, correlation binding, hookspec dispatch); (3) per-platform hookspec catalogue with platform-shaped names — no unified `register_<platform>_event` family; (4) per-platform infrastructure service exposing a platform-specific Protocol — no synthetic unifying Protocol; (5) `OperationResult` handoff via a per-platform rendering helper. Pins the host / feature responsibility split: connection, verification, correlation, plugin dispatch, and outbound API construction are host-owned; per-platform handler functions and feature business logic are feature-owned. The record explicitly does not prescribe which platforms are supported, any platform's hookspec names, any platform's Protocol surface, per-handler implementation discipline, or per-platform verification mechanisms — those live in per-platform records and in `feature-handler-standard.md`.
- 2026-05-08: Removed the spurious `app/server/transports/<platform>/` package introduced earlier. The "inbound adapter" is a logical phase of plumbing whose physical location depends on the platform: HTTP's inbound adapter is FastAPI's request pipeline plus ASGI middleware in `app/server/`; non-HTTP platforms' inbound adapter is a phase of that platform's infrastructure service in `app/infrastructure/<platform>/` (the SDK runtime — Bolt `AsyncApp`, Bot Framework adapter — is held by the service alongside the outbound Protocol surface). HTTP is the application's own protocol and has no `app/clients/http/` or `app/infrastructure/http/`. The Confirmation section's repository-structure rule was rewritten to reflect this; the per-platform infrastructure-service slot was strengthened to name what the service holds (SDK runtime, inbound dispatch, outbound Protocol) and to require that vendor-SDK access comes only from `app/clients/<platform>/` per `client-module-placement.md`.

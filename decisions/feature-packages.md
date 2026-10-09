---
status: Accepted
date: 2026-07-06
applies: target
scope: The one package shape for features, capabilities and their subdomains, plus handler discipline — the record most contributors work from.
---

# Feature Packages

## Context

Features live in `app/packages/` today; `features/` and `capabilities/` do not exist yet ([plugin-architecture.md](plugin-architecture.md)). An earlier layout record was a closed filename list that banned names the code needed (no slot for persistence, no `locales/`), so this record was reconciled with the shipped shape. Nothing enforces it, and the shipped packages have drifted:
- Three packages (`geolocate`, `rant`, `user_rotations`) put Slack handlers in `platforms/`, and `access` puts them in `interactions/`, instead of `entrypoints/`; `geolocate` also has `routes.py`, `oncall_sync` has `ports.py`, and `access/sync` has many extra top-level modules (`application.py`, `job_runner.py`, `presenters.py` and others).
- Handler files in six packages import `integrations.slack` directly, `oncall_sync/providers.py` imports `integrations.slack.settings`, and the `incident/scribe` service imports `integrations.openai`.
- `access/sync` handlers are synchronous `def` functions.
- `access/request` and `access/sync` publish and handle domain events through the blinker-backed `infrastructure.events` dispatcher.
- `access/common` reads runtime-config files and holds a cached provider, although `common/` is meant to do no I/O.

`packages/access/` and `packages/incident/` are umbrellas with empty `__init__.py` files. No entry points are declared yet.

## Decision

### Layout

Features, capabilities and subdomains all use this one shape. Features live in `app/features/<feature>/`, capabilities in `app/capabilities/<capability>/`.

```text
app/features/<feature>/
├── __init__.py        # hookimpls: the package's registration surface
├── README.md          # purpose; for a capability, its classification and feature consumers
├── settings.py        # the package's typed settings slice (optional)
├── api.py             # capabilities only: public Protocol, domain types, provider function
├── hookspecs.py       # capabilities only: the extension points it owns (optional)
├── service.py         # business logic; the only orchestrator
├── domain.py          # frozen dataclasses, enums, invariants (optional)
├── schemas.py         # Pydantic models at trust boundaries (optional)
├── store.py           # persistence through the storage contract (optional)
├── providers.py       # local wiring: builds services from registry-provided contracts (optional)
├── adapters/          # Path B adapters: the ONLY files importing app.integrations
├── entrypoints/       # inbound handlers: slack.py, teams.py, http.py for the package's API
└── locales/           # EN/FR catalogues (see i18n.md)
```

A package generator creates new packages in this shape. A CI shape check rejects any top-level name outside the table; the table grows by amending this record. A complex feature holds subdomains, each shaped like the table above.

### Complex features: an umbrella directory, never a flat prefix

A feature too large for one `service.py` becomes an umbrella: one directory per bounded context, holding its subdomains, an optional `core/` and `common/`. `access/{catalog,request,sync}` with `access/common` is the shipped instance.

```text
app/features/<feature>/
├── __init__.py      # EMPTY: namespace only, no hookimpls, no re-exports, no entry point
├── <subdomain>/     # shaped like the layout table above; each is a plugin
├── core/            # optional: what every subdomain works on; may do I/O; public surface is api.py
└── common/          # shared kernel: domain vocabulary and the settings tree, no I/O
```

Imports run one way: subdomains → `core/` → `common/`. Six rules keep the umbrella from becoming a god package:

1. **The umbrella holds no code.** The plugin unit stays the subdomain, so registration granularity, enablement blast radius and strangler increments match a flat layout. [plugins.md](plugins.md) permits subdomain plugins.
2. **A subdomain is a unit you would enable, own or delete on its own.** It groups the use cases that are switched on together. One command is not a subdomain: two commands that are never enabled separately are two handlers and two service functions in one subdomain. Inside a subdomain, modules import each other freely.
3. **Subdomains never import each other.** A disabled subdomain registers nothing ([plugins.md](plugins.md)), so a sibling that imported it would call into a plugin that was never wired. What two subdomains share moves down into `core/` or `common/`, or out to a capability when its vocabulary is feature-free ([plugin-architecture.md](plugin-architecture.md)).
4. **`core/` holds what every subdomain works on, and may do I/O.** That is the feature's record and its store, purpose-shaped interfaces for the resources the record references (an incident's conversation, its report) with one adapter per system, and the checks every subdomain applies (which incident does this command refer to, and may it still be changed). An item enters `core/` when it is the feature's record itself or has two or more subdomain consumers. `core/` uses the layout table without `entrypoints/`: it is not a plugin, so it has no hookimpls, no entry point and no enablement key. Subdomains import only `core/api.py` (Protocols, domain types, provider functions), as they would a capability's. Most of an umbrella's `adapters/` live here, so a subdomain often has none.
5. **`common/` admits only types and values with two or more subdomain consumers and no I/O.** Once an item there calls a backing service, it moves to `core/`.
6. **Entry-point names carry the dotted prefix**: `"access.sync" = "features.access.sync"`, never `"sync"`. Entry-point names form a flat registry per group, so a bare last component collides the day a second feature grows a `sync`. Django hits the same wall: `AppConfig.label` defaults to the last component of the dotted path and must be unique project-wide.

Independent siblings over a shared lower layer that owns persistence, reached through `api.py`, is the shape Kraken and Open edX enforce with import-linter ([Kraken's layered monolith](https://blog.europython.eu/kraken-technologies-how-we-organize-our-very-large-pythonmonolith/), [OEP-49](https://docs.openedx.org/projects/openedx-proposals/en/latest/best-practices/oep-0049-django-app-patterns.html)). Free imports between siblings were rejected: they defeat per-subdomain enablement and allow import cycles.

**Flat `<feature>_<subfeature>` naming is rejected.** It is the convention for separately distributed components. Separate distributions do not enforce import boundaries by themselves: uv [can't ensure](https://docs.astral.sh/uv/concepts/projects/workspaces/) that one workspace member doesn't import another member's dependencies. We need import contracts either way, and we ship one wheel. Within that wheel, flat naming causes two problems:

- It declares subdomains to be separate features. Shared feature vocabulary then breaks "features never import each other", forcing duplication or a premature capability.
- No package groups a feature's subdomains. import-linter wildcards replace whole module names only (`features.incident_*` is not valid), and `exhaustive` requires `containers`, so the per-feature contract in Checks cannot be written.

Nesting stops at two levels: `features/<feature>/<subdomain>/` (or `core/`, `common/`), no deeper.

### Handler discipline

A handler (any platform) does five things and nothing else: receive the platform input → translate it to typed values → call **one** service method → receive `OperationResult` → render through the platform's shared renderer. Handlers are `async def`. Handlers never contain business logic, vendor SDK calls, state, or try/except around business outcomes (services return results; unexpected exceptions propagate to the central handler, which logs them). The one permitted try/except is the transport's shared helper around platform sends (`say`/`respond`), per [transport-slack.md](transport-slack.md). A handler past ~30 lines is a sign that logic is leaking out of `service.py`.

### Dependency rules

- A package imports only `contracts`, capabilities' `api.py` and its own modules; an umbrella subdomain also imports its feature's `core/api.py` and `common/`. Only `adapters/` may import `integrations`. A capability may also import a lower capability's `api.py` in the declared order. Nothing imports `infrastructure/` or `server/`.
- Services depend on Protocols through their constructor. `providers.py` builds them from contracts the host registers in the registry; services never look a dependency up mid-method. Domain code depends on nothing outside the package and the standard library.
- **A Protocol is named for its role, never for the pattern.** `UserIdentityLookup`, `IdempotencyStore`, `DirectoryProvider`, `SlackCommandRegistrar`, `SlackReplySender`: the name says what the interface does. `Port` stays out of class, function and variable names, and prose says "interface"; "port" is kept only where a record discusses ports-and-adapters itself, because elsewhere it reads as a network port.
- **Features never import each other.** A need two features share becomes a capability, when it passes [plugin-architecture.md](plugin-architecture.md)'s three tests. A need two subdomains of one feature share goes to that feature's `core/`.
- **Reactions go through extension points.** A feature that reacts to something another plugin does registers a strategy, at startup, into an extension point owned by the capability where it happens. A reaction that must reach every replica or survive a restart goes through the queue contract.
- Worked example: the approval-workflow engine inside `access/request` graduates to `capabilities/approvals/`, because SaaS-subscription and AI-key approvals need it too ([approvals.md](approvals.md)). The access-specific policy and IDP/sync effect stay in the access feature as strategies registered into the engine.
- Platform helpers (parser, renderer) come from the transport contract; otherwise handlers use the SDK's documented objects handed to them by the runtime, and no shared helper wraps the SDK ([platform-transports.md](platform-transports.md)). No handler imports `integrations/`.

## Consequences

- A new contributor runs the generator and is productive in an afternoon; that is this record's success criterion. For a complex feature, the reference is `access/`.
- Features and capabilities share one shape, so moving a need from a feature into a capability changes paths and imports, not structure.
- Subdomains stay small: a handler, a service and little else. Adapters, wiring and the record are written once per feature, in `core/`.
- Cost, accepted: every current package moves and renames `platforms/` and `interactions/` to `entrypoints/`. These are import-path and entry-point-name changes with no runtime surface change.
- Cost, accepted: `incident_draft` and `incident_summary` are reshaped, not just moved. They become use cases of one incident subdomain over `core/`, and the I/O in `access/common` moves to `access/core/`.
- Risk: `core/` becomes the feature's grab-bag. Mitigation: the admission test in rule 4, `api.py` as its only public surface, and no entry points.

## Checks

- CI shape check: every package under `features/` and `capabilities/` uses only names from the layout table.
- import-linter `independence` across `features/`; `integrations` imported only under `adapters/`; no package imports `infrastructure` or `server` ([plugin-architecture.md](plugin-architecture.md)).
- Umbrella `__init__.py` files are empty and have no entry point; every subdomain entry-point name is `<feature>.<subdomain>` (grep and review).
- Each umbrella has an import-linter `layers` contract with `containers = ["features.<feature>"]`, subdomains as pipe-separated independent siblings above `core` (when present) above `common`, and `exhaustive = true`, so an undeclared subdirectory fails CI.
- CI shape check: an umbrella's `core/` has no `entrypoints/`, no hookimpls and no entry point; `common/` imports no `adapters/`, store or provider module.
- Subdomains import `core/` only through `core/api.py` (an import-linter `forbidden` contract on `core`'s other modules; review until it exists).
- Handler tests stub the service and assert rendering; service tests use Protocol fakes. Handlers are `async def` (review).

## Migration

Tickets: TASK-18 (import-linter contracts), TASK-38 (incident), TASK-124 (package moves, including the `access/core/` split), TASK-135 (`incident_draft` and `incident_summary` reshaped onto `core/`), and the generator and shape check listed in [plugin-architecture.md](plugin-architecture.md)'s Migration.

Tolerated until then:
- packages in `app/packages/`, with no generator and no shape check;
- `platforms/` directories and the extra top-level modules listed in Context;
- `integrations` imports outside `adapters/`: `integrations.slack` in handler files and `oncall_sync/providers.py`, and `integrations.openai` in the `incident/scribe` service;
- `providers.py` files that import `infrastructure` providers instead of resolving contracts from the registry;
- the runtime-config loaders and cached provider in `access/common`;
- synchronous handlers in `access/sync/interactions/`;
- the `infrastructure.events` dispatcher in `access/request` and `access/sync`;
- the approval engine inside `access/request` until TASK-60 moves it.

**Changes:**
- 2026-09-03: added the umbrella rule for complex features.
- 2026-09-10: corrected the rationale for rejecting flat naming.
- 2026-09-24: one generator-enforced shape for features and capabilities under the plugin-architecture layers, with reactions through extension points instead of domain events; inbound handlers live in `entrypoints/`.
- 2026-10-01: umbrellas gain an optional `core/` layer that may do I/O, imported through `api.py`; a subdomain is an enablement unit, not a command; sibling independence is kept.
- 2026-10-02: Protocols are named for their role, never with a `Port` suffix, and prose says "interface" (TASK-136).
- 2026-10-02: `incident_draft` and `incident_summary` are now the `scribe` subdomain of `packages/incident/`, reading the transcript through `core/` (TASK-135); Context and the tolerated list no longer name them as separate packages.
- 2026-10-09: `incident/scribe` Slack handlers merged into `entrypoints/` (TASK-144.1); Context no longer lists it among the packages with `platforms/`.

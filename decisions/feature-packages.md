---
status: Accepted
date: 2026-07-06
applies: target
scope: The one package shape for features, capabilities and their subdomains, plus handler discipline — the record most contributors work from.
---

# Feature Packages

## Context

Features live in `app/packages/` today; `features/` and `capabilities/` do not exist yet ([plugin-architecture.md](plugin-architecture.md)). An earlier layout record was a closed filename list that banned names the code needed (no slot for persistence, no `locales/`), so this record was reconciled with the shipped shape. Nothing enforces it, and the shipped packages have drifted:
- Five packages (`geolocate`, `incident_draft`, `incident_summary`, `rant`, `user_rotations`) put Slack handlers in `platforms/`, and `access` puts them in `interactions/`, instead of `entrypoints/`; `geolocate` also has `routes.py`, `oncall_sync` has `ports.py`, and `access/sync` has many extra top-level modules (`application.py`, `job_runner.py`, `presenters.py` and others).
- Handler files in six packages import `integrations.slack` directly, `oncall_sync/providers.py` imports `integrations.slack.settings`, and the `incident_draft` and `incident_summary` services import `integrations.openai`.
- `access/sync` handlers are synchronous `def` functions.
- `access/request` and `access/sync` publish and handle domain events through the blinker-backed `infrastructure.events` dispatcher.
- `incident_draft` and `incident_summary` sit outside the `packages/incident/` umbrella.

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

A feature too large for one `service.py` becomes an umbrella: one directory per bounded context, one subdirectory per subdomain, plus `common/`. `access/{catalog,request,sync}` with `access/common` is the shipped instance.

```text
app/features/<feature>/
├── __init__.py      # EMPTY: namespace only, no hookimpls, no re-exports, no entry point
├── common/          # shared kernel: domain vocabulary and the settings tree, no I/O
└── <subdomain>/     # shaped like the layout table above; each is a plugin
```

Three rules keep the umbrella from becoming a god package:

1. **The umbrella holds no code.** The plugin unit stays the subdomain, so registration granularity, enablement blast radius and strangler increments match a flat layout. [plugins.md](plugins.md) permits subdomain plugins.
2. **`common/` admits only types and values with two or more subdomain consumers and no I/O.** Once an item there calls a backing service, it is either a subdomain service or a capability candidate ([plugin-architecture.md](plugin-architecture.md)). `common/` makes that promotion visible; it does not prevent it.
3. **Entry-point names carry the dotted prefix**: `"incident.draft" = "features.incident.draft"`, never `"draft"`. Entry-point names form a flat registry per group, so a bare last component collides the day a second feature grows a `summary`. Django hits the same wall: `AppConfig.label` defaults to the last component of the dotted path and must be unique project-wide.

**Flat `<feature>_<subfeature>` naming is rejected.** It is the convention for separately distributed components. Separate distributions do not enforce import boundaries by themselves: uv [can't ensure](https://docs.astral.sh/uv/concepts/projects/workspaces/) that one workspace member doesn't import another member's dependencies. We need import contracts either way, and we ship one wheel. Within that wheel, flat naming causes two problems:

- It declares subdomains to be separate features. Shared feature vocabulary then breaks "features never import each other", forcing duplication or a premature capability.
- No package groups a feature's subdomains. import-linter wildcards replace whole module names only (`features.incident_*` is not valid), and `exhaustive` requires `containers`, so the per-feature contract in Checks cannot be written.

Nesting stops at two levels: `features/<feature>/<subdomain>/`, no deeper.

### Handler discipline

A handler (any platform) does five things and nothing else: receive the platform input → translate it to typed values → call **one** service method → receive `OperationResult` → render through the platform's shared renderer. Handlers are `async def`. Handlers never contain business logic, vendor SDK calls, state, or try/except around business outcomes (services return results; unexpected exceptions propagate to the central handler, which logs them). The one permitted try/except is the transport's shared helper around platform sends (`say`/`respond`), per [transport-slack.md](transport-slack.md). A handler past ~30 lines is a sign that logic is leaking out of `service.py`.

### Dependency rules

- A package imports only `contracts`, capabilities' `api.py` and its own modules. Only `adapters/` may import `integrations`. A capability may also import a lower capability's `api.py` in the declared order. Nothing imports `infrastructure/` or `server/`.
- Services depend on Protocols through their constructor. `providers.py` builds them from contracts the host registers in the registry; services never look a dependency up mid-method. Domain code depends on nothing outside the package and the standard library.
- **Features never import each other.** A need two features share becomes a capability, when it passes [plugin-architecture.md](plugin-architecture.md)'s three tests.
- **Reactions go through extension points.** A feature that reacts to something another plugin does registers a strategy, at startup, into an extension point owned by the capability where it happens. A reaction that must reach every replica or survive a restart goes through the queue contract.
- Worked example: the approval-workflow engine inside `access/request` graduates to `capabilities/approvals/`, because SaaS-subscription and AI-key approvals need it too ([approvals.md](approvals.md)). The access-specific policy and IDP/sync effect stay in the access feature as strategies registered into the engine.
- Platform helpers (parser, renderer) come from the transport contract; otherwise handlers use the SDK's documented objects handed to them by the runtime, and no shared helper wraps the SDK ([platform-transports.md](platform-transports.md)). No handler imports `integrations/`.

## Consequences

- A new contributor runs the generator and is productive in an afternoon; that is this record's success criterion. For a complex feature, the reference is `access/`.
- Features and capabilities share one shape, so moving a need from a feature into a capability changes paths and imports, not structure.
- Cost, accepted: every current package moves and renames `platforms/` and `interactions/` to `entrypoints/`, and `incident_draft` and `incident_summary` move under the incident umbrella. These are import-path and entry-point-name changes with no runtime surface change.

## Checks

- CI shape check: every package under `features/` and `capabilities/` uses only names from the layout table.
- import-linter `independence` across `features/`; `integrations` imported only under `adapters/`; no package imports `infrastructure` or `server` ([plugin-architecture.md](plugin-architecture.md)).
- Umbrella `__init__.py` files are empty and have no entry point; every subdomain entry-point name is `<feature>.<subdomain>` (grep and review).
- Each umbrella has an import-linter `layers` contract with `containers = ["features.<feature>"]`, subdomains as pipe-separated independent siblings above `common`, and `exhaustive = true`, so an undeclared subdirectory fails CI.
- Handler tests stub the service and assert rendering; service tests use Protocol fakes. Handlers are `async def` (review).

## Migration

Tickets: TASK-18 (import-linter contracts), TASK-38 (incident, including the `incident_draft` and `incident_summary` relocation), and the generator, shape check and package moves listed in [plugin-architecture.md](plugin-architecture.md)'s Migration.

Tolerated until then:
- packages in `app/packages/`, with no generator and no shape check;
- `platforms/` directories and the extra top-level modules listed in Context;
- `integrations` imports outside `adapters/`: `integrations.slack` in handler files and `oncall_sync/providers.py`, and `integrations.openai` in the `incident_draft` and `incident_summary` services;
- `providers.py` files that import `infrastructure` providers instead of resolving contracts from the registry;
- synchronous handlers in `access/sync/interactions/`;
- the `infrastructure.events` dispatcher in `access/request` and `access/sync`;
- the approval engine inside `access/request` until TASK-60 moves it.

**Changes:**
- 2026-09-03: added the umbrella rule for complex features.
- 2026-09-10: corrected the rationale for rejecting flat naming.
- 2026-09-24: one generator-enforced shape for features and capabilities under the plugin-architecture layers, with reactions through extension points instead of domain events; inbound handlers live in `entrypoints/`.

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

`packages/access/` and `features/incident/` are umbrellas with empty `__init__.py` files. No entry points are declared yet.

## Decision

### Layout

Features, capabilities and subdomains all use this one shape. Features live in `app/features/<feature>/`, capabilities in `app/capabilities/<capability>/`.

```text
app/features/<feature>/
├── __init__.py        # hookimpls: the package's registration surface, register_requirements first
├── README.md          # purpose; for a capability, its classification and feature consumers
├── settings.py        # the package's typed settings slice (optional)
├── api.py             # capabilities only: public Protocol, domain types, provider function
├── hookspecs.py       # capabilities only: the extension points it owns (optional)
├── service.py         # business logic; the only orchestrator (optional for a capability)
├── interfaces.py      # the Protocols service.py depends on, implemented in adapters/ (optional)
├── domain.py          # frozen dataclasses, enums, invariants and pure rules over them (optional)
├── schemas.py         # Pydantic models at trust boundaries (optional)
├── store.py           # persistence through the records contract (optional)
├── providers.py       # local wiring: builds services from registry-provided contracts (optional)
├── plugin.py          # the hookimpls, when the host reads the package's settings before plugins load; the entry point names it (optional)
├── adapters/          # Path B adapters: the ONLY files importing app.integrations (optional)
├── entrypoints/       # inbound handlers: slack.py, teams.py, http.py for the package's API (optional for a capability)
└── locales/           # EN/FR catalogues, see i18n.md (optional)
```

A package's `__init__.py` declares each vendor or capability it cannot run without in a `register_requirements` hookimpl that returns `Requirement` values, and declares none it uses optionally ([plugins.md](plugins.md)); the generator's template includes the hook, returning an empty list. `service.py` and `domain.py` may each grow into a package of the same name (`service/`, `domain/`) when one module no longer reads well, as Django lets `models.py` become `models/`; nothing else gains a sibling module. A `service/` package holds one module per use case, named in the domain's words as rule 2 names subdomains (`incident/comms`: `draft`, `form`, `approval`, `publication`, `history`), and keeps the helpers they share private inside it; its `__init__.py` re-exports nothing. A pure rule several adapters or surfaces apply, such as rendering a status update through a comms profile, lives in `domain.py`, never inside one adapter: adapters do not import each other. A package generator (`make new-package`) creates new packages in this shape. A CI shape check rejects any top-level name outside the table; the table grows by amending this record. `app/bin/package_layout.toml` is the table's machine copy, with each kind's required, optional and forbidden entries: the shape check and the generator both read it. The generator writes each kind's required entries, and an optional entry only when asked by an option flag named for it (`--hookspecs`, `--service`, `--entrypoints`, `--interfaces`, `--adapters`, `--settings`), never an empty placeholder; `--interfaces` needs `--service` on a capability, and an option the kind does not list, or an option given to umbrella or promote, is refused with nothing written. A capability requires only `__init__.py`, `README.md` and `api.py`: a driven-port capability is its `api.py` Protocol and the adapters implementing it, and the shape check cannot see which Protocol a capability implements. Which config files a kind edits (entry points, contracts, enablement keys) is generator behaviour, not layout, and stays in code. Amend this record and the manifest together; a drift test fails when their names differ. A complex feature holds subdomains, each shaped like the table above.

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
2. **A subdomain is a purpose in the feature's process, named in the domain's words.** It passes three tests: (a) it has a distinct audience or outcome in that process; (b) its name is the domain's word for that purpose; (c) it is never named for a mechanism or for the capability it uses. A subdomain for everything that calls the text-generation capability is a mechanism bucket, the same mistake as a `database` subdomain. One command is not a subdomain: it joins the subdomain whose users need it at that point in the process, so two commands that are never enabled separately are two handlers and two service functions in one subdomain. Inside a subdomain, modules import each other freely.
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
- **A Protocol is named for its role, never for the pattern.** `UserIdentityLookup`, `ConditionalWriteStore`, `DirectoryProvider`, `SlackCommandRegistrar`, `SlackReplySender`: the name says what the interface does. `Port` stays out of class, function and variable names, and prose says "interface"; "port" is kept only where a record discusses ports-and-adapters itself, because elsewhere it reads as a network port.
- **Features never import each other.** A need two features share becomes a capability, when it passes [plugin-architecture.md](plugin-architecture.md)'s three tests. A need two subdomains of one feature share goes to that feature's `core/`.
- **Reactions go through extension points.** A feature that reacts to something another plugin does registers a strategy, at startup, into an extension point owned by the capability where it happens. A reaction that must reach every replica or survive a restart goes through the queue contract.
- Worked example: the approval-workflow engine inside `access/request` graduates to `capabilities/approvals/`, because SaaS-subscription and AI-key approvals need it too ([approvals.md](approvals.md)). The access-specific policy and IDP/sync effect stay in the access feature as strategies registered into the engine.
- Platform helpers (parser, renderer) come from the transport contract; otherwise handlers use the SDK's documented objects handed to them by the runtime, and no shared helper wraps the SDK ([platform-transports.md](platform-transports.md)). No handler imports `integrations/`.

## Consequences

- A new contributor runs the generator (`make new-package`, `bin/new_package.py`, templates in `bin/package_templates/`) and is productive in an afternoon; that is this record's success criterion. For a complex feature, the reference is `access/`.
- Features and capabilities share one shape, so moving a need from a feature into a capability changes paths and imports, not structure.
- Subdomains stay small: a handler, a service and little else. Adapters, wiring and the record are written once per feature, in `core/`.
- Cost, accepted: every current package moves and renames `platforms/` and `interactions/` to `entrypoints/`. These are import-path and entry-point-name changes with no runtime surface change.
- Cost, accepted: `incident_draft` and `incident_summary` are reshaped, not just moved: first into one `scribe` subdomain by mechanism (TASK-135), then into the `postmortem` and `response` subdomains by purpose (TASK-145). The I/O in `access/common` moves to `access/core/`.
- Risk: `core/` becomes the feature's grab-bag. Mitigation: the admission test in rule 4, `api.py` as its only public surface, and no entry points.

## Checks

- CI shape check (`bin/check_package_shape.py`, `make check-package-shape`; known violations in `bin/baselines/package_shape.txt`, each naming the task that removes it): every package under `features/` and `capabilities/` uses only names from the layout table, read from `bin/package_layout.toml`; `plugin.py` only where an entry point names it.
- Ruff `INP001` (app code; `tests/` exempt): every Python directory is a package with an `__init__.py`.
- import-linter `independence` across `features/`; `integrations` imported only under `adapters/`; no package imports `infrastructure` or `server` ([plugin-architecture.md](plugin-architecture.md)).
- CI shape check: umbrella `__init__.py` files are empty and have no entry point; every subdomain entry-point name is `<feature>.<subdomain>`.
- Each umbrella has an import-linter `layers` contract with `containers = ["features.<feature>"]`, subdomains as pipe-separated independent siblings above `core` (when present) above `common`, and `exhaustive = true`, so an undeclared subdirectory fails CI.
- CI shape check: an umbrella's `core/` has no `entrypoints/`, no hookimpls and no entry point; `common/` imports no `adapters/`, store or provider module.
- Subdomains import `core/` only through `core/api.py` (an import-linter `forbidden` contract on `core`'s other modules; review until it exists).
- Handler tests stub the service and assert rendering; service tests use Protocol fakes. Handlers are `async def` (review).

## Migration

Tickets: TASK-18 (import-linter contracts), TASK-145 (incident, replacing TASK-38), TASK-146 (on-call), TASK-124 (package moves, including the `access/core/` split), and the generator and shape check listed in [plugin-architecture.md](plugin-architecture.md)'s Migration.

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
- 2026-10-09: rule 2 becomes the purpose test (audience or outcome, the domain's word, never a mechanism); TASK-135 had merged two packages by mechanism and this rule would have caught it (TASK-145).
- 2026-10-13: the storage contract is the records contract (`RecordStore`, TASK-27.4).
- 2026-10-29: a package states the vendors and capabilities it requires in a `register_requirements` hookimpl, per plugins.md; the generator template includes it (TASK-172).
- 2026-10-29: `register_requirements` returns `Requirement` declarations the host resolves, per plugins.md (TASK-175 planning); the generator template returns an empty list.
- 2026-11-06: the layout table gains `interfaces.py` (a package's own Protocols; `ports.py` was the drift) and `plugin.py` (per plugins.md 2026-11-04); `service.py` and `domain.py` may grow into packages; the shape check (TASK-114.1) also enforces the umbrella and dotted-name rules, with a ratcheting baseline (TASK-114 planning, human).
- 2026-11-06: the generator (`make new-package`) creates a feature, capability, umbrella, subdomain, `core/` or `common/` in this shape, with its entry point, protected-plugins and independence or umbrella contract entries and its enablement key; a capability takes its classification and at least one existing feature consumer, so it passes the shape check from the start (TASK-114.2).
- 2026-11-06: `make new-package ARGS="promote <feature> --subdomain <name>"` turns a flat feature into an umbrella in place, keeping its name: its code becomes the first subdomain, `settings.py` moves to `common/` with its table and environment names unchanged, references are rewritten, and the entry point and enablement keys become `<feature>.<subdomain>`; generated `core/` and `common/` get a README (TASK-114.2).
- 2026-11-06: a `service/` package splits one module per use case in the domain's words with private shared helpers and no re-exports; `domain.py` also holds pure rules over its types, and a pure rule several adapters apply lives there, never in one adapter (TASK-186, which reshaped `incident/comms` into the table and removed its package-shape baseline entries).
- 2026-11-09: `app/bin/package_layout.toml` becomes the layout table's machine copy (kinds with required, optional and forbidden entries; `extends` between kinds), read by the shape check through `bin/package_layout.py`, with a drift test against this table; ruff `INP001` is enabled for app code (TASK-114.3).
- 2026-11-10: the generator reads the manifest and emits optional entries only on request; a capability requires only `__init__.py`, `README.md` and `api.py`; `service.py`, `entrypoints/`, `adapters/` and `locales/` are optional; options outside a kind, and any option on umbrella or promote, are refused (TASK-114.4).

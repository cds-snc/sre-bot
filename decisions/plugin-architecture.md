---
status: Accepted
date: 2026-09-24
applies: target
scope: The app's layers (host, contracts, features, capabilities, infrastructure, integrations), what each holds and what each may import.
---

# Plugin Architecture

## Context

The former three-tier model (`packages/`, `infrastructure/`, `integrations/`) sorted code by one question: how close is it to a vendor? That put three different kinds of code in `app/infrastructure/`:
- hosting adapters: `storage`, `idempotency`, `resilience`, logging setup;
- framework services that features plug into: `plugins`, `i18n`, `security`, `events`, `audit`, and the planned `approvals` engine ([approvals.md](approvals.md));
- workplace systems: `directory`, `drive`, `spreadsheets` ([workplace-systems.md](workplace-systems.md)).

A draft capability-packages record added a shared business layer inside `packages/`, but its tests required organization policy, which excluded a generic engine such as approvals. So a domain-agnostic engine that features extend had no home.

The app is a platform: other teams add features to it, today in this repository. They need a small, stable surface to build on. Hosting has to become portable across clouds, and features must not see which cloud they run on.

Established practice separates these concerns:
- Backstage's backend has a plugin API package (interfaces and extension points, no implementations), default implementations that only the deployment wires in, and plugins that never import each other's implementations. Its shared engines (permissions, notifications, scaffolder) are plugins that take strategies through extension points ([architecture](https://backstage.io/docs/backend-system/architecture/index), [extension points](https://backstage.io/docs/backend-system/architecture/extension-points)).
- An interface shared by many consumers belongs in a neutral package that both the consumer and the implementation depend on ([Separated Interface](https://martinfowler.com/eaaCatalog/separatedInterface.html)).

Current state:
- Features import `infrastructure` Protocols and provider functions directly ([dependency-injection.md](dependency-injection.md)). `infrastructure.operations` is the only declared shared kernel.
- No entry points are declared yet; plugin discovery walks `app/packages/`. No module path or class name is stored as data, so moving a package changes imports only.
- Legacy `modules/`, `jobs/` and `api/` import `packages/`, mostly `packages/aws_platform`.
- [feature-packages.md](feature-packages.md) defines a package shape, but nothing enforces it, and the legacy modules predate it. `modules/sre/` and `modules/aws/` became grab-bags, and `modules/incident/` is built around Google Workspace resources rather than around the incident itself.

## Decision

**Six layers under `app/`. Each may import only what its row allows.**

| Layer | Holds | May import |
| --- | --- | --- |
| `server/` | The host: composition root, lifespan, plugin manager, transport runtimes (Bolt), and the framework services' implementations (i18n, auth, logging setup) | everything |
| `features/` | Business feature plugins | `contracts`, capabilities' `api.py`; its `adapters/` may import `integrations` |
| `capabilities/` | Engines and shared business capabilities (approvals, notifications, audit trail, people and accounts, workplace systems) | `contracts`, lower capabilities' `api.py`; its `adapters/` may import `integrations` |
| `infrastructure/` | Hosting implementations of `contracts` Protocols | `contracts`, `integrations` |
| `integrations/` | Vendor clients ([outbound-clients.md](outbound-clients.md), unchanged) | `contracts` (shared types only) |
| `contracts/` | The public plugin API | the standard library, `typing` and `pluggy` markers only |

**`contracts/` is the public plugin API.** It holds:
- hookspecs, including the host's extension points;
- the core-service Protocols: storage, queue, coordination, secrets, scheduler, translator and current user;
- shared types: `OperationResult`, `OperationStatus`, identifiers and an actor reference.

It contains no implementation and imports nothing else from the app, so it could ship as a separate distribution without moving. Changes to it follow [hookspec-deprecation.md](hookspec-deprecation.md)'s lifecycle.

**Features and capabilities never import `infrastructure/` or `server/`.** The host constructs the core services and hands them to plugins.

**Features never import each other.** A need two features share becomes a capability.

**Plugins get core services from a registry, keyed by contract.** At startup the host registers a factory for each `contracts` Protocol in a type-keyed registry ([svcs](https://svcs.hynek.me/)). Entry points (HTTP routes, Slack and Teams handlers, jobs) take what they need from a container scoped to that call; FastAPI routes do this through the registry's FastAPI integration. Services receive their dependencies through their constructor and never look them up mid-method. Tests register fakes against the same Protocols.

**There is no in-process event bus.** The app runs as two or more replicas, so an in-process event reaches only the replica that raised it. A plugin reacts to something another plugin does through an extension point that the capability where it happens owns. That call is explicit, typed and visible at startup. For example, the incoming-webhook pipeline is a capability, and the incident feature registers the alert actions it handles. A reaction that must reach every replica, or survive a crash or a restart, goes through a queue or publish-subscribe contract in `contracts/`, implemented in `infrastructure/` with a transactional outbox, built when the first such reaction exists.

**Extension points collect strategies once, at startup.** The host calls each capability's hookspecs during startup to collect strategy objects (an `ApprovalPolicy`, an alert-action handler). At runtime the capability awaits those objects' async methods. pluggy hooks are synchronous and are never called per request.

**Every core-service contract assumes several replicas.** No plugin keeps shared state in memory. A scheduled job runs once across replicas by taking a lease from the coordination contract.

**Plugins are declared in `pyproject.toml` and enabled per environment in configuration.** These are three separate concerns:
- *Which plugins exist* is an entry point in `pyproject.toml`: static, reviewed, and the same in every image.
- *Which plugins run, and their settings,* live in typed configuration files checked into the repo: a base file plus one per environment, selected by `ENVIRONMENT` and validated at boot with pydantic-settings' TOML source. This is Backstage's `app-config.yaml` plus `app-config.production.yaml` pattern. The host skips a disabled plugin before registering it. Environment variables carry only secrets and deployment identity. The same image is promoted through every environment.
- *Runtime flags* (gradual rollout, a kill switch without a deploy) use [OpenFeature](https://openfeature.dev/), with the self-hosted flagd provider, and are added only when a feature needs them.

**One package shape, enforced by tooling.** Every feature, capability and subdomain follows the [feature-packages.md](feature-packages.md) layout. A generator creates new packages in that shape, and a CI check rejects top-level names outside the layout table.

**Legacy modules are rebuilt by surface, not moved.** Each user-facing surface of `modules/` (slash command, interaction, webhook route, scheduled job) is assigned to a target feature or capability and rebuilt there in the standard shape, behind smoke tests that pin its external behaviour. Vendor-specific concepts leave features on the way: an incident works with documents and a chat channel through capability contracts, not with Google Drive folders. A legacy module is deleted when its last surface has moved. Features already in `packages/` move to `features/` one per PR, with every importer rewritten, legacy ones included.

**A capability** qualifies only when all three hold:
1. at least one feature needs it now;
2. it is a domain-agnostic engine, or it carries organization policy across external systems;
3. its vocabulary is feature-free.

Whether it is generic or supporting is recorded in its README, not by its directory.

**A capability's public surface** is `api.py` (Protocol, domain types, provider function) plus its own hookspecs module. Everything else in it is private.
- An extension point belongs to one capability. Features register into it at startup, before that capability initializes.
- A capability may import a lower capability's `api.py`, in a declared order, with no cycles.

**Engines take strategies and hold no feature logic.** The approvals engine exposes `start`, `submit_decision`, `get_state` and `cancel`. Features supply a pure, deterministic `ApprovalPolicy` and an idempotent `EffectHandler` keyed by request id. A durable-execution engine can then replace the in-house state machine without changing any feature.

**`infrastructure/` is hosting only:** code that talks to the hosting environment and is swapped per deployment. Its contracts expose no provider concept (DynamoDB keys and indexes, stream records), so a second cloud's implementation can be added. Which store is the portability target is a separate decision.

**Framework services are host code.** The plugin manager, transport runtimes, i18n, auth and logging setup are implemented in `server/`, with their contracts in `contracts/`. i18n is built in: every user-facing feature string goes through the translator contract, whose implementation uses a maintained library (a separate decision).

**Enforcement comes before any move.** Import-linter contracts for this table land first. Existing violations are listed as `ignore_imports` entries, which may only be removed (`unmatched_ignore_imports_alerting = error`). Layers that don't exist yet are marked optional.

This record replaces the former three-tier layers record, the capability-packages draft and the events record. Path B adapters are unchanged ([outbound-clients.md](outbound-clients.md)).

## Consequences

- Contributors learn one rule: import `contracts`, capabilities' `api.py` and your own package.
- Hosting can change per cloud without any feature changing.
- An engine can move to a managed workflow product behind the same `api.py`.
- Cost: most of `infrastructure/` moves, and the host takes on the wiring that features do themselves today.
- Risk: `contracts/` becomes a grab-bag. Mitigation: it only holds Protocols and types used across layers, and every change is reviewed as public API.
- Risk: `server/` becomes a god package. Mitigation: each framework service is its own subpackage with a contract.

## Checks

- import-linter `layers` contract over `app/` matching the table; its ignore list only shrinks.
- import-linter `forbidden`: `features` and `capabilities` never import `infrastructure` or `server`; `contracts` imports nothing from the app.
- import-linter `independence` across the packages in `features/`.
- Review: each capability's README states its classification and names at least one feature consumer; features import a capability only through `api.py`.
- Boot test: every plugin loads, and every extension point is filled before its capability initializes.
- CI shape check: every package under `features/` and `capabilities/` uses only names from the layout table.
- Boot test: every entry point has an enablement key in the base configuration file, and a disabled plugin is never registered.
- Review: no feature or capability reads an environment variable; configuration arrives through its settings slice.
- import-linter `forbidden`: nothing outside `server/` imports provider modules; plugins resolve core services through the registry.

## Migration

Tickets to create:
- update `CLAUDE.md`'s architecture and import-boundary sections, and the skills that restate them;
- rescope TASK-18 to these contracts;
- hold TASK-60 and rescope it to `capabilities/approvals/`;
- build the package generator and the shape check;
- move, one package at a time: `contracts/`, workplace systems to `capabilities/`, audit and notifications to `capabilities/`, framework services to `server/`, existing features to `features/`;
- inventory every legacy surface with its target feature or capability, then rebuild them surface by surface.

Tolerated until then:
- features importing `infrastructure` providers;
- framework and workplace code in `infrastructure/`;
- `OperationResult` in `infrastructure/operations/`;
- the DynamoDB `RetryStore` used as a queue;
- the blinker-backed event dispatcher, used only by `access/request` and `access/sync`, which are rebuilt anyway;
- feature switches and settings read from environment variables;
- legacy `modules/` surfaces not yet rebuilt;
- the in-house i18n implementation.

**Changes:**
- 2026-09-24: accepted; the layers, capability-packages and events records are deleted and the related records rewritten to match.

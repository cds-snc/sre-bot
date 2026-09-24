---
status: Accepted
date: 2026-07-06
applies: target
scope: How core services are constructed, registered, and reach features, capabilities, and entry points.
---

# Dependency Injection

## Context

Features need core services (storage, queue, coordination, secrets, scheduler, translator, current user) that satisfy the Protocols in `contracts/` ([plugin-architecture.md](plugin-architecture.md)). The host constructs them; features and capabilities must not import their implementations.

Current code:
- Each infrastructure service exposes a module-level provider function (`get_storage_service()`, `get_event_dispatcher()`, `get_directory_provider()`), and features import these directly from `infrastructure.*`. `packages/access/request/providers.py`, for example, calls `get_storage_service()` and `get_event_dispatcher()`.
- Feature `providers.py` files (`access/*`, `incident_draft`, `oncall_sync`, `user_rotations`) build service objects in `@lru_cache` functions, so each is process-global state that tests must reset.
- Construction is lazy, on first call. Lifespan warms up a few services explicitly (JWKS, directory, translator) and each feature's `startup_warmup` hookimpl warms its own; nothing guarantees every service is built before traffic.
- Routes rarely use `Depends()`; most call provider functions inline.

[svcs](https://svcs.hynek.me/) (26.x) is a small, typed service locator: a registry maps a type to a factory, and a container scoped to one unit of work resolves services from it (`get`, async `aget`) and runs their cleanup when the scope closes. Its FastAPI integration builds the registry in lifespan and gives each request its own container.

## Decision

**The host registers core services by contract in an svcs registry.** At startup `server/` registers one factory per `contracts` Protocol (`registry.register_factory(StorageService, ...)`). The Protocol is the key; the concrete class name appears only in the host's registration code. Nothing outside `server/` imports a provider module or an `infrastructure` implementation.

**Construction is validated eagerly at boot.** After registration, lifespan resolves every registered service once from a startup container and runs its health check. A missing setting or a failing constructor aborts boot before `yield` ([lifecycle.md](lifecycle.md)); nothing is first built mid-request.

**Entry points take services from a container scoped to that call:**
- HTTP routes use the svcs FastAPI integration: a `svcs.fastapi.DepContainer` parameter, then `await services.aget(StorageService)`. The container closes with the request, running factory cleanup.
- Slack and Teams handlers, webhook consumers and jobs open a container per invocation and close it when the invocation ends.
- Only entry points touch a container. Services receive their dependencies through their constructor, typed by Protocol, and never look anything up mid-method.

**Feature-local wiring stays in the feature.** A feature builds its own service objects (repositories, application services, policies) from contracts it resolved from the registry, in its own wiring module. It does not register them as core services, and no other package imports that wiring.

**No `lru_cache` provider functions across layers.** A cached module-level function that returns a shared instance is the pattern being replaced; features and capabilities do not import one from another layer. Singleton lifetime, where a service needs it, is the host's registration choice (`register_value` or a factory closing over one instance), not a cache on a function.

**Tests register fakes against the same Protocols.** A test builds a registry, registers a Protocol-conforming fake for each contract it needs, and passes it to the app or the entry point. Fakes that satisfy the Protocol are preferred over `MagicMock`. No test clears global caches.

## Consequences

- Features see only Protocols; hosting implementations change without any feature changing.
- One mechanism covers HTTP, chat platforms and jobs, with explicit scope and cleanup per call.
- Tests replace a dependency by registering a fake, not by patching module globals.
- Cost: a new runtime dependency (svcs) and a locator call at every entry point. A locator used inside services would hide dependencies, so the entry-point-only rule is load-bearing.
- Cost: eager resolution at boot lengthens startup and needs every service to be constructible in CI with fakes or local backends.

## Checks

- import-linter `forbidden`: nothing outside `server/` imports provider modules or `infrastructure` implementations ([plugin-architecture.md](plugin-architecture.md)).
- Boot test: a registered factory that raises aborts lifespan before `yield`.
- grep: no `@lru_cache` provider function under `features/` or `capabilities/` is imported from another package.
- Review: services take dependencies in `__init__`; `get`/`aget` calls appear only in entry points and host code.

## Migration

Tickets: TASK-18 (contracts and import boundaries). A separate ticket, still to create, introduces the registry in `server/`.

Tolerated until closed:
- features importing `infrastructure` provider functions (`get_storage_service`, `get_event_dispatcher` and the other `get_*` functions);
- `@lru_cache` providers in feature `providers.py` files, and the global cache resets tests need for them;
- lazy first-call construction, with warmup done piecemeal in lifespan and `startup_warmup` hookimpls;
- routes calling provider functions inline instead of taking a container.

**Changes:**
- 2026-09-24: replaced cached provider functions with an svcs registry of contract-keyed factories, resolved per call at entry points.

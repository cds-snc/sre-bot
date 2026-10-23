---
status: Accepted
date: 2026-07-06
applies: target
scope: How core services are constructed, registered, and reach features, capabilities, and entry points.
---

# Dependency Injection

## Context

Features need core services (records, queue, coordination, secrets, scheduler, translator, current user) that satisfy the Protocols in `contracts/` ([plugin-architecture.md](plugin-architecture.md)). The host constructs them; features and capabilities must not import their implementations.

Current code:
- Each infrastructure service exposes a module-level provider function (`get_record_store()`, `get_event_dispatcher()`, `get_directory_provider()`), and features import these directly from `infrastructure.*`. `packages/access/request/providers.py`, for example, calls `get_record_store()` and `get_event_dispatcher()`.
- Feature `providers.py` files (`access/*`, `incident/scribe`, `oncall_sync`, `user_rotations`) build service objects in `@lru_cache` functions, so each is process-global state that tests must reset.
- Construction is lazy, on first call. Lifespan builds a few services explicitly (JWKS clients, directory, translator) and each feature's `startup_warmup` hookimpl builds its own; nothing guarantees every service is built before traffic. Two of these paths call the network while building a service, which the Decision below forbids: the opt-in directory warmup and `access/sync`'s AWS adapter, whose client factory assumes a role through STS.
- Routes rarely use `Depends()`; most call provider functions inline.

[svcs](https://svcs.hynek.me/) (26.x) is a small, typed service locator: a registry maps a type to a factory, and a container scoped to one unit of work resolves services from it (`get`, async `aget`) and runs their cleanup when the scope closes. Its FastAPI integration builds the registry in lifespan and gives each request its own container.

## Decision

**The host registers core services by contract in an svcs registry.** At startup `server/` registers one factory per `contracts` Protocol (`registry.register_factory(RecordStore, ...)`). The Protocol is the key; the concrete class name appears only in the host's registration code. Nothing outside `server/` imports a provider module or an `infrastructure` implementation.

**Construction is validated eagerly at boot, without network I/O.** After registration, lifespan resolves every registered service once from a startup container. That boot check is construction plus static validation of the service's settings slice. A missing setting or a failing constructor aborts boot before `yield` ([lifecycle.md](lifecycle.md)); nothing is first built mid-request. A factory never calls its backing service while constructing it, so the check cannot fail because a dependency is down.

**Pings are diagnostics, not boot checks.** A factory may register an svcs `ping` ([health checks](https://svcs.hynek.me/en/stable/core-concepts.html)) that calls its backing service. Pings are never run by the container, load-balancer or DNS health checks ([health-checks.md](health-checks.md)). A service that should report broken credentials at boot declares a classified credential check instead, which alerts and never aborts ([lifecycle.md](lifecycle.md)).

**Entry points take services from a container scoped to that call:**
- HTTP routes use the svcs FastAPI integration: a `svcs.fastapi.DepContainer` parameter, then `await services.aget(RecordStore)`. The container closes with the request, running factory cleanup.
- Slack and Teams handlers and jobs open a scope with `create_scope()` on the `ServiceScopeOpener` their registrar exposes (`registrar.service_scopes`, `registry.service_scopes`). The scope closes when the invocation ends, including when the handler raises. The handler resolves the contracts it needs there, builds its services through the feature's provider functions from the resolved contracts, and calls one service method. The resolver is never given to a service: resolving at the entry point is dependency injection, resolving inside a service is service location. The scope is synchronous now; an async variant arrives with async Bolt (TASK-33). The Protocols live in `contracts/services` and import no svcs; `server/services.py` implements the opener over the registry. Webhook consumers and approval handlers obtain an opener from their own registration points, settled when each is planned.
- Only entry points touch a container. Services receive their dependencies through their constructor, typed by Protocol, and never look anything up mid-method.

**Alternative considered: a host Bolt middleware.** A middleware opens the container per request and places it in the Bolt context, the svcs custom-integration pattern. Pros: native for block actions and view listeners, and no registrar API change. Cons: it does not cover background jobs; host-routed commands would need it threaded through `CommandPayload` while TASK-141 is undecided; and it would be a second mechanism beside the job one. Revisit if TASK-141 or TASK-33 changes how Slack listeners are registered.

**Feature-local wiring stays in the feature.** A feature builds its own service objects (repositories, application services, policies) from contracts it resolved from the registry, in its own wiring module. It does not register them as core services, and no other package imports that wiring. In an umbrella, the services every subdomain shares are built by the provider functions in the feature's `core/api.py`, which each subdomain's wiring calls ([feature-packages.md](feature-packages.md)).

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
- Boot test: resolving every registered service opens no outbound connection (`socket.connect` spy).
- grep: no `@lru_cache` provider function under `features/` or `capabilities/` is imported from another package.
- Review: services take dependencies in `__init__`; `get`/`aget` calls appear only in entry points and host code.

## Migration

Tickets: TASK-18 (contracts and import boundaries), TASK-109 (the registry in `server/`), TASK-148 (lease duration on the claim call), TASK-149 (no credential lookup at client construction).

In place (TASK-109): `server/services.py` registers the records contract (`RecordStore`) and the coordination contract (`ConditionalWriteStore`), each built once per registry; lifespan phase 2 resolves both before plugin loading; tests register fakes with `tests/fixtures/service_registry.py`; import-linter contract (k) keeps `infrastructure.records` and `infrastructure.coordination` out of every module outside `server/`. The registry, phase 2 and the fixture are in place. The opener and the registrar exposure are in place (TASK-145.5.2): `registrar.service_scopes` on the Slack registrars and `registry.service_scopes` on the job registry, implemented by `SvcsServiceScopeOpener` in `server/services.py`. No production route or handler resolves from a container yet; the only route taking `DepContainer` is a reference test. The registered store carries the default in-progress TTL, and consumers build `LeaseStore` and `IdempotencyStore` over it with their own read-failure policy.

Tolerated until closed:
- features importing `infrastructure` provider functions (`get_record_store`, `get_event_dispatcher` and the other `get_*` functions), and contracts not yet registered; for records and coordination each remaining import is an ignore entry in contract (k) naming its removing task;
- non-default lease TTLs built through `build_lease_store`/`get_lease_store` (removed by TASK-148);
- building an AWS client with only ambient credentials contacts the instance metadata endpoint, so phase 2 is network-free only with configured credentials (TASK-149);
- `@lru_cache` providers in feature `providers.py` files, and the global cache resets tests need for them;
- lazy first-call construction for services not yet registered, with warmup done piecemeal in lifespan and `startup_warmup` hookimpls, two of which call the network while building a service (removed by TASK-98 and TASK-128);
- routes calling provider functions inline instead of taking a container.
- the process state in `contracts/configuration.py` that the app factory installs once: the configuration files, needed while slices are built by zero-argument providers, and the `host_info()` accessor, read by code not yet on the registry (`modules/`, the Notify client, the request auth dependency and the version route) until each reader resolves `HostInfo` from the registry or receives it through its constructor; tests install and uninstall it in a fixture.

**Changes:**
- 2026-09-24: replaced cached provider functions with an svcs registry of contract-keyed factories, resolved per call at entry points.
- 2026-09-25: the boot check is construction and static validation with no network I/O; svcs pings are diagnostics; credential checks alert and never abort.
- 2026-10-01: an umbrella's shared services are wired through its `core/api.py`.
- 2026-10-13: the storage contract is the records contract (`RecordStore`, TASK-27.4).
- 2026-10-14: the registry exists for records and coordination, with phase 2, the entry-point convention, the test fixture and contract (k); the coordination registration is the primitive, and consumers build the lease and idempotency facades (TASK-109).
- 2026-10-15: non-HTTP entry points open a scope through `ServiceScopeOpener` exposed by the Slack registrars and the job registry; resolve-then-pass rule and the Bolt middleware alternative recorded; the in-place line corrected (TASK-145.5.2).
- 2026-10-22: the registry holds `HostInfo` as a value registered in the lifespan; the `contracts/configuration.py` process state (installed files, `host_info()` accessor) is tolerated for code not yet on the registry (TASK-111.7).
- 2026-10-23: logging setup no longer reads `host_info()`; the configuration phase passes it the environment (TASK-111.17).

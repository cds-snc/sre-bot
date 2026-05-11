---
title: "Dependency Injection"
status: Accepted
type: Standard
tier: Tier-2
governance_domain: [application]
concerns: [architecture]
constrained_by: [layered-architecture.md, type-boundaries.md, configuration-ownership.md, application-lifecycle.md]
date: 2026-05-08
decision_makers:
  - SRE Team
---

# Dependency Injection

## Context and Problem Statement

The application is composed of layers (feature packages, infrastructure services, vendor clients) and cross-cutting primitives (settings, identity, eventing). Most of these depend on each other: a composed-service implementation needs a vendor client and a settings slice; a feature service needs one or more Protocols satisfied by infrastructure; a feature-owned outbound adapter needs a vendor client received via constructor injection. Without a single mechanism for wiring those dependencies together, every consumer ends up constructing its own collaborators, hard-coding concrete classes, or pulling in a global registry — and the boundary rules of [layered-architecture.md](layered-architecture.md) become unenforceable in practice.

The problem this record addresses: **how are dependencies constructed and supplied to the code that uses them?** The answer has to satisfy four concurrent requirements:

1. Feature service and domain code depends on Protocol types only ([layered-architecture.md](layered-architecture.md), [type-boundaries.md](type-boundaries.md)). The mechanism by which a Protocol-typed name receives a concrete value cannot leak the concrete type into the consumer's source.
2. Settings classes are loaded once per process and reused ([configuration-ownership.md](configuration-ownership.md)). Whatever wires services together must compose those cached settings without making services aware of caching mechanics.
3. Wiring runs during the lifespan's phase 2 (infrastructure composition), with all registries frozen at `yield` ([application-lifecycle.md](application-lifecycle.md)). Construction of dependencies is a startup-time activity, not a per-request one.
4. Tests substitute dependencies for Protocol-conformant stubs without touching production code ([configuration-ownership.md](configuration-ownership.md) already establishes the override patterns; this ADR governs what gets overridden).

**Constraints:**

- The framework is FastAPI on Uvicorn. FastAPI provides `Depends()` for declarative injection into route handlers and `app.dependency_overrides` for test-time substitution.
- Non-HTTP execution contexts exist: pluggy hookimpls, background loops, startup code. These do not run inside an ASGI request and cannot use `Depends()`.
- Settings providers already use `@lru_cache(maxsize=1)` per [configuration-ownership.md](configuration-ownership.md). The same pattern is the natural fit for service providers.
- The application has no third-party DI container (e.g., `dependency-injector`, `lagom`); FastAPI's `Depends()` plus `functools.lru_cache` provider functions cover what is needed.

**Non-goals:**

- This record does not define `BaseSettings` ownership, partitioning, or the `@lru_cache(maxsize=1)` settings-provider rule — see [configuration-ownership.md](configuration-ownership.md).
- This record does not define when in the boot sequence providers run — see [application-lifecycle.md](application-lifecycle.md), phase 2.
- This record does not define which Protocol contracts exist for shared infrastructure services or how Category A/B/C is assigned — see [infrastructure-service-classification.md](infrastructure-service-classification.md).
- This record does not define feature-package internal organization — see [feature-package-structure.md](feature-package-structure.md).
- This record does not define static-analysis import rules — see [import-governance.md](import-governance.md).

## Considered Options

**Option 1 — Function-based providers with FastAPI `Depends()` and `@lru_cache(maxsize=1)`, co-located with the service they construct.** Each infrastructure service is a vertical slice: its own module owns the Protocol contract, the concrete implementation(s), and the `get_<service>()` provider function. HTTP route handlers receive dependencies through `Annotated[T, Depends(get_x)]`; non-HTTP code calls `get_x()` directly. Cross-service composition (where one provider calls another) happens through normal Python imports between service modules at the provider level. Consumers import both the Protocol and the provider from a single per-service consumption surface.

**Option 2 — Third-party DI container.** Adopt a library (`dependency-injector`, `lagom`, etc.) that registers providers in a container and resolves them at call sites.

**Option 3 — Manual constructor wiring at startup.** Construct concrete instances at process boot and pass them by reference to consumers; no provider functions, no caching layer.

## Decision Outcome

**Chosen: Option 1 — function-based providers with FastAPI `Depends()` and `@lru_cache(maxsize=1)`.**

The application uses what FastAPI and the Python standard library already provide: provider functions, declarative `Depends()` for HTTP routes, and `@lru_cache` for the singleton lifecycle. There is no DI container; the composition mechanism is a set of small functions whose signatures and call graphs are visible to readers and to type checkers.

### The provider function pattern

Every dependency has a provider function with this shape:

```python
@lru_cache(maxsize=1)
def get_<name>() -> <ProtocolType>:
    settings = get_<domain>_settings()
    return <ConcreteImpl>(settings=settings, ...other_deps...)
```

Rules:

- **Naming.** `get_<name>()`. The name describes the *capability*, not the concrete implementation — `get_storage_service()`, not `get_dynamodb_storage_service()`.
- **Caching.** `@lru_cache(maxsize=1)` — the provider returns the same instance for the process lifetime. First call performs construction and validation; subsequent calls return the cache.
- **Return type.** Provider functions for Category A capabilities return the **Protocol type** ([infrastructure-service-classification.md](infrastructure-service-classification.md)), not the concrete implementation. This keeps the consumer's source free of any concrete class name.
- **Internals.** Inside the provider, settings are read by calling the relevant settings provider, and dependencies on other services are made by calling their `get_x()` functions. Construction is the only place where a concrete class name appears.

Provider functions are pure (modulo their cache): given the same environment, repeated invocations from a fresh process produce the same instance.

### Provider location

Each infrastructure service is a self-contained vertical slice. The service's module owns three things together: its Protocol contract, its concrete implementation(s), and its provider function.

```text
app/infrastructure/<service>/
├── __init__.py        # public surface: re-exports Protocol + get_<service>
├── protocol.py        # the Protocol contract
├── providers.py       # @lru_cache get_<service>() — the provider
└── <concrete>.py      # one or more concrete implementations
```

The service's `__init__.py` is the **per-service consumption surface**: it re-exports the Protocol and the provider function so consumers reach both through one import:

```python
# app/infrastructure/storage/__init__.py
from app.infrastructure.storage.protocol import StorageService
from app.infrastructure.storage.providers import get_storage_service

__all__ = ["StorageService", "get_storage_service"]
```

Three rules follow from this:

1. **Cross-service composition lives in the consuming service's `providers.py`**. When `get_notification_service()` needs `get_idempotency_service()` and `get_resilience_service()`, the notification service's provider module imports those siblings via the public surface (`from app.infrastructure.idempotency import get_idempotency_service`) and calls them. The dependency graph between services is visible by reading each service's provider module and tracing its imports.
2. **Sibling-service imports are scoped to provider modules.** The notification service's domain code (`protocol.py`, concrete implementation files) does not import from sibling services. Only the provider — the wiring code — sees other services. Domain code only sees Protocols received via constructor.
3. **Feature-package-local providers** live at `app/packages/<feature>/providers.py`. A feature owns provider functions for its package-local domain services, repositories, feature-owned outbound adapters, and feature-specific settings. These providers are private to the feature: infrastructure code does not import them, and other features do not import them.

The "composition root" of the application — the moment when the object graph is assembled — is the lifespan's phase 2 ([application-lifecycle.md](application-lifecycle.md)), not a single physical file. Phase 2 is when the providers are first invoked and their `@lru_cache` caches populated. Where the provider *functions* live is a code-organization question; the *timing* of composition is what Composition Root is fundamentally about, and that is owned by the lifespan.

### HTTP route injection

Route handlers receive dependencies through FastAPI's declarative mechanism:

```python
from typing import Annotated
from fastapi import Depends
from app.infrastructure.storage import StorageService, get_storage_service

StorageServiceDep = Annotated[StorageService, Depends(get_storage_service)]

@router.get("/items/{item_id}")
async def get_item(item_id: str, storage: StorageServiceDep) -> Item:
    ...
```

Rules:

- **Type annotation.** The annotated type is the **Protocol**, not the concrete. The handler's signature carries no knowledge of the backing implementation.
- **`Depends()`.** Receives the `@lru_cache` provider function directly. No lambdas, no wrappers, no string indirection.
- **Alias declaration.** The `Annotated` alias (`StorageServiceDep`) is declared by the consumer of the dependency — typically in the same module as the route or in a small `deps.py` adjacent to the routes. There is no central "all DI aliases" file.
- **Test substitution.** `app.dependency_overrides[get_storage_service] = lambda: stub` ([configuration-ownership.md](configuration-ownership.md)).

### Non-HTTP injection

Code that runs outside an ASGI request scope — pluggy hookimpls, background loops, startup code, scheduled jobs — calls provider functions directly:

```python
@hookimpl
def my_feature_register(plugin_manager) -> None:
    dispatcher = get_event_dispatcher()
    dispatcher.register(...)
```

Rules:

- **Inside function body.** Provider calls happen inside the function that uses the dependency, not at module level. Module-level provider calls would force eager construction at import time and defeat the lifespan-phase ordering established by [application-lifecycle.md](application-lifecycle.md).
- **No `Depends()`.** `Depends()` is FastAPI machinery for routes. Outside the request scope, it does nothing.
- **Test substitution.** `get_x.cache_clear()` followed by monkey-patching the function to return a stub. `app.dependency_overrides` is not available outside the FastAPI request scope and must not be used here.

### Constructor injection rules

Once a dependency reaches its consumer, the consumer holds it as a constructor argument typed by Protocol:

```python
class NotificationService:
    def __init__(
        self,
        notify_settings: NotifySettings,
        idempotency: IdempotencyService,        # Protocol
        resilience: ResilienceService,          # Protocol
    ) -> None:
        ...
```

Rules:

- **Protocol-typed parameters** for service dependencies. No concrete class name appears in the parameter type.
- **Narrow-slice settings.** A consumer that needs a settings slice receives that slice's `BaseSettings` (or relevant fields). It does not receive a wider `Settings` object that contains other domains' values.
- **No service locator.** Consumers receive their dependencies by constructor; they do not call provider functions inside their own methods (with one exception: a provider may call other providers to build its own dependency graph; that is composition, not service-locator usage).
- **Concrete construction lives in providers, not in domain or service code.** A class name like `DynamoDBStorageService` or `AwsIdentityCenterAdapter` appears in exactly one place: the provider that constructs it.

### Cross-service composition only at the root

When one infrastructure service depends on another (Service B needs Service A), the provider for Service B at the composition root calls Service A's provider:

```python
@lru_cache(maxsize=1)
def get_notification_service() -> NotificationService:
    return NotificationService(
        notify_settings=get_notify_settings(),
        idempotency=get_idempotency_service(),     # cross-service call here
        resilience=get_resilience_service(),
    )
```

A composed service does not import another composed service's concrete class to construct it; the wiring happens through providers. Sibling-service composition that is not at the composition root is prohibited — it would distribute the call graph across the codebase.

### Composition depth

The composition graph has four conceptual levels, in order:

| Level | Producer | Consumer of |
| --- | --- | --- |
| 0 | `BaseSettings` providers (e.g., `get_<domain>_settings`) | environment |
| 1 | Vendor-client providers and Level-0 settings | settings |
| 2 | Composed-service providers | settings + clients |
| 3 | Higher-level composed services | other composed services |

A composition graph deeper than this — Level 4+ — indicates a service that has accumulated too many concerns and should be broken up before adding more. Code review enforces the depth bound; nothing in the mechanism makes Level 4+ impossible, but it is a smell.

### Test substitution

The override mechanisms are already established by [configuration-ownership.md](configuration-ownership.md); this ADR does not redefine them. In summary:

- **HTTP route consumers**: `app.dependency_overrides[get_x] = lambda: stub` set up before the test request and cleared in teardown.
- **Direct-call consumers**: `get_x.cache_clear()` plus `monkeypatch` (or test-double substitution) on the function itself. `app.dependency_overrides` does not apply.
- **Stubs.** Protocol-conformant in-process stubs are preferred for Category A services. `MagicMock` is acceptable for narrow internal collaborators that have no Protocol contract.

## Consequences

**Positive:**

- The wiring mechanism is small (provider functions + `Depends()` + `lru_cache`), uses only the framework and standard library, and is fully visible to type checkers and to readers.
- Provider locations encode the composition rule visually: cross-service wiring lives at the root; self-contained wiring lives with its service; feature-internal wiring lives in the feature.
- The same provider supplies HTTP and non-HTTP consumers; there is one path through which a dependency reaches its caller, and one place each consumer overrides it in tests.
- Domain and service code is free of concrete class names; refactoring a backing implementation does not touch consumers.

**Tradeoffs accepted:**

- The "two-location" provider rule (centralized cross-service vs distributed self-contained) requires authors to think about whether their provider depends on siblings. The distinction is a one-question check; the alternative (everything central, or everything distributed) is worse.
- `@lru_cache` providers cache for the process lifetime, which is a global state surface. Tests must clear caches; production must rely on disposability ([application-lifecycle.md](application-lifecycle.md)) to handle restarts cleanly.

**Risks:**

- A consumer might call `get_x()` from inside a method body to obtain a dependency at runtime ("service locator"), bypassing constructor injection. Mitigation: code review catches this; the smell is "calling `get_*` outside a provider, hookimpl, or background entry point."
- A provider might be defined in a self-contained location that secretly depends on a sibling service, miscategorizing it. Mitigation: code review verifies the rule; static-analysis tooling can flag cross-module provider calls outside the composition root.

## Confirmation

Compliance is verified by:

- **Code review (providers).** Each provider function uses `@lru_cache(maxsize=1)`, returns a Protocol type when the consumer is a Category A surface, and contains the only reference to its concrete class. Cross-service composition lives at the composition root; self-contained providers are co-located and re-exported.
- **Code review (consumers).** Domain and service code does not name concrete classes. HTTP routes use `Annotated[T, Depends(get_x)]`; hookimpls and background code call `get_x()` inside the function body; module-level provider calls are absent.
- **Static analysis.** Import-linter (or equivalent) confirms feature service modules import only from each infrastructure service's public surface (`app/infrastructure/<service>`) — the Protocol and the provider function — never from the concrete-implementation files inside that service. Sibling-service imports inside infrastructure are restricted to provider modules (`providers.py`); domain code (`protocol.py`, concrete files) does not import from sibling services.
- **Tests.** HTTP-handler tests use `app.dependency_overrides`; hookimpl and background tests use `cache_clear()` plus monkey-patching. Substitutions are Protocol-conformant where the dependency exposes a Protocol.

## Source References

1. Composition Root — Mark Seemann
   - URL: <https://blog.ploeh.dk/2011/07/28/CompositionRoot/>
   - Accessed: 2026-04-29
   - Relevance: Establishes the Composition Root pattern: a single, unique location at the application's entry point where the object graph is constructed. Grounds the rule that cross-service composition happens at `app/infrastructure/services/providers.py` rather than being distributed across consumer modules.

2. Inversion of Control Containers and the Dependency Injection Pattern — Martin Fowler
   - URL: <https://martinfowler.com/articles/injection.html>
   - Accessed: 2026-04-29
   - Relevance: Distinguishes constructor injection (preferred), setter injection, and service locator (anti-pattern in most contexts). Grounds the rule that consumers receive dependencies as constructor arguments rather than calling provider functions from inside their methods.

3. FastAPI — Dependencies
   - URL: <https://fastapi.tiangolo.com/tutorial/dependencies/>
   - Accessed: 2026-04-29
   - Relevance: Documents `Annotated[T, Depends(...)]` for declarative dependency injection in route handlers and `app.dependency_overrides` for test-time substitution. The HTTP-route injection pattern is the framework's intended use.

4. Architecture Patterns with Python (Cosmic Python) — Dependency Injection and Bootstrapping (Chapter 13) — Percival and Gregory
   - URL: <https://www.cosmicpython.com/book/chapter_13_dependency_injection.html>
   - Accessed: 2026-04-29
   - Relevance: Demonstrates function-based dependency injection in Python without a DI container: a bootstrap module wires concrete adapters together at startup and exposes them through provider functions. Confirms that the function-and-cache pattern is canonical for Python-without-container codebases.

5. Python 3.12 — `functools.lru_cache`
   - URL: <https://docs.python.org/3.12/library/functools.html#functools.lru_cache>
   - Accessed: 2026-04-29
   - Relevance: Documents `@lru_cache(maxsize=1)` as a memoization decorator on a parameterless function (effectively a singleton initializer) and the `cache_clear()` method used in test setup/teardown. Grounds the singleton lifecycle and test substitution mechanism.

6. The Twelve-Factor App — Backing Services
   - URL: <https://12factor.net/backing-services>
   - Accessed: 2026-04-29
   - Relevance: Backing services are attached resources whose concrete provider is selected at deployment time. Provider functions returning Protocol types operationalize this contract: the consumer holds a Protocol; the provider chooses the concrete based on configuration; swapping providers requires no consumer change.

## Change Log

- 2026-05-08: Created. Establishes function-based providers with `@lru_cache(maxsize=1)` returning Protocol types as the application's dependency-injection mechanism. Each infrastructure service is a vertical slice — Protocol, provider, and concrete implementation co-located in `app/infrastructure/<service>/` — and exposes a single per-service consumption surface (`from app.infrastructure.<service> import <Protocol>, get_<service>`). Cross-service composition happens in the consuming service's `providers.py` via normal Python imports between sibling services; sibling-service imports are scoped to provider modules and do not appear in domain code. Feature-package-local providers at `app/packages/<feature>/providers.py` remain private to the feature. HTTP route handlers receive dependencies through `Annotated[T, Depends(get_x)]`; non-HTTP code (hookimpls, background loops, startup) calls providers directly inside function bodies. Constructor injection with Protocol-typed parameters; no service-locator usage in consumers. The "composition root" is the lifespan's phase 2 (when providers are first invoked and caches populated), not a single physical file. Composition depth bounded at four conceptual levels (settings → clients → composed services → higher-level composed services).

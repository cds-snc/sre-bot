---
status: Accepted
date: 2026-07-06
applies: target
scope: How dependencies are constructed and reach their consumers.
---

# Dependency Injection

## Context

Features need Protocols satisfied; services need clients and settings. FastAPI provides `Depends()` and `dependency_overrides`; the standard library provides caching. A third-party DI container adds machinery this codebase doesn't need.

## Decision

**Provider functions, cached, returning Protocol types:**

```python
@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:      # Protocol, not concrete
    return DynamoDBStorageService(settings=get_storage_settings(), ...)
```

- Named for the capability (`get_storage_service`, never `get_dynamodb_...`). The concrete class name appears in exactly one place: its provider.
- Each infrastructure service is a vertical slice — `protocol.py`, implementation(s), `providers.py` — re-exported through its `__init__.py`. Provider-to-provider calls are how services compose; only `providers.py` may import sibling services.
- Feature-local providers live at `app/packages/<feature>/providers.py`, private to the feature.

**Eager composition at startup.** Providers register themselves in a small registry (a decorator appending to a module-level list); lifespan phase 2 **invokes every registered provider**, so construction and validation happen at boot — fail fast, not mid-request. This makes "the composition root is lifespan phase 2" true instead of aspirational, and gives tests one switch to clear all caches.

**Consumption:**

- HTTP routes: `Annotated[StorageService, Depends(get_storage_service)]`.
- Hookimpls, jobs, startup code (no request scope): call `get_x()` inside the function body. This is locator-style access, and that's fine **at entry points only** — inside services, dependencies arrive by constructor, typed by Protocol, never fetched mid-method.

**Tests:** routes use `app.dependency_overrides[get_x] = lambda: fake`; direct-call consumers use the registry's clear-all fixture + monkeypatch. Fakes conforming to the Protocol beat `MagicMock`.

## Consequences

- The whole mechanism is ~three idioms of framework + stdlib, visible to type checkers; no container to learn.
- `lru_cache` singletons are process-global state: the registry + clear-all fixture is the required antidote in tests.
- Divergence to fix: `Depends()` is barely used in existing routes and no warmup registry exists yet — new code follows this record; the registry is a small standalone PR.

## Checks

- Lifespan phase 2 invokes the provider registry (test: a poisoned provider fails boot).
- grep: concrete service class names appear only in `providers.py` files.
- Test suite has one autouse fixture clearing registered providers.

## Migration

Ticket: provider registry + eager phase-2 warmup (one small PR; unblocks [testing.md](testing.md)'s clear-all fixture). Tolerated until closed: lazy first-call construction; sparse `Depends()` usage in existing routes.

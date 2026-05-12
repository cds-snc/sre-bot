---
name: plugin-registration-lifespan
description: Apply pluggy registration and lifespan startup patterns for package discovery, initialization ordering, and testable startup behavior.
---

## Startup Phases (Fail-Fast)

1. **Configuration** — Load env vars into `BaseSettings`.
2. **Infrastructure** — Compose shared services (storage, queue, idempotency).
3. **Discovery/Registration** — Load plugins via entry-points; register hookspecs.
4. **Feature Activation** — Call `register_routes`, `register_background_jobs`, etc.
5. **Transport** — Bind HTTP routes, Slack/Teams handlers.
6. **Background** — Start scheduled tasks, job processors.

Any phase failure stops startup. No partial success.

## Plugin Discovery & Registration

Plugins declared in `pyproject.toml` `[project.entry-points."<host_namespace>"]`:

```toml
[project.entry-points."sre_bot"]
myfeature = "app.packages.myfeature"
```

Each entry-point is one feature package = one plugin.

At startup:
1. Create `PluginManager("<host_namespace>")`.
2. Call `pm.add_hookspecs(hookspecs_module)` (centralized, not per-feature).
3. Call `pm.load_setuptools_entrypoints("<host_namespace>")`.
4. Call each hook: `pm.hook.register_routes(app=...)`, etc.

Singleton via `@lru_cache(maxsize=1)`.

## Feature Hookimpls

In feature's `__init__.py` only:

```python
@hookimpl
async def register_routes(app: FastAPI) -> None:
    app.include_router(routes.router)

@hookimpl
async def startup_warmup() -> None:
    await service.validate()
```

No import-time side effects. No module-level state mutations.

## Anti-patterns

- Import-time registration.
- Business logic in bootstrap.
- Silent warmup failures.
- Feature `__init__.py` with anything but hookimpls.
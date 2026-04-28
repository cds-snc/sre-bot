---
adr_id: ADR-0013
title: "Plugin Managers"
status: Accepted
decision_type: Principle
tier: Tier-1
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by: []
related_records:
  - ADR-0011
  - ADR-0026
  - ADR-0027
related_packages: []
review_state: stale
---
# Plugin Managers

## Context

Feature packages need a way to self-register during startup without modifying the main lifespan function. A declarative plugin system allows new packages under `packages/` to automatically wire themselves into the application.

## Decision

Use Pluggy (pytest's battle-tested plugin system) for managing hook specifications and plugin registration. Each hook specification defines an extension point; feature packages implement `@hookimpl` decorators. Plugin manager is a singleton created via `@lru_cache`.

## Consequences

- ✅ No coupling between main lifespan and feature packages
- ✅ Type-safe hook specifications
- ✅ Auto-discovery via `auto_discover_plugins()`
- ✅ Comprehensive validation via `pm.check_pending()`
- ⚠️ Requires pluggy learn curve for hook ordering (see ADR-0027)

---

## Plugin Manager Pattern

```python
# infrastructure/hookspecs/interactions.py
import pluggy

hookspec = pluggy.HookspecMarker("sre_bot")


class SREBotHookSpec:
    @hookspec
    def handle_command(self, command):
        """Handle an incoming command dispatched by the platform provider."""

    @hookspec
    def register_commands(self, platform):
        """Register commands with the given platform provider."""
```

```python
# infrastructure/services/plugins/interactions.py
from functools import lru_cache
import pluggy
import structlog
from infrastructure import hookspecs

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_plugin_manager() -> pluggy.PluginManager:
    """Singleton plugin manager — add_hookspecs before register."""
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(hookspecs.interactions)  # ✅ specs first
    return pm
```

```python
# packages/some_package/__init__.py
from infrastructure.services import hookimpl  # ✅ import, never re-define
import structlog

logger = structlog.get_logger()


class PlatformPlugin:
    @hookimpl
    def handle_command(self, command):
        log = logger.bind(plugin="platform", command=command)
        log.info("command_handled")
```

```python
# app/server/lifespan.py  (during startup)
from infrastructure.services.plugins.base import auto_discover_plugins

pm = get_plugin_manager()
# ✅ startup-driven discovery: scans packages/ and modules/, registers all @hookimpl packages
auto_discover_plugins(pm, base_paths=["packages", "modules"])
pm.check_pending()  # ✅ raises PluginValidationError if any hookimpl has no matching spec

# Always call hooks with keyword arguments
pm.hook.handle_command(command=ctx)  # ✅ keyword args
```

---

## Usage in Initialization

```python
def initialize_features(app: FastAPI, settings: Settings):
    log = logger.bind(phase="features")
    log.info("features_initializing")

    pm = get_plugin_manager()
    app.state.plugin_manager = pm

    log.info("features_ready")
```

---

## Rules

- ✅ Import `hookspec` from `infrastructure.hookspecs`; import `hookimpl` from `infrastructure.services`
- ✅ `add_hookspecs()` called **before** any `register()` call — enables immediate hookimpl validation
- ✅ Plugin manager created once via `@lru_cache(maxsize=1)` (singleton)
- ✅ `pm.check_pending()` called after all registrations — raises `PluginValidationError` for unmatched hookimpls (unless `optionalhook=True`)
- ✅ Register plugins during lifespan startup via `auto_discover_plugins` — adding a new package under `packages/` requires no lifespan changes
- ✅ Call hooks with **keyword arguments only** — pluggy raises `HookCallError` for positional args
- ✅ Use `@hookimpl(optionalhook=True)` for hookimpls that intentionally have no matching spec
- ❌ Never define `hookspec` or `hookimpl` markers locally in feature packages — use shared imports
- ❌ Never dynamically register plugins during request handling
- ❌ Never call hooks with positional arguments


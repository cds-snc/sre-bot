---
adr_id: ADR-0026
title: "Explicit Registration Pattern"
status: Superseded
decision_type: Standard
tier: Tier-2
date_created: unknown
last_updated: 2026-04-29
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0049
related_records:
  - ADR-0025
  - ADR-0027
related_packages: []
review_state: stale
---
# Explicit Registration Pattern

## Context

Early development explored three registration patterns: import-time side effects, decorator-based auto-registration, and explicit Pluggy registration. Import-time mutations cause hidden state, test pollution, and order dependencies.

## Decision

Use explicit registration via Pluggy hooks instead of import-time auto-discovery. Feature registration occurs during lifespan startup, not at import time. Hooks are metadata markers only; actual registration happens through explicit plugin manager calls.

## Consequences

- ✅ No hidden import-time mutations or state
- ✅ Registration order is explicit and controlled
- ✅ Tests do not require registry reset teardown
- ✅ Pluggy provides battle-tested infrastructure
- ⚠️ Requires disciplined avoidance of import-time side effects

---

**Decision**: Use explicit registration via Pluggy hooks instead of import-time auto-discovery.

## The Problem

Three patterns emerged during development:

---

**Option 1: Module-Body Side Effects** (❌ Rejected)
```python
# packages/geolocate/interactions/slack.py
from infrastructure.interactions import get_slack_provider
slack = get_slack_provider()
slack.register_command("geolocate", handler)  # Runs at import time — hidden!

# main.py
from infrastructure.interactions import discover_interaction_features
discover_interaction_features()  # Imports all packages, which triggers registration
```

The call to `slack.register_command(...)` executes as a side effect of the Python import system. This makes registration order dependent on import order and makes tests that mock providers extremely fragile.

---

**Option 2: Decorator-Based Self-Registration** (❌ Rejected — the subtler anti-pattern)
```python
# modules/groups/providers/google.py
@register_primary_provider("google")       # ← executes when this class is defined
class GoogleWorkspaceProvider(PrimaryGroupProvider):
    ...

# modules/groups/providers/__init__.py
_primary_discovered: Dict[str, Type] = {}  # module-level mutable registry

def register_primary_provider(name: str):
    def decorator(cls):
        _primary_discovered[name] = cls    # ← mutates global dict at import time
        return cls
    return decorator

def load_providers():                      # called during startup
    for module_info in pkgutil.iter_modules(__path__):
        importlib.import_module(full_name) # ← triggers decorator side effects above
    activate_providers()                   # reads _primary_discovered
```

This looks more structured, but the import-time mutation of `_primary_discovered` is the same fundamental problem as Option 1. Key problems:
- `@register_primary_provider` mutates a module-level dict when the **class body is processed** — at import time
- `load_providers()` deliberately imports modules to trigger these mutations
- Each sub-system invents its own `_discovered` dict, `reset_registry()`, activation lifecycle, and validation rules
- Tests require explicit `reset_registry()` teardown; missed teardown causes cross-test pollution
- `load_providers()` couples discovery to `pkgutil.iter_modules` on a specific filesystem path — not pluggable

This pattern is present in `modules/groups/providers/` and `infrastructure/commands/providers/` and is being superseded.

---

**Option 3: Pluggy + Startup-Driven Discovery** (✅ Chosen)
```python
# packages/geolocate/__init__.py  — @hookimpl is a metadata marker only, zero side effects
from infrastructure.services import hookimpl

@hookimpl                                  # ← only attaches metadata to the function
def register_slack_commands(provider):     # no dict mutation, no external calls
    provider.register_command("geolocate", handler)

# infrastructure/services/plugins/manager.py  — scanning happens during lifespan startup
def collect_feature_i18n_resources(logger):
    pm = get_plugin_manager()
    auto_discover_plugins(pm, base_paths=["packages", "modules"])  # ← startup-time scan
    pm.hook.register_i18n_resources(registry=registry)
```

`@hookimpl` only stores metadata on the function object — no side effects. `auto_discover_plugins` performs the filesystem scan and calls `pm.register(module)` **during lifespan startup**, after the application is initializing but before it accepts requests.

## Why Pluggy + Startup Discovery is Better

### Problems with Options 1 and 2 (import-time side effects)

❌ **Hidden Mutations**: State changes during import make behavior depend on import order  
❌ **Per-Subsystem Boilerplate**: Each service reinvents discovery, registration, activation, and reset  
❌ **Test Pollution**: Module-level dicts persist across tests; `reset_registry()` must be called explicitly  
❌ **Fragile Isolation**: A missed `reset_registry()` in teardown silently passes wrong state to the next test  
❌ **Not Pluggable**: `pkgutil.iter_modules` on a hardcoded path cannot be overridden or composed  

### Advantages of Option 3

✅ **No Import-Time Side Effects**: `@hookimpl` is a marker; the module can be imported safely in any order  
✅ **Single Mechanism**: All services share pluggy's PluginManager — one discovery engine, one set of rules  
✅ **Testable**: Override providers with `dependency_overrides`; no `reset_registry()` needed  
✅ **Startup-Explicit**: Discovery is visibly invoked in lifespan; nothing hidden in module init  
✅ **Zero-Touch Extension**: Add a new `packages/` directory — nothing else changes  
✅ **Battle-Tested**: Pluggy powers pytest (1400+ plugins); industry proven  

## Implementation

### 1. Hook Specification

```python
# infrastructure/hookspecs/interactions.py
import pluggy
from typing import Protocol

hookspec = pluggy.HookspecMarker("sre_bot")

class InteractionProvider(Protocol):
    def register_command(self, *args, **kwargs): ...

@hookspec
def register_slack_commands(provider: InteractionProvider) -> None:
    """Register Slack commands with provider."""

@hookspec
def register_teams_commands(provider: InteractionProvider) -> None:
    """Register Teams commands with provider."""
```

### 2. Plugin Manager

```python
# infrastructure/services/plugins/interactions.py
from functools import lru_cache
import pluggy
import structlog
from infrastructure import hookspecs

logger = structlog.get_logger()

@lru_cache(maxsize=1)
def get_interaction_plugin_manager() -> pluggy.PluginManager:
    """Get interaction plugin manager singleton."""
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(hookspecs.interactions)
    return pm

def discover_and_register_interactions(slack_provider=None, teams_provider=None) -> None:
    """Discover and register all interaction handlers.
    
    Called explicitly during application startup via lifespan.
    Feature packages must be explicitly registered with the plugin manager
    before this is called (see lifespan startup).
    """
    pm = get_interaction_plugin_manager()
    
    if slack_provider:
        pm.hook.register_slack_commands(provider=slack_provider)
        logger.info("slack_commands_registered")
    
    if teams_provider:
        pm.hook.register_teams_commands(provider=teams_provider)
        logger.info("teams_commands_registered")
```

### 3. Feature Packages Implement Hooks

```python
# packages/geolocate/__init__.py
from infrastructure.services import hookimpl
from packages.geolocate.interactions.slack import register_commands as slack_register

@hookimpl
def register_slack_commands(provider):
    """Register geolocate Slack commands."""
    slack_register(provider)
```

### 4. Application Startup (lifespan)

Feature packages must be registered with the plugin manager **before** hooks are invoked. The canonical approach is **startup-driven discovery**: `auto_discover_plugins` scans `packages/` and `modules/` once at lifespan startup and calls `pm.register(module)` for every discovered package. Adding a new package requires **no changes to lifespan code**.

```python
# app/server/lifespan.py
from infrastructure.services.plugins.manager import (
    collect_feature_i18n_resources,
    register_feature_integrations,
)
from infrastructure.platforms import get_slack_provider, get_teams_provider

async def startup(app):
    # ✅ startup-driven discovery: auto_discover_plugins runs inside this call
    # all packages/ and modules/ packages with @hookimpl are registered automatically
    i18n_registry = collect_feature_i18n_resources(logger=logger)
    # ✅ pm.check_pending() should be called after discovery to validate hookimpls

    settings = get_settings()
    # ✅ keyword arguments only when calling hooks
    register_feature_integrations(
        app=app,
        logger=logger,
        slack_provider=get_slack_provider() if settings.slack.enabled else None,
        teams_provider=get_teams_provider() if settings.teams.enabled else None,
    )
```

New feature package — zero-touch registration:
```python
# packages/newfeature/__init__.py  — this is all that's needed
from infrastructure.services import hookimpl
from packages.newfeature.interactions.http import router

@hookimpl
def register_routes(app):
    app.include_router(router)
```

## Rules

- ✅ Hook specs define extension points (what can be extended)
- ✅ `add_hookspecs()` called **before** any `register()` call — enables immediate hookimpl validation
- ✅ Plugin manager created once via `@lru_cache(maxsize=1)` (singleton)
- ✅ Use `auto_discover_plugins` for startup-driven discovery — packages self-register via `@hookimpl`; lifespan code does not need updating when new packages are added
- ✅ `pm.check_pending()` called after all registrations — raises `PluginValidationError` for unmatched hookimpls
- ✅ Hooks called with **keyword arguments only** — pluggy raises `HookCallError` for positional args
- ✅ Registration invoked during lifespan startup; never at import time
- ✅ Use `@hookimpl(optionalhook=True)` for hookimpls that intentionally have no matching spec
- ❌ Never register at import time — `__init__.py` must only define `@hookimpl` functions, no side-effecting calls
- ❌ Never use global side effects from module imports
- ❌ Never create a new plugin manager per registration
- ❌ Never call hooks with positional arguments

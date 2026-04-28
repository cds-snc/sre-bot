---
adr_id: ADR-0027
title: "Pluggy Plugin System Integration"
status: Accepted
decision_type: Standard
tier: Tier-2
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by: []
related_records:
  - ADR-0013
  - ADR-0026
related_packages: []
review_state: stale
---
# Pluggy Plugin System Integration

## Context

The application needs a plugin system for feature registration, discovery, and initialization. Building a custom registry introduces risk and maintenance burden. pytest's Pluggy is a proven, battle-tested alternative.

## Decision

Adopt Pluggy for platform registration and discovery. Define hook specifications for extension points (e.g., register_slack_commands, register_http_routes). Feature packages implement hookimpl functions. Plugin discovery happens at lifespan startup via auto_discover_plugins.

## Consequences

- ✅ Leverages proven pytest infrastructure (1400+ plugins)
- ✅ Type safety and call ordering built-in
- ✅ Comprehensive documentation and ecosystem
- ✅ Reduces custom registry code and bugs
- ⚠️ Requires learning Pluggy patterns

---

**Decision**: Adopt Pluggy (pytest's battle-tested plugin system) for platform registration and discovery.

## Why Pluggy

**Pluggy powers pytest** with 1400+ ecosystem plugins. Instead of building custom registry:

| Need | Custom | Pluggy |
|------|--------|--------|
| Type safety | ❌ | ✅ |
| Discovery | ❌ | ✅ |
| Call ordering | ❌ | ✅ |
| Documentation | ❌ | ✅ |
| Battle-tested | ❌ | ✅ |

**Decision**: Use proven infrastructure instead of reinventing.

## Implementation Pattern

### 1. Define Hook Specifications (Extension Points)

```python
# infrastructure/hookspecs/interactions.py
"""Hook specifications for interaction provider registration."""
import pluggy
from typing import Protocol

hookspec = pluggy.HookspecMarker("sre_bot")

class InteractionProvider(Protocol):
    """Protocol for interaction providers."""
    def register_command(self, *args, **kwargs): ...

@hookspec
def register_slack_commands(provider: InteractionProvider) -> None:
    """Register Slack commands with provider."""

@hookspec
def register_teams_commands(provider: InteractionProvider) -> None:
    """Register Teams commands with provider."""

@hookspec
def register_http_routes(api_router) -> None:
    """Register HTTP routes with FastAPI router."""
```

### 2. Plugin Manager (Singleton)

```python
# infrastructure/services/plugins/interactions.py
from functools import lru_cache
import pluggy
import structlog
from infrastructure import hookspecs

logger = structlog.get_logger()

@lru_cache(maxsize=1)
def get_interaction_plugin_manager() -> pluggy.PluginManager:
    """Get interaction plugin manager singleton.
    
    Feature packages must be explicitly registered before hook invocation.
    Registration happens during application lifespan startup.
    """
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(hookspecs.interactions)
    
    logger.info("plugin_manager_initialized")
    return pm

def discover_and_register_interactions(
    slack_provider=None,
    teams_provider=None,
    discord_provider=None,
) -> None:
    """Invoke hooks for all enabled interaction providers.
    
    Explicitly invokes hooks, passing enabled providers.
    Called during application startup via lifespan after all
    feature packages have been registered with the plugin manager.
    """
    pm = get_interaction_plugin_manager()
    
    if slack_provider:
        pm.hook.register_slack_commands(provider=slack_provider)
        logger.info("slack_commands_registered")
    
    if teams_provider:
        pm.hook.register_teams_commands(provider=teams_provider)
        logger.info("teams_commands_registered")
    
    if discord_provider:
        pm.hook.register_discord_commands(provider=discord_provider)
        logger.info("discord_commands_registered")
```

### 3. Lifespan Registration

Feature packages are registered during lifespan startup via **startup-driven discovery** — the canonical approach. `auto_discover_plugins` scans `packages/` and `modules/` at startup, imports each package, and calls `pm.register(module)` for it. Adding a new feature package under `packages/` requires no changes to lifespan code.

The packages themselves must have **no import-time side effects** — `__init__.py` must only define `@hookimpl`-decorated functions and nothing else.

```python
# app/server/lifespan.py
from infrastructure.services.plugins.manager import (
    get_plugin_manager,
    collect_feature_i18n_resources,
    register_feature_integrations,
)

async def startup(app):
    # ✅ startup-driven discovery: scans packages/ and modules/ once during lifespan
    # Any package with @hookimpl functions is automatically registered
    i18n_registry = collect_feature_i18n_resources(logger=logger)

    # ... translation service initialization ...

    # ✅ invoke hooks after all packages are registered
    register_feature_integrations(
        app=app,
        logger=logger,
        slack_provider=get_slack_provider() if settings.slack.enabled else None,
        teams_provider=get_teams_provider() if settings.teams.enabled else None,
    )
```

`auto_discover_plugins` (called inside `collect_feature_i18n_resources`) uses `pkgutil.walk_packages` + `importlib.import_module` + `pm.register(module)` — all standard pluggy. `pm.check_pending()` should be called after discovery completes to validate every hookimpl has a matching hookspec.

> **Manual listing** (`pm.register(some_package)` per package) is also valid for very small, stable plugin sets where zero-touch discovery is not required.

### 4. Feature Packages Implement Hooks

```python
# packages/geolocate/__init__.py
"""Geolocate package - self-registers via Pluggy hooks."""
from infrastructure.services import hookimpl
from packages.geolocate.interactions.slack import register_commands as slack_register

@hookimpl
def register_slack_commands(provider):
    """Register geolocate Slack commands."""
    slack_register(provider)

@hookimpl
def register_http_routes(api_router):
    """Register geolocate HTTP routes."""
    from packages.geolocate.interactions.http import router
    api_router.include_router(router)
```

### 5. Export via Central Services

```python
# infrastructure/services/__init__.py
"""Central service exports."""
from infrastructure.services.providers import (
    get_settings,
    get_interaction_service,
)
from infrastructure.services.plugins.interactions import discover_and_register_interactions
from pluggy import HookimplMarker

hookimpl = HookimplMarker("sre_bot")

__all__ = [
    "get_settings",
    "get_interaction_service",
    "discover_and_register_interactions",
    "hookimpl",
]
```

## Rules

- ✅ Hook specs define extension points (what can be extended)
- ✅ Plugin managers created once via `@lru_cache(maxsize=1)` (singleton)
- ✅ Feature packages use `@hookimpl` decorators to implement hooks
- ✅ Feature packages registered during lifespan startup via `auto_discover_plugins` (startup-driven discovery) — no manual per-package imports needed
- ✅ `pm.check_pending()` called after all plugin registrations: raises `PluginValidationError` if any hookimpl has no matching hookspec and is not marked `optionalhook=True`
- ✅ `add_hookspecs()` called before `register()` to enable immediate validation
- ✅ Hooks invoked with keyword arguments only — pluggy raises `HookCallError` for positional args
- ✅ Explicit hook invocation triggers registration at runtime
- ✅ Export `hookimpl` via `infrastructure.services` for easy access
- ✅ Type-hint hook functions for IDE support and clarity
- ✅ Use `@hookimpl(optionalhook=True)` for hookimpls that intentionally have no matching spec
- ❌ Never perform registration at import time — `__init__.py` must only define `@hookimpl` functions, no side-effecting calls
- ❌ Never create plugin manager per invocation (defeats singleton pattern)
- ❌ Never register plugins after startup (initialize at lifespan startup)
- ❌ Never call hooks with positional arguments

---

## Generic Pattern for Extensible Services

This pattern applies to **any** core service that needs plugin discovery. It replaces bespoke decorator-based registries (e.g. `@register_command_provider`, `@register_primary_provider`) with a single unified mechanism.

### Services to migrate to this pattern

| Service | Current mechanism | Status |
|---|---|---|
| Feature packages (`packages/`) | Pluggy + `auto_discover_plugins` | ✅ Complete |
| i18n resource registration | Pluggy `register_i18n_resources` hookspec | ✅ Complete |
| Interaction Providers (Slack, Teams, Discord) | Pluggy `register_slack_commands` etc. | ✅ Complete |
| Commands providers (`infrastructure/commands/providers/`) | `@register_command_provider` decorator + `load_providers()` | ⚠️ Superseded by Interaction Providers — deprecate, do not extend |
| Events handlers (`infrastructure/events/discovery.py`) | Bespoke `pkgutil` filesystem walker + `_DISCOVERED_MODULES` set | ⚠️ Should migrate to pluggy hookspec |
| Groups module providers (`modules/groups/providers/`) | `@register_primary_provider` / `@register_secondary_provider` + `load_providers()` | ⚠️ Legacy `modules/` pattern — do not reference as an architectural example |

### Step 1: Define Hook Specification
```python
# infrastructure/hookspecs/<service>.py
import pluggy
hookspec = pluggy.HookspecMarker("sre_bot")

@hookspec
def register_<feature>(<target>) -> None:
    """Hook specification for <feature> registration."""
```

### Step 2: Create Plugin Manager
```python
# infrastructure/services/plugins/<service>.py
from functools import lru_cache
import pluggy

@lru_cache(maxsize=1)
def get_<service>_plugin_manager() -> pluggy.PluginManager:
    """Get <service> plugin manager singleton."""
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(hookspecs.<service>)  # specs first, then register plugins
    return pm

def discover_and_register_<service>(<target>) -> None:
    """Discover and register all <service> plugins.

    Feature packages must be registered with the plugin manager before calling this.
    Called during lifespan startup after all pm.register() calls.
    """
    pm = get_<service>_plugin_manager()
    # Always use keyword arguments when calling hooks
    pm.hook.register_<feature>(<target>=<target>)
```

### Step 3: Export via Central Services
```python
# infrastructure/services/__init__.py
from infrastructure.services.plugins.<service> import discover_and_register_<service>
```

### Step 4: Feature Packages Implement Hooks
```python
# packages/<package>/__init__.py
from infrastructure.services import hookimpl

@hookimpl
def register_<feature>(<target>):
    """Register <package> with <service>."""
    # Implementation
```

---

## Consequences

### Positive

✅ **Proven Infrastructure**: Battle-tested in pytest ecosystem (1400+ plugins)  
✅ **Type-Safe**: Full IDE support and type checking  
✅ **Explicit Control**: Clear invocation points in application lifecycle  
✅ **Extensible**: Easy to add new hook specs for new services  
✅ **Documented**: Extensive documentation and examples  
✅ **Maintained**: Community-maintained, not our burden  
✅ **Simple main.py**: Registration is centralized and clean  

### Negative

⚠️ **New Dependency**: Adds Pluggy to requirements.txt  
⚠️ **Learning Curve**: Team must learn Pluggy concepts  
⚠️ **Abstraction Layer**: Additional layer between features and services  

### Neutral

🔄 **Migration Required**: Convert existing bespoke decorator registries (`@register_command_provider`, `@register_primary_provider`, event handler discovery) to pluggy hookspecs  
🔄 **Anti-pattern to retire**: `load_providers()` functions that `pkgutil.iter_modules` over a local path to trigger decorator side effects — replace with `auto_discover_plugins` + `@hookimpl`  

---

## firstresult: Single-Value Hook Calls

By default every hook invocation collects the return values from **all** registered implementations and returns them as a `list`. For hooks that logically yield a single value (e.g. resolving a user, returning a platform config, checking feature enablement), receiving a list forces the caller to always take `results[0]` — fragile and undocumented.

Mark single-value hooks with `firstresult=True` in the spec. Pluggy stops calling implementations as soon as the first one returns a non-`None` value and returns that value directly (not wrapped in a list).

```python
# infrastructure/hookspecs/identity.py
import pluggy

hookspec = pluggy.HookspecMarker("sre_bot")

@hookspec(firstresult=True)
def resolve_user_identity(platform_id: str) -> "User | None":
    """Resolve a platform-specific user ID to a canonical User.

    Only the first non-None result is used.
    Return None to pass to the next registered resolver.
    """
```

```python
# packages/access/__init__.py
from infrastructure.services import hookimpl
from packages.access.identity import resolve_slack_user

@hookimpl
def resolve_user_identity(platform_id: str):
    """Resolve Slack user IDs; return None for non-Slack IDs."""
    if not platform_id.startswith("U"):
        return None
    return resolve_slack_user(platform_id)
```

```python
# Callsite — returns a User directly, not a list
user = pm.hook.resolve_user_identity(platform_id=slack_user_id)
if user is None:
    raise ValueError(f"No resolver found for {slack_user_id}")
```

**Decision rules:**

| Hook pattern | Use |
|---|---|
| Fan-out: every implementation runs, all results matter | default (list return) |
| First-match: stop at first non-None, rest are fallbacks | `firstresult=True` |

- ✅ Use `firstresult=True` for: resolver hooks, factory hooks, capability-check hooks
- ✅ Implementing hooks should return `None` to indicate "I cannot handle this"
- ❌ Do not use `firstresult=True` for registration hooks where all implementations must run (e.g. `register_slack_commands`)
- ❌ `firstresult=True` is **incompatible** with `historic=True` — do not combine them

---

## Call Ordering: LIFO, tryfirst, trylast

By default, hook implementations are called in **LIFO (last-in, first-out)** registered order — the most recently registered plugin's hook runs first.

```python
pm.register(Plugin_1())  # called last
pm.register(Plugin_2())  # called second
pm.register(Plugin_3())  # called first

result = pm.hook.myhook(args=())
# → [Plugin_3 result, Plugin_2 result, Plugin_1 result]
```

A hookimpl can override its call position with `tryfirst=True` or `trylast=True`:

```python
@hookimpl(tryfirst=True)
def startup_warmup(app) -> None:
    """Run before all other warmup implementations."""
    ...

@hookimpl(trylast=True)
def startup_warmup(app) -> None:
    """Run after all other warmup implementations — e.g. a default fallback."""
    ...
```

**Decision rules:**

| Need | Use |
|---|---|
| This hook must run before all others | `tryfirst=True` |
| This hook is a fallback / default | `trylast=True` |
| Order does not matter | neither (default LIFO) |

- ✅ Use `tryfirst` / `trylast` sparingly — most hooks should not need ordering
- ✅ Both flags respect LIFO within each priority category (tryfirst group is still LIFO, etc.)
- ❌ Do not rely on LIFO order for correctness; design hooks to be order-independent where possible

---

## Hook Wrappers

A hookimpl can wrap all other implementations in the same hook — useful for audit logging, tracing, or error handling around a hook call. Use new-style wrappers (`wrapper=True`, added in pluggy 1.1). Old-style `hookwrapper=True` is deprecated.

```python
# infrastructure/hookspecs/startup.py
@hookspec
def startup_warmup(app) -> None:
    """Called during application startup for each package to validate itself."""

# infrastructure/services/plugins/monitoring.py — wrapper plugin
@hookimpl(wrapper=True)
def startup_warmup(app):
    """Audit wrapper: log timing for all startup_warmup calls."""
    import time
    import structlog
    log = structlog.get_logger()
    start = time.monotonic()
    try:
        result = yield  # all other implementations run here
        log.info("warmup_complete", duration_ms=round((time.monotonic() - start) * 1000))
        return result
    except Exception:
        log.error("warmup_failed", duration_ms=round((time.monotonic() - start) * 1000))
        raise
```

**Wrapper contract:**
- Must be a generator function with exactly one `yield`
- Receive the result of all wrapped hookimpls via the `yield` expression
- Return a value or raise an exception — both propagate to further wrappers then to the caller
- All hook wrappers still run even when `firstresult=True` is set on the spec

- ✅ Use new-style `wrapper=True` (pluggy ≥ 1.1)
- ❌ Do not use old-style `hookwrapper=True` — it is deprecated and `PluggyTeardownRaisedWarning` is emitted on exception

---

## optionalhook and Opt-In Arguments

### optionalhook

If a hookimpl intentionally has no corresponding hookspec (e.g. a package implementing a hook that is only available when a specific plugin manager is present), mark it with `optionalhook=True` to suppress `check_pending()` errors:

```python
@hookimpl(optionalhook=True)
def register_discord_commands(provider) -> None:
    """Register Discord commands — only called if Discord provider is registered."""
    ...
```

Without `optionalhook=True`, calling `pm.check_pending()` after registration will raise `PluginValidationError` for any hookimpl whose name does not match a known spec.

### Opt-In Arguments (Forward Compatibility)

Hookimpls may accept **fewer** arguments than their corresponding hookspec defines. This allows specs to grow over time without breaking existing implementations:

```python
# Hookspec with two args
@hookspec
def startup_warmup(app, settings) -> None: ...

# ✅ Valid: impl only uses the arg it needs
@hookimpl
def startup_warmup(app) -> None:
    app.state.warmed_up = True

# ❌ Invalid: impl adds an arg not in the spec — raises PluginValidationError
@hookimpl
def startup_warmup(app, settings, extra) -> None: ...
```

- ✅ Add new arguments to hookspecs freely — existing hookimpls that omit them continue to work
- ❌ Never add arguments to a hookimpl that are not declared in the spec

---

## specname: Multiple Implementations in One Module

By default, a hookimpl is matched to a hookspec by function name. If you need multiple implementations of the same hook in one Python module (e.g. in a package's `__init__.py`), use `specname=`:

```python
# packages/access/__init__.py
from infrastructure.services import hookimpl

# ✅ Two implementations of the same spec in one module — both registered
@hookimpl(specname="register_slack_commands")
def register_access_slash_commands(provider) -> None:
    from packages.access.interactions.slack import register_slash_commands
    register_slash_commands(provider)

@hookimpl(specname="register_slack_commands")
def register_access_shortcut_commands(provider) -> None:
    from packages.access.interactions.slack import register_shortcuts
    register_shortcuts(provider)
```

- ✅ Use `specname=` when a single package needs to register multiple handlers for the same hook
- ❌ Do not use `specname=` to bypass spec validation for unrelated hooks

---

## Historic Hooks

A historic hook replays all previous calls to any plugin registered *after* the hook was first invoked. This is useful when the plugin registration order cannot be guaranteed (e.g. lazily loaded packages).

```python
# infrastructure/hookspecs/events.py
@hookspec(historic=True)
def on_application_ready(app) -> None:
    """Called once when the application finishes startup.

    Late-registered plugins will receive this call immediately upon registration.
    Historic hooks cannot return values to the caller — use result_callback instead.
    """
```

```python
# Calling a historic hook (call_historic, not __call__)
pm.hook.on_application_ready.call_historic(
    kwargs={"app": app},
    result_callback=lambda result: logger.info("ready_handler_result", result=result),
)

# Late registration — callback fires immediately
pm.register(late_package)  # on_application_ready fires for late_package right here
```

**Constraints:**
- Historic hooks cannot return values to the original caller (use `result_callback` for results)
- `historic=True` is **incompatible** with `firstresult=True`
- Historic hooks are called using `call_historic()`, not the normal `__call__()` syntax

**When to use:**
| Use case | Pattern |
|---|---|
| Application lifecycle events where package load order varies | `historic=True` |
| All packages registered at startup in deterministic order | standard hook |

- ✅ Use for events that must reach late-registered plugins (e.g. background warmup signals)
- ❌ Do not use for registration hooks (all plugins are explicitly registered before invocation)

---

## warn_on_impl: Deprecating Hooks

To deprecate a hookspec without breaking existing plugins immediately, use `warn_on_impl`:

```python
# infrastructure/hookspecs/interactions.py
@hookspec(
    warn_on_impl=DeprecationWarning(
        "register_slack_commands is deprecated; implement register_interaction_commands instead."
    )
)
def register_slack_commands(provider) -> None:
    """Deprecated. Use register_interaction_commands."""
```

Pluggy emits the warning for every plugin that still implements the deprecated hook. To deprecate only specific parameters (added in pluggy 1.5):

```python
@hookspec(
    warn_on_impl_args={
        "legacy_provider": DeprecationWarning(
            "The legacy_provider parameter is deprecated; use provider instead."
        )
    }
)
def register_interaction_commands(provider, legacy_provider=None) -> None: ...
```

- ✅ Use `warn_on_impl` when retiring a hookspec over multiple release cycles
- ✅ Prefer `warn_on_impl_args` (pluggy ≥ 1.5) when only a parameter is being removed
- ✅ Remove the deprecated hookspec only after all known implementations are migrated

---

## Alternatives Considered

### 1. Custom Registry System
Build our own `@register` decorator and discovery system.

**Rejected**: Reinventing the wheel. Pluggy is mature and proven.

### 2. Setuptools Entry Points
Use `entry_points` in `setup.py` for plugin discovery.

**Rejected**: 
- Requires package installation for discovery
- Less flexible than Pluggy hooks
- Harder to test in development

### 3. Import-Time Registration
Use module-level registration when packages are imported.

**Rejected**: Violates explicit registration principle (see [ADR-0026: Explicit Registration Pattern](./0026-explicit-registration-pattern.md))

---

## Usage Guidelines

### When to Create a New Hook Spec

Create a new hook specification when:
- ✅ Multiple packages need to extend a core service
- ✅ The extension point is well-defined and stable
- ✅ Features should be discovered automatically
- ✅ Registration should happen at application startup

Examples:
- ✅ `register_slack_commands` - Many packages provide commands
- ✅ `register_http_routes` - Many packages expose HTTP endpoints
- ✅ `register_event_handlers` - Many packages handle events

### When NOT to Use Pluggy

Don't use Pluggy when:
- ❌ Only one implementation exists (use direct import)
- ❌ Extension point is unstable/experimental
- ❌ Registration needs to happen at request time (use dependency injection)
- ❌ Simple configuration is sufficient (use Settings)

---

## Testing Strategy

### Testing Hook Implementations

```python
# tests/packages/geolocate/test_hooks.py
import pytest
from packages.geolocate import register_slack_commands

def test_register_slack_commands(mock_slack_provider):
    """Test Slack command registration hook."""
    # Act
    register_slack_commands(provider=mock_slack_provider)
    
    # Assert
    mock_slack_provider.register_command.assert_called_with(
        command="geolocate",
        handler=...,
        description="Geolocate IP addresses",
    )
```

### Testing Plugin Discovery

```python
# tests/infrastructure/test_platform_plugins.py
import pytest
from infrastructure.services.plugins.platforms import get_platform_plugin_manager

def test_plugin_discovery():
    """Test that all platform plugins are discovered."""
    pm = get_platform_plugin_manager()
    
    # Should discover implementations from packages
    assert len(pm.get_plugins()) > 0
    
    # Should have our hook specs
    assert pm.hook.register_slack_commands
    assert pm.hook.register_teams_commands
```

---

## References

- [Pluggy Documentation](https://pluggy.readthedocs.io/)
- [Pytest Plugin System](https://docs.pytest.org/en/stable/how-to/writing_plugins.html)

---

## Revision History

- **2026-02-05**: Initial decision captured

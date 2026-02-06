# Pluggy Plugin System Integration

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
# infrastructure/hookspecs/platforms.py
"""Hook specifications for platform command registration."""
import pluggy
from typing import Protocol

hookspec = pluggy.HookspecMarker("sre_bot")

class PlatformProvider(Protocol):
    """Protocol for platform providers."""
    def register_command(self, *args, **kwargs): ...

@hookspec
def register_slack_commands(provider: PlatformProvider) -> None:
    """Register Slack commands with provider."""

@hookspec
def register_teams_commands(provider: PlatformProvider) -> None:
    """Register Teams commands with provider."""

@hookspec
def register_http_routes(api_router) -> None:
    """Register HTTP routes with FastAPI router."""
```

### 2. Plugin Manager (Singleton)

```python
# infrastructure/services/plugins/platforms.py
from functools import lru_cache
import pluggy
import structlog
from infrastructure import hookspecs

logger = structlog.get_logger()

@lru_cache(maxsize=1)
def get_platform_plugin_manager() -> pluggy.PluginManager:
    """Get platform plugin manager singleton.
    
    Manages registration and invocation of platform hooks.
    Auto-discovers implementations in packages/ and modules/.
    """
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(hookspecs.platforms)
    auto_discover_plugins(pm, base_paths=["packages", "modules"])
    
    logger.info("plugin_manager_initialized", plugins=len(pm.get_plugins()))
    return pm

def discover_and_register_platforms(
    slack_provider=None,
    teams_provider=None,
    discord_provider=None,
) -> None:
    """Discover and register all platform commands.
    
    Explicitly invokes hooks, passing enabled providers.
    Called during application startup.
    """
    pm = get_platform_plugin_manager()
    
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

### 3. Auto-Discovery Helper

```python
# infrastructure/services/plugins/base.py
import importlib
import pkgutil
from pathlib import Path
import pluggy
import structlog

logger = structlog.get_logger()

def auto_discover_plugins(pm: pluggy.PluginManager, base_paths: list[str]) -> None:
    """Auto-discover and register plugins from base paths.
    
    Recursively imports all Python modules from specified paths,
    allowing them to register @hookimpl decorators.
    """
    for base_path in base_paths:
        path = Path(base_path)
        if not path.exists():
            logger.warning("plugin_path_not_found", path=str(path))
            continue
        
        # Import all modules to trigger @hookimpl decorators
        for module_info in pkgutil.walk_packages([str(path)], prefix=f"{base_path}."):
            try:
                module = importlib.import_module(module_info.name)
                pm.register(module)
            except Exception as e:
                logger.error("plugin_discovery_error", module=module_info.name, error=str(e))
```

### 4. Feature Packages Implement Hooks

```python
# packages/geolocate/__init__.py
"""Geolocate package - self-registers via Pluggy hooks."""
from infrastructure.services import hookimpl
from packages.geolocate.platforms.slack import register_commands as slack_register

@hookimpl
def register_slack_commands(provider):
    """Register geolocate Slack commands."""
    slack_register(provider)

@hookimpl
def register_http_routes(api_router):
    """Register geolocate HTTP routes."""
    from packages.geolocate.routes import router
    api_router.include_router(router)
```

### 5. Export via Central Services

```python
# infrastructure/services/__init__.py
"""Central service exports."""
from infrastructure.services.providers import (
    get_settings,
    get_platform_service,
)
from infrastructure.services.plugins.platforms import discover_and_register_platforms
from pluggy import HookimplMarker

hookimpl = HookimplMarker("sre_bot")

__all__ = [
    "get_settings",
    "get_platform_service",
    "discover_and_register_platforms",
    "hookimpl",
]
```

## Rules

- ✅ Hook specs define extension points (what can be extended)
- ✅ Plugin managers created once via `@lru_cache(maxsize=1)` (singleton)
- ✅ Feature packages use `@hookimpl` decorators to implement hooks
- ✅ Auto-discovery finds implementations; explicit invocation triggers registration
- ✅ Export hookimpl via `infrastructure.services` for easy access
- ✅ Type-hint hook functions for IDE support and clarity
- ❌ Never create plugin manager per invocation (defeats singleton pattern)
- ❌ Never register plugins after discovery (initialize at startup)
- ❌ Never use @hookimpl without corresponding hookspec definition
hookimpl = HookimplMarker("sre_bot")

# Plugin managers
from infrastructure.services.plugins.platforms import (
    discover_and_register_platforms,
    get_platform_plugin_manager,
)

__all__ = [
    "get_settings",
    "hookimpl",
    "discover_and_register_platforms",
    # ... other exports
]
```

### 6. Application Startup (main.py)

```python
# main.py
from infrastructure.services import (
    get_settings,
    discover_and_register_platforms,
)
from infrastructure.platforms import (
    get_slack_provider,
    get_teams_provider,
)

def providers_startup():
    """Activate platform providers at startup."""
    settings = get_settings()
    
    # Get enabled providers
    slack = get_slack_provider() if settings.slack.ENABLED else None
    teams = get_teams_provider() if settings.teams.ENABLED else None
    
    # Explicit registration via Pluggy
    discover_and_register_platforms(
        slack_provider=slack,
        teams_provider=teams,
    )

# Register startup handler
server_app.add_event_handler("startup", providers_startup)
```

---

## Generic Pattern for Extensible Services

This pattern applies to **any** core service that needs plugin discovery:

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
    pm.add_hookspecs(hookspecs.<service>)
    auto_discover_plugins(pm, base_paths=["packages", "modules"])
    return pm

def discover_and_register_<service>(<target>) -> None:
    """Discover and register all <service> plugins."""
    pm = get_<service>_plugin_manager()
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

🔄 **Migration Required**: Must convert existing registration to Pluggy hooks  
🔄 **Documentation Updates**: Must document Pluggy patterns in architecture docs  

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

**Rejected**: Violates explicit registration principle (see [02-explicit-registration-pattern.md](./02-explicit-registration-pattern.md))

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

- **Design Document**: [PLUGGY_INTEGRATION_DESIGN.md](../../../architecture/PLUGGY_INTEGRATION_DESIGN.md)
- **Pluggy Documentation**: https://pluggy.readthedocs.io/
- **Pytest Plugin System**: https://docs.pytest.org/en/stable/how-to/writing_plugins.html
- **Explicit Registration Decision**: [02-explicit-registration-pattern.md](./02-explicit-registration-pattern.md)

---

## Revision History

- **2026-02-05**: Initial decision captured

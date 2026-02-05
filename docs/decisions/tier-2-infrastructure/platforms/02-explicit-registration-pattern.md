# Explicit Registration Pattern

**Decision**: Use explicit registration via Pluggy hooks instead of import-time auto-discovery.

## The Problem

Two patterns emerged:

**Option 1: Import-Time Auto-Discovery** (❌ Rejected)
```python
# packages/geolocate/platforms/slack.py
from infrastructure.platforms import get_slack_provider
slack = get_slack_provider()
slack.register_command("geolocate", handler)  # Runs at import time - hidden!

# main.py
from infrastructure.platforms import discover_platform_features
discover_platform_features()  # Imports all packages, triggers registration
```

**Option 2: Explicit Registration via Pluggy** (✅ Chosen)
```python
# packages/geolocate/__init__.py
@hookimpl
def register_slack_commands(provider):
    """Explicitly register Slack commands."""
    provider.register_command("geolocate", handler)

# main.py
discover_and_register_platforms(slack_provider=slack)  # Explicit invocation
```

## Why Explicit is Better

### Problems with Import-Time Auto-Discovery

❌ **Hidden Side Effects**: Module imports have invisible behavior; violates "explicit is better than implicit" (PEP 20)  
❌ **Fragile**: Registration order depends on import order; circular dependency risk  
❌ **Hard to Test**: Global side effects; difficult to isolate tests  
❌ **No Control**: Cannot conditionally register based on runtime state  
❌ **Inconsistent**: FastAPI uses explicit router inclusion; creates pattern inconsistency  

### Advantages of Explicit Registration

✅ **Clear Execution**: Registration called explicitly: `discover_and_register_platforms(provider)`  
✅ **Testable**: Easy to invoke in isolation; no global state pollution  
✅ **Configurable**: Can conditionally register based on config  
✅ **Type-Safe**: Hook specs define expected signatures; IDE support  
✅ **Battle-Tested**: Pluggy powers pytest (1400+ plugins); industry proven  

## Implementation

### 1. Hook Specification

```python
# infrastructure/hookspecs/platforms.py
import pluggy
from typing import Protocol

hookspec = pluggy.HookspecMarker("sre_bot")

class PlatformProvider(Protocol):
    def register_command(self, *args, **kwargs): ...

@hookspec
def register_slack_commands(provider: PlatformProvider) -> None:
    """Register Slack commands with provider."""

@hookspec
def register_teams_commands(provider: PlatformProvider) -> None:
    """Register Teams commands with provider."""
```

### 2. Plugin Manager

```python
# infrastructure/services/plugins/platforms.py
from functools import lru_cache
import pluggy
import structlog
from infrastructure import hookspecs

logger = structlog.get_logger()

@lru_cache(maxsize=1)
def get_platform_plugin_manager() -> pluggy.PluginManager:
    """Get platform plugin manager singleton."""
    pm = pluggy.PluginManager("sre_bot")
    pm.add_hookspecs(hookspecs.platforms)
    auto_discover_plugins(pm, base_paths=["packages", "modules"])
    return pm

def discover_and_register_platforms(slack_provider=None, teams_provider=None) -> None:
    """Discover and register all platform commands.
    
    Called explicitly during application startup.
    """
    pm = get_platform_plugin_manager()
    
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
from packages.geolocate.platforms.slack import register_commands as slack_register

@hookimpl
def register_slack_commands(provider):
    """Register geolocate Slack commands."""
    slack_register(provider)
```

### 4. Application Startup

```python
# main.py
from infrastructure.services import discover_and_register_platforms
from infrastructure.platforms import get_slack_provider, get_teams_provider

settings = get_settings()

# Explicit registration
discover_and_register_platforms(
    slack_provider=get_slack_provider() if settings.slack.enabled else None,
    teams_provider=get_teams_provider() if settings.teams.enabled else None,
)
```

## Rules

- ✅ Hook specs define extension points (what can be extended)
- ✅ Plugin manager created once via `@lru_cache(maxsize=1)` (singleton)
- ✅ Feature packages use `@hookimpl` decorators
- ✅ Registration invoked explicitly in application startup
- ✅ Auto-discover implementations but explicit invoke registration
- ❌ Never register at import time
- ❌ Never use global side effects from module imports
- ❌ Never create new plugin manager per registration

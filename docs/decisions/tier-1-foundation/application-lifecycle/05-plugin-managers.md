# Plugin Managers

Plugin system using Pluggy for extensible platform integrations.

---

## Plugin Manager Pattern

```python
import pluggy
import structlog

logger = structlog.get_logger()

hookspec = pluggy.HookspecMarker("sre_bot")
hookimpl = pluggy.HookimplMarker("sre_bot")

class SREBotHookSpec:
    @hookspec
    def handle_command(self, command):
        """Handle incoming command."""
        pass
    
    @hookspec
    def register_commands(self, platform):
        """Register commands with platform."""
        pass

class PlatformPlugin:
    @hookimpl
    def handle_command(self, command):
        log = logger.bind(plugin="platform", command=command)
        log.info("command_handled")
        # Handle command...

# Initialize plugin manager
manager = pluggy.PluginManager("sre_bot")
manager.add_hookspecs(SREBotHookSpec)
manager.register(PlatformPlugin())
```

---

## Usage in Initialization

```python
def initialize_features(app: FastAPI, settings: Settings):
    log = logger.bind(phase="features")
    log.info("features_initializing")
    
    # Create and register plugin manager
    manager = initialize_plugin_manager()
    app.state.plugin_manager = manager
    
    log.info("features_ready")
```

---

## Rules

- ✅ Use Pluggy for plugin system
- ✅ Define hook specs clearly
- ✅ Register plugins during initialization
- ✅ Store manager in `app.state`
- ❌ Never dynamically register plugins during request handling

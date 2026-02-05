# Provider Discovery

Discover and activate providers in strict order during initialization Phase 3.

---

## Provider Load Order

1. **Group Providers** - IdP integrations (Google Workspace, Azure, Okta, AWS)
2. **Command Providers** - Domain-specific commands
3. **Platform Providers** - Slack, Teams

```python
def initialize_providers(settings: Settings) -> dict:
    log = logger.bind(phase="providers")
    log.info("providers_initializing")
    
    providers = {
        "groups": load_group_providers(settings),
        "commands": load_command_providers(settings),
        "platforms": load_platform_providers(settings),
    }
    
    log.info("providers_ready", 
             groups=len(providers["groups"]),
             commands=len(providers["commands"]),
             platforms=len(providers["platforms"]))
    return providers
```

---

## Rules

- ✅ Load in strict order: Groups → Commands → Platforms
- ✅ Fail fast on missing required providers
- ✅ Log provider count for each category
- ✅ Store in `app.state.providers`
- ❌ Never dynamically add providers after startup

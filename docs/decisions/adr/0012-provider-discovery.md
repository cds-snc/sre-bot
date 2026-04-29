---
adr_id: ADR-0012
title: "Provider Discovery"
status: Superseded
decision_type: Principle
tier: Tier-1
date_created: unknown
last_updated: 2026-04-29
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - SRE Team
supersedes: []
superseded_by:
  - ADR-0056
related_records:
  - ADR-0005
  - ADR-0011
  - ADR-0013
  - ADR-0026
  - ADR-0027
related_packages: []
review_state: stale
---
# Provider Discovery

## Context

Three provider types (Groups, Commands, Platforms) have interdependencies. Groups must load before Commands (which may depend on group information); both must load before Platforms. We need a strict ordering mechanism.

## Decision

Load providers in fixed order during Phase 3: Groups → Commands → Platforms. Log provider counts for each category. Fail fast if any required provider is missing.

## Consequences

- ✅ Predictable provider initialization
- ✅ Observable provider status via logs
- ⚠️ Provider load order is fixed; cannot be customized per deployment

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

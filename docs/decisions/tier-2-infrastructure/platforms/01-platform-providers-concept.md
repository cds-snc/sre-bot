# Platform Providers Concept

**Decision**: Replace "Command Provider" (text-only) with "Platform Providers" (multi-feature abstraction).

## Why

Modern platforms offer rich interactive features beyond commands:
- Commands (slash commands, bot mentions)
- Views/Modals (forms, workflows)
- Interactive Components (buttons, dropdowns, date pickers)
- Messaging (DMs, threads, file attachments)
- Message Actions (context menus, forwarding)

Command-only abstraction limited us to lowest-common-denominator text interfaces.

## What Changed

**Before** (Command Providers):
```python
class CommandProvider:
    def register_command(self, name: str, handler: Callable): ...
```

**After** (Platform Providers):
```python
class PlatformProvider:
    def register_command(self, name: str, handler: Callable): ...
    def register_view(self, view_id: str, handler: Callable): ...
    def register_action(self, action_id: str, handler: Callable): ...
    def send_message(self, channel: str, content: dict): ...
    def upload_file(self, channel: str, file: bytes): ...
```

## Platform Capabilities Matrix

| Platform | Commands | Views | Actions | Messaging | Files |
|----------|----------|-------|---------|-----------|-------|
| **Slack** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Teams** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Discord** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **HTTP API** | ✅ | ❌ | ❌ | ✅ | ✅ |

## CRITICAL: Business Logic HTTP-First

Business logic exposed as **FastAPI endpoints first**. Platform providers wrap endpoints for native experiences.

```
HTTP Request → FastAPI → Business Logic → JSON
Slack Command → Slack Provider → Internal HTTP → JSON → Block Kit
Teams Message → Teams Provider → Internal HTTP → JSON → Adaptive Card
```

This ensures:
- ✅ Business logic platform-agnostic
- ✅ Easy testing (HTTP, no SDK mocking)
- ✅ Platform-independent
- ✅ API-first preserved

## Implementation

```
infrastructure/platforms/
├── base.py                  # BasePlatformProvider (interface)
└── providers/
    ├── slack.py             # SlackPlatformProvider
    ├── teams.py             # TeamsPlatformProvider
    └── discord.py           # DiscordPlatformProvider
```

**Feature packages register capabilities**:
```python
# packages/geolocate/platforms/slack.py
slack = get_slack_provider()

slack.register_command(
    command="geolocate",
    handler=handle_geolocate_command,
    description="Geolocate IP addresses",
)

slack.register_action(
    action_id="show_more_details",
    handler=handle_show_more_details,
)
```

**Environment-based enablement**:
```bash
SLACK__ENABLED=true
SLACK__APP_TOKEN=xapp-...
SLACK__BOT_TOKEN=xoxb-...

TEAMS__ENABLED=true
TEAMS__APP_ID=...

DISCORD__ENABLED=false
```

## Rules

- ✅ All business logic exposed as HTTP endpoints first
- ✅ Platform providers wrap HTTP endpoints
- ✅ Each platform uses its native capabilities
- ✅ Configuration-driven platform enablement
- ❌ Never implement platform-specific business logic
- ❌ Never hardcode platform selection
- ❌ Never skip HTTP endpoint in favor of platform-direct integration

## References

- [02-explicit-registration-pattern.md](./02-explicit-registration-pattern.md) - Registration method
- [03-pluggy-plugin-system.md](./03-pluggy-plugin-system.md) - Implementation infrastructure
- [04-platform-feature-isolation.md](./04-platform-feature-isolation.md) - Package structure

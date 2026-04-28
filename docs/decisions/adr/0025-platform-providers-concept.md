---
adr_id: ADR-0025
title: "Interaction Providers Concept"
status: Accepted
decision_type: Standard
tier: Tier-2
date_created: unknown
last_updated: 2026-04-28
last_reviewed: unknown
next_review_due: 2026-04-28
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records: []
related_packages: []
review_state: stale
---
# Interaction Providers Concept

**Decision**: Standardize and isolate collaboration platform capabilities as a centrally managed core service through typed Interaction Provider implementations.

## Why

Collaboration platforms (Slack, Teams, Discord) offer rich interactive features that span multiple interaction modes:
- Commands (slash commands, bot mentions)
- Views/Modals (forms, multi-step workflows)
- Interactive Components (buttons, dropdowns, date pickers)
- Messaging (DMs, threads, file attachments)
- Message Actions (context menus, shortcuts)

A single abstraction — the Interaction Provider — exposes all of these capabilities behind a typed interface, isolating feature packages from platform SDK details.

## Provider Interface

```python
class InteractionProvider:
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

Business logic is exposed as **FastAPI HTTP endpoints** (`interactions/http.py`) so it remains independently testable and accessible. However, Slack and Teams interaction handlers in feature packages do **not** call that HTTP endpoint internally — they call the service layer directly.

The Interaction Provider (infrastructure) owns the channel protocol:
- `SlackInteractionProvider` manages the WebSocket connection, acknowledgment, and response delivery
- `TeamsInteractionProvider` manages the bot framework channel and adaptive card delivery

Feature handlers receive a structured payload from the provider, call business logic via `ingress.py`, format with `presenters.py`, and return the result. The provider handles delivery.

```
HTTP Request  → interactions/http.py  → ingress.py → service.py → presenter → JSON response
Slack Interaction → SlackInteractionProvider (WebSocket, ack) → interactions/slack.py → ingress.py → service.py → presenter → Block Kit
Teams Interaction → TeamsInteractionProvider → interactions/teams.py → ingress.py → service.py → presenter → Adaptive Card
```

This ensures:
- ✅ Business logic testable over HTTP independently of any channel
- ✅ No internal HTTP calls between feature interaction handlers and business logic
- ✅ Channel protocol details (WebSocket, bot framework) isolated in infrastructure providers
- ✅ Consistent service invocation path regardless of inbound channel

## Implementation

```
infrastructure/interactions/
├── base.py                  # BaseInteractionProvider (interface)
├── service.py               # InteractionService (central registry and dispatcher)
└── providers/
    ├── slack.py             # SlackInteractionProvider
    ├── teams.py             # TeamsInteractionProvider
    └── discord.py           # DiscordInteractionProvider
```

**Feature packages register capabilities**:
```python
# packages/geolocate/interactions/slack.py
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

- [ADR-0026: Explicit Registration Pattern](./0026-explicit-registration-pattern.md) - Registration method
- [ADR-0027: Pluggy Plugin System Integration](./0027-pluggy-plugin-system.md) - Implementation infrastructure
- [ADR-0028: Feature Interaction Layer Isolation](./0028-platform-feature-isolation.md) - Package structure

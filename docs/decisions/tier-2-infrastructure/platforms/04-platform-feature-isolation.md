# Platform Feature Isolation in Packages

**Decision**: Feature packages in `/packages/` use standardized structure isolating platform-specific code in dedicated `platforms/` subdirectory.

## Standard Package Structure

```
packages/<feature>/
├── __init__.py              # Pluggy hooks (@hookimpl)
├── routes.py                # FastAPI routes (HTTP-first, platform-agnostic)
├── schemas.py               # Pydantic models
├── service.py               # Business logic (platform-agnostic)
├── platforms/               # Platform-specific adapters
│   ├── slack.py             # Slack command/view/action handlers
│   ├── teams.py             # Teams command/card handlers
│   └── discord.py           # Discord command/modal handlers
├── providers/               # External services (optional)
│   └── google.py            # Google Workspace integration
└── tests/
    ├── test_routes.py       # HTTP endpoint tests
    ├── test_service.py      # Business logic tests
    └── test_platforms.py    # Platform adapter tests
```

## Directory Responsibilities

**`__init__.py`** - Pluggy hook implementations (registration entry point):
```python
"""<Feature> package - self-registers via Pluggy hooks."""
from infrastructure.services import hookimpl
from packages.<feature>.routes import router
from packages.<feature>.platforms import slack

@hookimpl
def register_http_routes(api_router):
    """Register HTTP routes."""
    api_router.include_router(router)

@hookimpl
def register_slack_commands(provider):
    """Register Slack commands."""
    slack.register_commands(provider)
```

**`routes.py`** - FastAPI HTTP routes (primary interface, platform-agnostic):
```python
"""HTTP routes for <feature> - platform-agnostic interface."""
from fastapi import APIRouter
from infrastructure.services import SettingsDep
from packages.<feature>.service import execute_business_logic

router = APIRouter(prefix="/<feature>")

@router.post("/action")
def perform_action(request: SomeRequest, settings: SettingsDep):
    """Perform action - this is the primary interface.
    
    Platform adapters call this internally.
    """
    result = execute_business_logic(request, settings)
    return result
```

**`service.py`** - Business logic (completely platform-agnostic):
```python
"""Business logic - platform-agnostic."""
from infrastructure.operations import OperationResult

def execute_business_logic(request, settings) -> OperationResult:
    """Execute core business logic.
    
    No knowledge of platforms (Slack, Teams, etc.).
    Works with domain models, returns OperationResults.
    """
    # Business logic
    return OperationResult.success(data=result)
```

**`platforms/slack.py`** - Slack command/view/action handlers:
```python
"""Slack platform integration for <feature>."""
import httpx

def handle_slack_command(ack, command, client):
    """Handle Slack slash command.
    
    Acknowledges immediately, then calls internal HTTP endpoint.
    """
    ack()  # Acknowledge within 3 seconds
    
    # Call internal HTTP API
    response = httpx.post(
        "http://localhost:8000/api/v1/<feature>/action",
        json={"param": command["text"]},
    )
    
    # Format response as Block Kit
    client.chat_postMessage(
        channel=command["channel_id"],
        blocks=format_as_block_kit(response.json()),
    )

def register_commands(provider):
    """Register all Slack commands for this feature."""
    provider.register_command(
        command="<feature>",
        handler=handle_slack_command,
        description="<Feature> description",
    )
```

**`platforms/teams.py`** - Teams command/card handlers:
```python
"""Microsoft Teams platform integration for <feature>."""
import httpx

def handle_teams_command(turn_context):
    """Handle Teams bot command.
    
    Acknowledges immediately, then calls internal HTTP endpoint.
    """
    # Send typing indicator (acknowledgment)
    turn_context.send_activity("Processing...")
    
    # Call internal HTTP API
    response = httpx.post(
        "http://localhost:8000/api/v1/<feature>/action",
        json={"param": turn_context.activity.text},
    )
    
    # Format response as Adaptive Card
    turn_context.send_activity(
        format_as_adaptive_card(response.json())
    )

def register_commands(provider):
    """Register all Teams commands for this feature."""
    provider.register_command(
        command="<feature>",
        handler=handle_teams_command,
        description="<Feature> description",
    )
```

## Examples

**Geolocate Package**:
```
packages/geolocate/
├── __init__.py              # Pluggy hooks
├── routes.py                # POST /geolocate/ip
├── schemas.py               # GeolocateRequest, Response
├── service.py               # geolocate_ip(ip: str) -> OperationResult
├── platforms/
│   ├── slack.py             # /geolocate command → Block Kit
│   └── teams.py             # @bot geolocate → Adaptive Card
└── tests/
```

**Groups Management Package**:
```
packages/groups/
├── __init__.py              # Pluggy hooks
├── routes.py                # POST /groups/add, GET /groups/list
├── schemas.py               # AddMemberRequest, GroupList
├── service.py               # add_member(), list_groups()
├── platforms/
│   ├── slack.py             # /sre groups add → Block Kit
│   ├── teams.py             # @bot groups add → Adaptive Card
│   └── discord.py           # /groups add → Embed
├── providers/
│   └── google.py            # Google Workspace Groups API
└── tests/
```

## Rules

- ✅ Each platform has dedicated adapter file (slack.py, teams.py, discord.py)
- ✅ Platform-specific code isolated in `platforms/` subdirectory
- ✅ Business logic in `service.py` is completely platform-agnostic
- ✅ HTTP endpoints in `routes.py` expose business logic first
- ✅ Platform adapters call internal HTTP endpoints (not business logic directly)
- ✅ All platform integrations self-register via Pluggy hooks in `__init__.py`
- ✅ Each package independently testable
- ❌ Never import platform-specific SDK in business logic (service.py)
- ❌ Never implement platform-specific branching in routes.py
- ❌ Never call business logic functions directly from platform adapters

---

## Footnote: Async Teams Adapters (Future)

Async adapters are deferred until the async-first migration. When that happens,
prefer async handlers and await SDK calls.

```python
# Future async example (not current standard)
import httpx

async def handle_teams_command(turn_context):
    await turn_context.send_activity("Processing...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/<feature>/action",
            json={"param": turn_context.activity.text},
        )
    await turn_context.send_activity(
        format_as_adaptive_card(response.json())
    )
```
```

---

## Migration Path: `/modules/` → `/packages/`

Features currently in `/modules/` will gradually migrate to `/packages/` structure:

### Phase 1: New Features (Immediate)
- ✅ All new features MUST use `/packages/` structure
- ✅ Follow the standard directory layout
- ✅ Implement Pluggy hooks in `__init__.py`

### Phase 2: Greenfield Refactoring (Opportunistic)
- When making significant changes to a module, migrate it to packages
- Refactor to separate platforms/ subdirectory
- Add Pluggy hooks

### Phase 3: Systematic Migration (Future)
- After patterns stabilize, systematically migrate remaining modules
- Update tests and documentation
- Deprecate `/modules/` for feature packages

### Coexistence
During migration, both `/modules/` and `/packages/` will coexist:
- `/modules/` - Legacy features (pre-platform-providers)
- `/packages/` - New architecture (platform-providers + Pluggy)

---

## Package Naming Conventions

### Package Names
- Use singular nouns: `geolocate`, `incident`, `group` (not `groups`)
- Use lowercase: `packages/geolocate/` (not `packages/GeoLocate/`)
- Use underscores for multi-word: `packages/access_request/`

### Platform File Names
- Always lowercase: `slack.py`, `teams.py`, `discord.py`
- Match platform name exactly

### Hook Implementation Names
- Format: `register_<platform>_<feature_type>`
- Examples: `register_slack_commands`, `register_http_routes`, `register_event_handlers`

---

## Testing Conventions

### Test Organization
```
tests/
├── test_routes.py           # HTTP endpoint tests (platform-agnostic)
├── test_service.py          # Business logic tests (pure functions)
├── test_schemas.py          # Pydantic model validation tests
└── test_platforms.py        # Platform adapter tests (all platforms)
```

### Testing Platform Adapters

```python
# tests/test_platforms.py
import pytest
from packages.<feature>.platforms import slack, teams

def test_slack_command_registration(mock_slack_provider):
    """Test Slack command registration."""
    slack.register_commands(mock_slack_provider)
    
    mock_slack_provider.register_command.assert_called_once_with(
        command="<feature>",
        handler=slack.handle_slack_command,
        description="<Feature> command",
    )

def test_slack_command_calls_http_endpoint(mock_httpx):
    """Test Slack command handler calls HTTP API."""
    # Mock ack and command
    ack = Mock()
    command = {"text": "test", "channel_id": "C123"}
    client = Mock()
    
    # Execute handler
    slack.handle_slack_command(ack, command, client)
    
    # Should acknowledge immediately
    ack.assert_called_once()
    
    # Should call HTTP endpoint
    mock_httpx.post.assert_called_with(
        "http://localhost:8000/api/v1/<feature>/action",
        json={"param": "test"},
    )
```

---

## References

- **Design Document**: [FEATURE_PACKAGE_STRUCTURE_DESIGN.md](../../../architecture/FEATURE_PACKAGE_STRUCTURE_DESIGN.md)
- **Refactoring Proposal**: [PACKAGES_REFACTORING_PROPOSAL.md](../../../architecture-review/PACKAGES_REFACTORING_PROPOSAL.md)
- **Pluggy Integration**: [03-pluggy-plugin-system.md](./03-pluggy-plugin-system.md)
- **Platform Providers**: [01-platform-providers-concept.md](./01-platform-providers-concept.md)

---

## Revision History

- **2026-02-05**: Initial decision captured

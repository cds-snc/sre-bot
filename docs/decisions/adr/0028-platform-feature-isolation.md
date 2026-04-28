---
adr_id: ADR-0028
title: "Feature Interaction Layer Isolation"
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
    - ADR-0025
    - ADR-0027
    - ADR-0032
related_packages: []
review_state: stale
---
# Feature Interaction Layer Isolation

**Decision**: Feature packages isolate all inbound channel handlers (HTTP, Slack, Teams) in a dedicated `interactions/` subdirectory. Outbound external integrations remain in `adapters/`.

## Standard Package Structure

```
packages/<feature>/
├── __init__.py              # Pluggy hooks (@hookimpl)
├── schemas.py               # Pydantic request/response models
├── domain.py                # Internal frozen dataclass models
├── service.py               # Business logic (channel-agnostic)
├── providers.py             # @lru_cache DI factory functions
├── presenters.py            # Shared response shape mapping (optional)
├── adapters/                # Outbound: Protocol-defined external integrations
│   ├── __init__.py            # Adapter Protocol contract
│   └── <provider>.py          # Provider-specific implementation
└── interactions/            # Inbound: channel-specific request handlers
    ├── ingress.py             # Shared admission logic (enabled-check, lock-check, job spawn)
    ├── http.py                # FastAPI route handlers
    ├── slack.py               # Slack command/view/action handlers
    └── teams.py               # Teams command/card handlers (when applicable)
```

## Directory Responsibilities

**`__init__.py`** - Pluggy hook implementations (registration entry point):
```python
"""<Feature> package - self-registers via Pluggy hooks."""
from infrastructure.services import hookimpl
from packages.<feature>.interactions.http import router
from packages.<feature>.interactions import slack

@hookimpl
def register_http_routes(api_router):
    """Register HTTP routes."""
    api_router.include_router(router)

@hookimpl
def register_slack_commands(provider):
    """Register Slack commands."""
    slack.register_commands(provider)
```

**`interactions/http.py`** - FastAPI HTTP routes (primary interface, channel-agnostic):
```python
"""HTTP interaction handler for <feature>."""
from fastapi import APIRouter, HTTPException
from typing import Annotated, Protocol
from fastapi import Depends
from packages.<feature>.providers import get_feature_settings, get_feature_service
from packages.<feature>.interactions.ingress import admit_sync_request
from packages.<feature>.schemas import FeatureRequest, FeatureResponse

router = APIRouter(prefix="/<feature>")

@router.post("/action")
def perform_action(request: FeatureRequest) -> FeatureResponse:
    """Primary HTTP interface — testable independently of any channel."""
    result = admit_sync_request(param=request.param)
    if result.is_success:
        return FeatureResponse(success=True, data=result.data)
    raise HTTPException(status_code=400, detail=result.message)
```

**`interactions/ingress.py`** - Shared admission logic (enabled-check, lock-check, job spawn):
```python
"""Shared admission logic for all interaction channels.

Both the HTTP route handler and the Slack command handlers admit requests
through these shared functions so that enabled-check, lock-check, and job
spawn behaviour is identical regardless of the calling channel.
"""

def admit_sync_request(param: str) -> OperationResult:
    settings = get_feature_settings()
    if not settings.enabled:
        raise FeatureDisabledError()
    service = get_feature_service()
    return service.do_action(param=param)
```

**`interactions/slack.py`** - Slack command/view/action handlers:
```python
"""Slack interaction handlers for <feature>.

The SlackInteractionProvider (infrastructure) manages the WebSocket
connection, acknowledgment, and response delivery. Handlers here
call business logic directly via ingress and format results with
presenters. No internal HTTP calls.
"""
from packages.<feature>.interactions.ingress import admit_sync_request
from packages.<feature>.presenters import to_slack_blocks

def handle_slack_command(ack, command, say):
    """Handle Slack slash command.
    
    ack() is called by the SlackInteractionProvider before dispatching here.
    Handler calls service layer directly and returns Block Kit response.
    """
    result = admit_sync_request(param=command["text"])
    say(blocks=to_slack_blocks(result))

def register_commands(provider):
    """Register all Slack commands for this feature."""
    provider.register_command(
        command="<feature>",
        handler=handle_slack_command,
        description="<Feature> description",
    )
```

**`service.py`** - Business logic (completely channel-agnostic):
```python
"""Business logic - channel-agnostic."""
from infrastructure.operations import OperationResult

def execute_business_logic(request, settings) -> OperationResult:
    """Execute core business logic.
    
    No knowledge of channels (Slack, Teams, HTTP).
    Works with domain models, returns OperationResults.
    """
    return OperationResult.success(data=result)
```

**`interactions/teams.py`** - Teams command/card handlers:
```python
"""Teams interaction handler for <feature>.

The TeamsInteractionProvider (infrastructure) manages the bot framework
channel and adaptive card delivery. Handlers call business logic
directly via ingress and format results with presenters.
"""
from packages.<feature>.interactions.ingress import admit_sync_request
from packages.<feature>.presenters import to_adaptive_card

def handle_teams_command(turn_context):
    """Handle Teams bot command."""
    result = admit_sync_request(param=turn_context.activity.text)
    turn_context.send_activity(
        to_adaptive_card(result)
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
├── schemas.py               # GeolocateRequest, Response
├── service.py               # geolocate_ip(ip: str) -> OperationResult
├── interactions/
│   ├── http.py              # POST /geolocate/ip
│   └── slack.py             # /geolocate command → Block Kit
└── tests/
```

**Groups Management Package**:
```
packages/groups/
├── __init__.py              # Pluggy hooks
├── schemas.py               # AddMemberRequest, GroupList
├── service.py               # add_member(), list_groups()
├── adapters/
│   └── google.py            # Google Workspace Groups API
├── interactions/
│   ├── http.py              # POST /groups/add, GET /groups/list
│   ├── slack.py             # /sre groups add → Block Kit
│   └── teams.py             # @bot groups add → Adaptive Card
└── tests/
```

## Rules

- ✅ All inbound channel handlers (HTTP, Slack, Teams) live inside `interactions/`
- ✅ Outbound Protocol-defined integrations (AWS, Google) live inside `adapters/`
- ✅ Business logic in `service.py` is completely channel-agnostic
- ✅ HTTP endpoints in `interactions/http.py` expose business logic as a testable surface
- ✅ Interaction handlers call `ingress.py` directly — no internal HTTP calls between feature handlers and business logic
- ✅ Shared admission logic (enabled-check, lock-check) lives in `interactions/ingress.py`
- ✅ Response formatting via `presenters.py` — one presenter function per channel shape
- ✅ All interaction registrations self-register via Pluggy hooks in `__init__.py`
- ✅ Channel protocol details (WebSocket, bot framework, HTTP delivery) are owned by Interaction Providers in infrastructure
- ✅ Each package independently testable
- ❌ Never import channel-specific SDK (`slack_bolt`, `botframework`) in feature packages — providers own SDKs
- ❌ Never make internal HTTP calls from feature interaction handlers (`httpx.post` to own endpoints)
- ❌ Never implement channel-specific branching in `interactions/ingress.py`

---

## Package Naming Conventions

### Package Names
- Use singular nouns: `geolocate`, `incident`, `group` (not `groups`)
- Use lowercase: `packages/geolocate/` (not `packages/GeoLocate/`)
- Use underscores for multi-word: `packages/access_request/`

### Interaction File Names
- Named after their channel: `http.py`, `slack.py`, `teams.py`, `discord.py`
- Always lowercase; match channel name exactly
- Shared admission logic: `ingress.py`

### Hook Implementation Names
- Format: `register_<channel>_<feature_type>`
- Examples: `register_slack_commands`, `register_http_routes`, `register_event_handlers`

---

## Testing Conventions

### Test Organization
```
tests/
├── test_http.py             # HTTP route tests
├── test_service.py          # Business logic tests (pure functions)
├── test_schemas.py          # Pydantic model validation tests
├── test_slack.py            # Slack interaction handler tests
└── test_ingress.py          # Shared admission logic tests
```

### Testing Interaction Handlers

```python
# tests/test_slack.py
import pytest
from unittest.mock import Mock, patch
from packages.<feature>.interactions import slack

def test_slack_command_registration(mock_slack_provider):
    """Test Slack command registration."""
    slack.register_commands(mock_slack_provider)
    
    mock_slack_provider.register_command.assert_called_once_with(
        command="<feature>",
        handler=slack.handle_slack_command,
        description="<Feature> command",
    )

def test_slack_command_calls_service_via_ingress():
    """Test Slack command handler calls service layer — not HTTP."""
    say = Mock()
    command = {"text": "test", "channel_id": "C123"}
    
    with patch("packages.<feature>.interactions.slack.admit_sync_request") as mock_admit:
        mock_admit.return_value = OperationResult.success(data={"result": "ok"})
        slack.handle_slack_command(command=command, say=say)
    
    mock_admit.assert_called_once_with(param="test")
    say.assert_called_once()
```

---


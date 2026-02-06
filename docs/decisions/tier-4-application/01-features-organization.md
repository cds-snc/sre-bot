# Features Organization

## Feature Package Structure

**Decision**: Feature packages follow vertical slice architecture.

**Structure**:
```
packages/groups/
├── __init__.py
├── routes.py              # FastAPI routes (HTTP interface)
├── service.py             # Business logic (platform-agnostic)
├── schemas.py             # Pydantic request/response models
└── platforms/             # Platform-specific adapters
    ├── __init__.py
    ├── slack.py           # Slack command/view handlers
    └── teams.py           # Teams command/view handlers
```

**Package Export**:
```python
# packages/groups/__init__.py
from packages.groups.routes import router

__all__ = ["router"]
```

**Rules**:
- ✅ Each package is complete vertical slice
- ✅ Routes in `routes.py` (HTTP interface, platform-agnostic)
- ✅ Business logic in `service.py` (platform-agnostic functions)
- ✅ Platform adapters in `platforms/` (call routes internally)
- ✅ Export router for FastAPI registration
- ✅ Enforce tier-1, tier-2, tier-3 standards (TYPE_CHECKING, logging, OperationResult)
- ❌ No cross-package dependencies (use infrastructure services)

---

## Routes Pattern (HTTP Interface)

**Decision**: Routes are platform-agnostic HTTP endpoints.

**Complete Implementation**:
```python
# packages/groups/routes.py
from typing import TYPE_CHECKING
import structlog
from fastapi import APIRouter

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

from infrastructure.services import SettingsDep, AWSClientsDep
from packages.groups.schemas import AddMemberRequest, AddMemberResponse
from packages.groups.service import add_member_to_group

logger = structlog.get_logger()
router = APIRouter(prefix="/groups", tags=["groups"])

@router.post("/members")
def add_member(
    request: AddMemberRequest,
    aws_clients: AWSClientsDep,
    settings: SettingsDep,
) -> AddMemberResponse:
    """Add member to group (platform-agnostic).
    
    Called by:
    - External API (JWT auth)
    - Slack adapter (internal call)
    - Teams adapter (internal call)
    """
    import uuid
    request_id = str(uuid.uuid4())
    
    log = logger.bind(
        group_id=request.group_id,
        user_email=request.user_email,
        request_id=request_id,
    )
    log.info("add_member_request")
    
    result = add_member_to_group(
        group_id=request.group_id,
        user_email=request.user_email,
        aws_clients=aws_clients,
        request_id=request_id,
    )
    
    if result.is_success:
        log.info("member_added")
        return AddMemberResponse(success=True, data=result.data)
    
    log.error("add_member_failed", error=result.message)
    return AddMemberResponse(success=False, message=result.message)
```

**Reference**: [Platform Integration Conventions](../../decisions/tier-2-infrastructure/04-command-framework-platform-abstraction.md)

**Rules**:
- ✅ TYPE_CHECKING for Settings class import
- ✅ Settings injected via SettingsDep
- ✅ Infrastructure clients injected (AWSClientsDep, etc.)
- ✅ Module-level logger only
- ✅ Request-scoped context binding (request_id, group_id, user_email)
- ✅ Business logic returns OperationResult
- ✅ Route converts OperationResult to Pydantic response
- ❌ No platform-specific logic (Slack, Teams) in routes
- ❌ No self.logger in classes

---

## Service Pattern (Business Logic)

**Decision**: Business logic is platform-agnostic.

**Complete Implementation**:
```python
# packages/groups/service.py
from typing import TYPE_CHECKING
import structlog

if TYPE_CHECKING:
    from infrastructure.clients.aws import AWSClients

from infrastructure.operations import OperationResult

logger = structlog.get_logger()

def add_member_to_group(
    group_id: str,
    user_email: str,
    aws_clients: "AWSClients",
    request_id: str,
) -> OperationResult:
    """Add member to group (platform-agnostic business logic).
    
    Args:
        group_id: Group identifier
        user_email: User email to add
        aws_clients: AWS clients facade
        request_id: Request ID for logging
    
    Returns:
        OperationResult with member data or error
    """
    log = logger.bind(
        group_id=group_id,
        user_email=user_email,
        request_id=request_id,
    )
    log.info("adding_member")
    
    result = aws_clients.iam.add_user_to_group(
        group_id=group_id,
        user_email=user_email,
        request_id=request_id,
    )
    
    if not result.is_success:
        log.error("aws_add_failed", error=result.message)
        return result
    
    log.info("member_added")
    return OperationResult.success(
        data={"group_id": group_id, "user_email": user_email},
        message="Member added successfully",
    )
```

**Reference**: [Operation Result Pattern](../../decisions/tier-2-infrastructure/03-operation-result-pattern.md)

**Rules**:
- ✅ TYPE_CHECKING for infrastructure client imports
- ✅ All dependencies injected as parameters
- ✅ Module-level logger only
- ✅ Request-scoped context binding
- ✅ Return OperationResult (not exceptions)
- ✅ Check result.is_success (property, not method)
- ❌ No Settings import outside TYPE_CHECKING
- ❌ No platform-specific logic
- ❌ No calling get_settings() or get_*_clients()

---

## Platform Adapters

**Decision**: Platform adapters call internal HTTP endpoints.

**Complete Implementation**:
```python
# packages/groups/platforms/slack.py
from typing import TYPE_CHECKING
import structlog
import httpx

if TYPE_CHECKING:
    from infrastructure.configuration import Settings

from infrastructure.platforms.formatters import get_formatter
from infrastructure.platforms.models import Card

logger = structlog.get_logger()

def handle_add_member_command(
    payload: dict,
    request_id: str,
    settings: "Settings",
) -> dict:
    """Handle Slack command event (received via WebSocket).
    
    Flow:
    1. Slack sends command via WebSocket Events API
    2. Adapter receives event, acknowledges within 3 seconds
    3. Adapter calls internal HTTP endpoint (platform-agnostic business logic)
    4. Adapter formats response for Slack
    
    Args:
        payload: Slack command payload (from WebSocket event)
        request_id: Request ID for logging
        settings: Application settings
    
    Returns:
        Slack Block Kit response
    """
    log = logger.bind(
        command="add_member",
        user_id=payload["user_id"],
        request_id=request_id,
    )
    log.info("slack_command_received")
    
    args = payload["text"].split()
    if len(args) != 2:
        return {"text": "Usage: /add-member <group_id> <user_email>"}
    
    group_id, user_email = args
    
    # Call internal HTTP endpoint (platform-agnostic business logic)
    with httpx.Client() as client:
        response = client.post(
            f"{settings.server.BASE_URL}/api/v1/groups/members",
            json={"group_id": group_id, "user_email": user_email},
            headers={"X-Request-ID": request_id},
        )
    
    result = response.json()
    
    if result.get("success"):
        card = Card(
            title="Member Added",
            description=f"{user_email} added to {group_id}",
            color="success",
        )
    else:
        card = Card(
            title="Error",
            description=result.get("message", "Failed to add member"),
            color="error",
        )
    
    formatter = get_formatter("slack", settings)
    return formatter.format_card(card)

---

## Footnote: Async Platform Adapters (Future)

Async adapters are deferred until the async-first migration. When that happens,
use async HTTP clients and await the internal call.

```python
# Future async example (not current standard)
import httpx

async def handle_add_member_command(
    payload: dict,
    request_id: str,
    settings: "Settings",
) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.server.BASE_URL}/api/v1/groups/members",
            json={"group_id": "example", "user_email": "user@example.com"},
            headers={"X-Request-ID": request_id},
        )
    return response.json()
```
```

**Why httpx for Internal Calls**:
- Slack events received via WebSocket (Events API)
- Adapter acknowledges Slack within 3 seconds (WebSocket response)
- Business logic executed via internal HTTP call (platform-agnostic)
- Ensures single HTTP endpoint serves API, Slack, Teams, Discord

**Reference**: [Response Format Abstraction](../../decisions/tier-2-infrastructure/05-response-format-abstraction.md)

**Rules**:
- ✅ TYPE_CHECKING for Settings import
- ✅ Module-level logger only
- ✅ Request-scoped context binding
- ✅ Platform events received via WebSocket (Slack), HTTP (Teams), etc.
- ✅ Business logic executed via internal HTTP endpoint
- ✅ Use platform formatters for response conversion
- ✅ Platform-agnostic Card model
- ❌ No direct business logic calls
- ❌ No platform-specific response models in business logic

---

## 1.5 Schemas Pattern

**Decision**: Pydantic models for request/response validation.

**Complete Implementation**:
```python
# packages/groups/schemas.py
from pydantic import BaseModel, Field

class AddMemberRequest(BaseModel):
    """Add member to group request."""
    
    group_id: str = Field(..., description="Group identifier")
    user_email: str = Field(..., description="User email to add")

class AddMemberResponse(BaseModel):
    """Add member to group response."""
    
    success: bool = Field(..., description="Operation success status")
    message: str | None = Field(None, description="Error message if failed")
    data: dict | None = Field(None, description="Result data if successful")
```

**Rules**:
- ✅ All fields have type hints
- ✅ All fields have descriptions
- ✅ Use Field(...) for required fields
- ✅ Use Field(None) for optional fields
- ✅ Platform-agnostic models only
- ❌ No platform-specific fields (Block Kit, Adaptive Cards)

---

## 1.6 Package Registration

**Decision**: Feature packages register routers with FastAPI at application startup.

**Complete Implementation**:
```python
# app/main.py
from fastapi import FastAPI
from packages.groups import router as groups_router
from packages.incident import router as incident_router

app = FastAPI()

app.include_router(groups_router, prefix="/api/v1")
app.include_router(incident_router, prefix="/api/v1")
```

**Rules**:
- ✅ Import router from package __init__.py
- ✅ Register with app.include_router()
- ✅ Use /api/v1 prefix for versioning
- ❌ No manual route registration

---

## 1.7 Testing Pattern

**Decision**: Feature package tests located in `app/tests/unit/packages/<feature>/`.

**Reference**: [Testing Standards](../../decisions/tier-3-cross-cutting/02-testing-standards.md)

**Structure**:
```
app/tests/unit/packages/groups/
├── __init__.py
├── test_groups_routes.py
├── test_groups_service.py
└── test_groups_platforms.py
```

**Naming Convention**: Feature-prefix test files (`test_<feature>_<module>.py`) for clarity in isolation.

**Complete Test Example**:
```python
# app/tests/unit/packages/groups/test_groups_service.py
from unittest.mock import MagicMock
from infrastructure.operations import OperationResult
from packages.groups.service import add_member_to_group

def test_add_member_success():
    """Test successful member addition."""
    mock_aws = MagicMock()
    mock_aws.iam.add_user_to_group.return_value = OperationResult.success(
        data={"user": "test@example.com"}
    )
    
    result = add_member_to_group(
        group_id="test-group",
        user_email="test@example.com",
        aws_clients=mock_aws,
        request_id="test-123",
    )
    
    assert result.is_success
    assert result.data["group_id"] == "test-group"
```

**Route Test Example**:
```python
# app/tests/unit/packages/groups/test_groups_routes.py
from fastapi.testclient import TestClient
from infrastructure.services import get_aws_clients
from server.main import app

def test_add_member_route(monkeypatch):
    """Test add member route."""
    from unittest.mock import MagicMock
    from infrastructure.operations import OperationResult
    
    mock_aws = MagicMock()
    mock_aws.iam.add_user_to_group.return_value = OperationResult.success(
        data={"group_id": "test-group"}
    )
    
    app.dependency_overrides[get_aws_clients] = lambda: mock_aws
    
    try:
        response = TestClient(app).post(
            "/api/v1/groups/members",
            json={"group_id": "test-group", "user_email": "test@example.com"},
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
    finally:
        app.dependency_overrides.clear()
```

**Run Tests**: From `/workspace/app`: `pytest tests/unit/packages/groups/ -v`

**Rules**:
- ✅ Tests in `app/tests/unit/packages/<feature>/`
- ✅ Mock infrastructure dependencies (MagicMock)
- ✅ Test OperationResult success/failure paths
- ✅ Use app.dependency_overrides for route tests
- ✅ Always clear overrides in finally block
- ✅ Use monkeypatch for environment/attribute mocking
- ✅ Run from /workspace/app directory
- ❌ No tests inside feature packages (packages/groups/tests/)
- ❌ No tests importing from other packages

---

## 1.8 Migration Path (modules/ → packages/)

**Decision**: New features use packages/, existing features migrate incrementally.

**Current State**: `modules/groups/` (reference implementation, will migrate)

**Target State**: `packages/groups/` (follows tier-1, tier-2, tier-3 standards)

**Migration Checklist**:
- ✅ TYPE_CHECKING pattern for all imports
- ✅ Settings injection via SettingsDep
- ✅ Module-level logger only (no self.logger)
- ✅ Request-scoped context binding
- ✅ OperationResult for all business logic
- ✅ Platform adapters call HTTP endpoints
- ✅ All tests passing

**Rules**:
- ✅ New features start in packages/
- ✅ Migrate one feature at a time
- ❌ No new features in modules/

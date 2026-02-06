# Identity Resolution Across Platforms

All platforms (Slack, Teams, API) resolve to a normalized `User` model. Business logic never sees platform-specific identifiers (Slack user IDs, JWT tokens).

## User Model

```python
# infrastructure/identity/models.py
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any

class IdentitySource(str, Enum):
    """Where identity came from."""
    SLACK = "slack"
    API_JWT = "api_jwt"
    WEBHOOK = "webhook"
    SYSTEM = "system"

class User(BaseModel):
    """Platform-agnostic user identity."""
    user_id: str = Field(..., description="Canonical ID (email)")
    email: str
    display_name: str
    source: IdentitySource
    platform_id: str  # Slack user ID, JWT sub, etc. (platform-specific)
    permissions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)  # Platform-specific metadata

class SlackUser(User):
    """Extended with Slack metadata."""
    slack_user_id: str
    slack_team_id: str = ""
    slack_user_name: str = ""
```

## IdentityResolver

```python
# infrastructure/identity/resolver.py
import structlog

logger = structlog.get_logger()

class IdentityResolver:
    """Resolve user identities across platforms."""
    
    def __init__(self, slack_client=None):
        self._slack_client = slack_client
    
    def resolve_from_slack(self, slack_user_id: str) -> SlackUser:
        """Resolve Slack user ID to canonical User."""
        log = logger.bind(slack_user_id=slack_user_id)
        
        if not self._slack_client:
            raise ValueError("Slack client not configured")
        
        user = self._slack_client.users_info(user=slack_user_id)["user"]
        email = user.get("profile", {}).get("email", "")
        
        return SlackUser(
            user_id=email,
            email=email,
            display_name=user.get("profile", {}).get("display_name", ""),
            source=IdentitySource.SLACK,
            platform_id=slack_user_id,
            slack_user_id=slack_user_id,
        )
    
    def resolve_from_jwt(self, jwt_payload: dict) -> User:
        """Resolve JWT token to canonical User."""
        return User(
            user_id=jwt_payload.get("sub", "unknown"),
            email=jwt_payload.get("email", "unknown"),
            display_name=jwt_payload.get("name", ""),
            source=IdentitySource.API_JWT,
            platform_id=jwt_payload.get("sub", "unknown"),
            permissions=jwt_payload.get("permissions", []),
        )
    
    def resolve_system_identity(self) -> User:
        """Create system identity for internal operations."""
        return User(
            user_id="system",
            email="system@sre-bot.local",
            display_name="SRE Bot System",
            source=IdentitySource.SYSTEM,
            platform_id="system",
            permissions=["system"],
        )
```

## Provider & Dependency Injection

```python
# infrastructure/services/providers.py
from functools import lru_cache
from infrastructure.identity.resolver import IdentityResolver
from infrastructure.identity.service import IdentityService

@lru_cache(maxsize=1)
def get_identity_resolver() -> IdentityResolver:
    """Get cached IdentityResolver with injected dependencies."""
    slack_client = get_slack_client()  # Injected singleton
    return IdentityResolver(slack_client_manager=slack_client)

@lru_cache(maxsize=1)
def get_identity_service() -> IdentityService:
    """Get cached IdentityService."""
    resolver = get_identity_resolver()
    return IdentityService(resolver=resolver)

# Type alias for FastAPI routes
from typing import Annotated
from fastapi import Depends

IdentityServiceDep = Annotated[IdentityService, Depends(get_identity_service)]
```

## Usage: Slack Platform Provider

```python
# Platform provider resolves Slack IDs to canonical User model
# Business logic never sees slack_user_id

class SlackCommandProvider:
    def handle_command(
        self, payload: dict, identity: IdentityServiceDep
    ) -> dict:
        # ✅ Resolve Slack user ID → canonical User
        user = identity.resolve_from_slack(payload["user_id"])
        
        # ✅ Pass User (not slack_user_id) to business logic
        result = business_logic.execute(user, payload["text"])
        
        # ✅ Format response for Slack
        return slack_formatter.format(result)
```

## Usage: API Routes

```python
# API routes resolve JWT → canonical User
# Business logic receives same User model regardless of source

@router.post("/groups/add")
def add_member(
    request: AddMemberRequest,
    identity: IdentityServiceDep,
    jwt_token: str = Depends(get_jwt_token)
) -> dict:
    # ✅ Resolve JWT token → canonical User
    user = identity.resolve_from_jwt(decode_jwt(jwt_token))
    
    # ✅ Same business logic signature as Slack provider
    # All identity sources use same User model
    result = add_member_to_group(request, user)
    return result
```

## Rules

**Provider/DI Pattern** (CRITICAL - frequently violated):
- ✅ Provider handles all dependency construction
- ✅ Use `@lru_cache(maxsize=1)` for singleton caching
- ✅ Provider injects fully-constructed resolver into service
- ✅ Routes/jobs get service via type alias (Depends injection)
- ❌ Never instantiate IdentityService directly in app code
- ❌ Never construct dependencies inside services (wire in provider)
- ❌ Never call `get_identity_service()` multiple times per request (use type alias)

**Identity Handling** (CRITICAL):
- ✅ Business logic receives User model, never platform IDs
- ✅ Audit logs use `user_id` and `email` from User
- ✅ Platform metadata stored in `User.metadata` dict
- ✅ All identity sources resolve to User via IdentityService
- ✅ Bind request context (user_id, request_id) in logging
- ❌ Never pass raw Slack user IDs to business logic
- ❌ Never pass JWT tokens to business logic
- ❌ Never implement ad-hoc identity resolution outside IdentityService

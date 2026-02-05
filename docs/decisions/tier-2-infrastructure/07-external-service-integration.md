# External Service Integration

## Naming Conventions

Consistent naming across all external services:

| Service | Provider | Type Alias | Facade |
|---------|----------|-----------|--------|
| AWS | `get_aws_clients()` | `AWSClientsDep` | `AWSClients` |
| Google Workspace | `get_google_workspace_clients()` | `GoogleWorkspaceClientsDep` | `GoogleWorkspaceClients` |
| Slack | `get_slack_client()` | `SlackClientDep` | `SlackClient` |

- ✅ Providers: `get_{service}_client(s)()`
- ✅ Type aliases: `{Service}ClientDep(s)`
- ✅ Facades: `{Service}Client(s)`

---

## Settings Injection Pattern

**CRITICAL**: Client facades receive settings as constructor parameters. Never fetch settings inside clients.

```python
# infrastructure/clients/google_workspace/__init__.py
import structlog

logger = structlog.get_logger()

class GoogleWorkspaceClients:
    """Google Workspace API facade."""
    
    def __init__(self, gws_settings: "GoogleWorkspaceSettings") -> None:
        """Initialize with injected settings."""
        log = logger.bind(service="google_workspace")
        
        # ✅ Extract credentials from validated settings
        self._auth = GoogleWorkspaceAuthProvider(
            service_account_email=gws_settings.service_account_email,
            credentials_json=gws_settings.credentials_json,
        )
        
        self.groups = GroupsClient(auth=self._auth)
        log.info("clients_initialized")
```

**Provider with dependency injection**:

```python
# infrastructure/services/providers.py
from functools import lru_cache
from fastapi import Depends
from typing import Annotated

from infrastructure.configuration import Settings
from infrastructure.clients.google_workspace import GoogleWorkspaceClients

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get validated settings singleton."""
    return Settings()  # Pydantic validates from env vars

SettingsDep = Annotated[Settings, Depends(get_settings)]

@lru_cache(maxsize=1)
def get_google_workspace_clients(settings: SettingsDep) -> GoogleWorkspaceClients:
    """Get GWS clients singleton with injected settings."""
    # ✅ Extract service-specific settings, inject into facade
    return GoogleWorkspaceClients(gws_settings=settings.integrations.google_workspace)

GoogleWorkspaceClientsDep = Annotated[GoogleWorkspaceClients, Depends(get_google_workspace_clients)]
```

**Usage in routes**:

```python
# api/v1/groups/routes.py
from infrastructure.services import GoogleWorkspaceClientsDep
import structlog

logger = structlog.get_logger()

@router.get("/groups/{group_id}")
def get_group(group_id: str, gws_clients: GoogleWorkspaceClientsDep):
    """Get group from Google Workspace.
    
    Clients injected by FastAPI DI.
    """
    log = logger.bind(group_id=group_id)
    
    # ✅ Use injected client facade
    result = gws_clients.groups.get_group(group_id, request_id)
    
    if result.is_success:
        return result.data
    
    log.error("fetch_failed", error=result.message)
    return {"error": result.message}
```

Rules (CRITICAL - frequently violated):
- ✅ All configuration passed via constructor parameter
- ✅ Settings must be validated Pydantic BaseSettings instances
- ✅ Providers use `@lru_cache(maxsize=1)` for singleton
- ✅ Providers extract service-specific settings from Settings
- ❌ Never call `get_settings()` or instantiate Settings in client code
- ❌ Never fetch settings inside client methods

---

## OperationResult from All Methods

All client methods return `OperationResult`. Library exceptions are caught, categorized, and converted to structured results.

```python
# infrastructure/clients/google_workspace/groups.py
from infrastructure.operations import OperationResult, OperationStatus
from googleapiclient.errors import HttpError
import structlog

logger = structlog.get_logger()

class GroupsClient:
    """Groups API client - all methods return OperationResult."""
    
    def get_group(self, group_id: str, request_id: str) -> OperationResult:
        """Get group details."""
        log = logger.bind(group_id=group_id, request_id=request_id)
        
        try:
            service = self._auth.get_directory_service()
            response = service.groups().get(groupKey=group_id).execute()
            
            log.info("group_fetched")
            return OperationResult.success(data=response)
        
        except HttpError as e:
            status = e.resp.status
            
            if status == 404:
                log.info("not_found")
                return OperationResult.error(
                    status=OperationStatus.NOT_FOUND,
                    message=f"Group {group_id} not found",
                    error_code="GROUP_NOT_FOUND",
                )
            
            elif status == 401 or status == 403:
                log.error("auth_failed")
                return OperationResult.error(
                    status=OperationStatus.UNAUTHORIZED,
                    message=f"Auth failed: {e.reason}",
                    error_code="AUTH_FAILURE",
                )
            
            elif status == 429:
                log.warning("rate_limited")
                return OperationResult.error(
                    status=OperationStatus.TRANSIENT_ERROR,
                    message="Rate limited",
                    error_code="RATE_LIMIT",
                    retry_after=60,
                )
            
            elif status >= 500:
                log.warning("server_error", status=status)
                return OperationResult.error(
                    status=OperationStatus.TRANSIENT_ERROR,
                    message=f"Server error: {e.reason}",
                    error_code="SERVER_ERROR",
                    retry_after=30,
                )
            
            else:
                log.error("http_error", status=status)
                return OperationResult.error(
                    status=OperationStatus.PERMANENT_ERROR,
                    message=f"HTTP {status}: {e.reason}",
                    error_code="HTTP_ERROR",
                )
        
        except Exception as e:
            log.error("unexpected_error", error=str(e))
            return OperationResult.error(
                status=OperationStatus.PERMANENT_ERROR,
                message=str(e),
                error_code="UNKNOWN_ERROR",
            )
```

**Application code handling results** (see 03-operation-result-pattern.md):

```python
def fetch_group_details(group_id: str, request_id: str) -> dict:
    """Fetch group with intelligent error handling."""
    log = logger.bind(group_id=group_id, request_id=request_id)
    
    gws_clients = get_google_workspace_clients()
    result = gws_clients.groups.get_group(group_id, request_id)
    
    # ✅ No try/except needed - all errors returned as OperationResult
    if result.is_success:
        log.info("group_fetched")
        return result.data
    
    if result.status == OperationStatus.TRANSIENT_ERROR:
        log.warning("transient_error", retry_after=result.retry_after)
        return {}
    
    log.error("permanent_error", error_code=result.error_code)
    return {}
```

Rules:
- ✅ All client methods return `OperationResult`
- ✅ Library exceptions caught and categorized in client code
- ✅ Transient errors include `retry_after` (seconds)
- ✅ Error codes are categorical (GROUP_NOT_FOUND, RATE_LIMIT, etc.)
- ✅ Caller inspects `result.is_success` and `result.status` to handle
- ✅ Ref: 03-operation-result-pattern.md for detailed handling
- ❌ Never raise exceptions from client methods
- ❌ Never return raw library exceptions
- ❌ Never require try/except in application code
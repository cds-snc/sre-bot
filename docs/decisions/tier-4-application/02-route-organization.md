# Route Organization

## Routes in Feature Packages

**Decision**: Routes live in feature packages, NOT centralized `api/`.

**Implementation**:
```python
# modules/groups/api/routes.py
from fastapi import APIRouter
from infrastructure.services import CommandServiceDep, SettingsDep

router = APIRouter(
    prefix="/api/v1/groups",  # ✅ Feature owns its prefix
    tags=["groups"],
)

@router.post("/add")
def add_member(
    request: AddMemberRequest,
    command_service: CommandServiceDep,
    settings: SettingsDep,
):
    """Add member to group."""
    # Implementation...
```

**Main Application Registration**:
```python
# server/main.py
from fastapi import FastAPI
# Current: import from modules/ (legacy directory name)
from modules.groups import router as groups_router
from modules.incident import router as incident_router
# Future: import from packages/ (correct Python term)
# from packages.groups import router as groups_router

app = FastAPI(title="SRE Bot API")

# ✅ Register feature routers
app.include_router(groups_router)
app.include_router(incident_router)

# api/ package only for shared/cross-cutting concerns
from api.routes.health import router as health_router
from api.routes.auth import router as auth_router
app.include_router(health_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
```

**Rules**:
- ✅ Routes in `modules/{feature}/api/routes.py` (current) or `packages/{feature}/api/routes.py` (future)
- ✅ Feature package exports `router` from `__init__.py`
- ✅ Main app registers via `app.include_router()`
- ✅ Centralized `api/` only for shared routes (health, auth)
- ❌ Never put feature routes in centralized `api/v1/`

---

## What Lives Where

| Component | Location | Responsibility |
|-----------|----------|----------------|
| **Feature Routes** | `modules/{feature}/api/routes.py` (current)<br>`packages/{feature}/api/routes.py` (future) | Feature-specific HTTP endpoints |
| **Request/Response Models** | `{feature}/api/schemas.py` | Pydantic models for HTTP |
| **Command Handlers** | `{feature}/commands/handlers.py` | Business logic |
| **Domain Logic** | `{feature}/core/` | Provider-agnostic operations |
| **Health Checks** | `api/routes/health.py` | System health endpoints |
| **Authentication** | `api/routes/auth.py` | Auth/OIDC endpoints |
| **Middleware** | `api/middleware/` | Request/response middleware |

**Rules**:
- ✅ Feature packages own complete vertical slices
- ✅ Centralized `api/` for cross-cutting concerns only
- ❌ Never mix feature logic in centralized `api/`

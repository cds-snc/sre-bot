# Route Organization

## Routes in Feature Packages

**Decision**: Routes live in feature packages under `packages/{feature}/transport/routes.py`. The main application never imports feature routes — each feature registers itself via hookimpl.

**Router declaration** — feature owns its path prefix:

```python
# packages/feature/transport/routes.py
from fastapi import APIRouter

router = APIRouter(prefix="/feature", tags=["Feature"])
```

**Registration via hookimpl** — `/api/v1` prefix applied once at include time:

```python
# packages/feature/__init__.py
from infrastructure.services import hookimpl
from packages.feature.transport.routes import router as feature_router


@hookimpl
def register_routes(app) -> None:
    app.include_router(feature_router, prefix="/api/v1")
```

**Rules**:
- ✅ Feature router declares its own sub-prefix (e.g. `/feature`)
- ✅ `/api/v1` versioning prefix applied once in `register_routes` hookimpl
- ✅ `api/` is for cross-cutting concerns only: health checks, auth endpoints
- ❌ No feature routes in centralized `api/`
- ❌ No `app.include_router()` calls outside hookimpl implementations
- ❌ Features do not export bare routers for external import

---

## Dependency Injection in Routes

**Decision**: Route handlers consume services and settings via `Annotated[Protocol, Depends(factory)]`. Factory functions come from `providers.py`.

Each route file declares a local structural Protocol for each dependency, exposing only the surface the handler needs. This decouples the handler from the concrete implementation and makes test substitution straightforward — patch `providers.get_*` at module scope.

```python
# packages/feature/transport/routes.py
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends

from infrastructure.operations import OperationResult
from packages.feature.providers import get_feature_service, get_feature_settings
from packages.feature.schemas import FeatureRequest, FeatureResponse

router = APIRouter(prefix="/feature", tags=["Feature"])


class _FeatureSettingsPort(Protocol):
    enabled: bool


class _FeatureServicePort(Protocol):
    def do_action(self, param: str) -> OperationResult: ...


@router.post("/actions", response_model=FeatureResponse)
def action_endpoint(
    request: FeatureRequest,
    service: Annotated[_FeatureServicePort, Depends(get_feature_service)],
    settings: Annotated[_FeatureSettingsPort, Depends(get_feature_settings)],
) -> FeatureResponse:
    ...
```

**Rules**:
- ✅ `Annotated[Protocol, Depends(factory)]` for all service and settings dependencies
- ✅ Factory functions imported from the feature's `providers.py`
- ✅ Local Protocol declares only the surface the route actually consumes
- ❌ No direct service instantiation in routes
- ❌ No `SettingsDep` or infrastructure client deps imported directly in route handlers

---

## What Lives Where

| Component | Location | Responsibility |
|---|---|---|
| HTTP routes | `packages/{feature}/transport/routes.py` | FastAPI route handlers |
| Chat command handlers | `packages/{feature}/transport/slack.py` | Slack/Teams command dispatch |
| Request/response schemas | `packages/{feature}/schemas.py` | Pydantic HTTP models |
| Business logic / orchestration | `packages/{feature}/service.py` or `coordinator.py` | Platform-agnostic operations |
| Domain models | `packages/{feature}/domain.py` | Internal frozen dataclasses |
| DI assembly | `packages/{feature}/providers.py` | `@lru_cache` factory functions |
| Health checks | `api/routes/health.py` | System health endpoints |
| Authentication | `api/routes/auth.py` | Auth/OIDC endpoints |
| Middleware | `api/middleware/` | Request/response middleware |

**Rules**:
- ✅ Feature packages own complete vertical slices
- ✅ Centralized `api/` for cross-cutting concerns only
- ❌ Never mix feature logic in centralized `api/`

# Features Organization

## Feature Package Structure

**Decision**: Feature packages follow vertical slice architecture. Each package is self-contained and registers itself with the application via hookimpl — the main application has no knowledge of individual features.

**Full layout** (for features with adapters, orchestration, or external config):
```
packages/feature/
├── __init__.py          — hookimpl registrations and startup wiring
├── schemas.py           — Pydantic HTTP request/response models
├── domain.py            — internal frozen dataclass models
├── coordinator.py       — orchestration layer (sequence of steps across modules)
├── policies.py          — business rules and planning logic
├── providers.py         — @lru_cache DI factory functions
├── store.py             — persistence layer
├── events.py            — domain event name constants
├── presenters.py        — shared response shape mapping (optional)
├── adapters/            — Protocol-defined external integrations
│   ├── __init__.py      — adapter Protocol contract
│   └── <platform>.py   — platform-specific implementation
├── config/              — feature settings and config loaders
│   ├── __init__.py
│   └── settings.py
└── interactions/        — inbound channel handlers (HTTP, Slack, Teams)
    ├── ingress.py       — shared admission logic (optional)
    ├── http.py          — FastAPI route handlers
    └── slack.py         — Slack interaction handlers
```

**Lean layout** (for simpler features without adapters or complex orchestration):
```
packages/feature/
├── __init__.py          — hookimpl registrations
├── schemas.py           — Pydantic models
├── domain.py            — internal dataclasses
├── service.py           — business logic
├── providers.py         — @lru_cache factory functions
└── interactions/
    └── http.py          — FastAPI route handlers
```

**Rules**:
- ✅ Each package is a complete vertical slice — no cross-package feature imports
- ✅ HTTP schemas (Pydantic) in `schemas.py`; internal models (frozen dataclasses) in `domain.py`
- ✅ Platform adapters conform to a Protocol defined in `adapters/__init__.py`
- ✅ `providers.py` is the only place that assembles the object graph
- ✅ Package registers itself via hookimpl in `__init__.py` — no bare router export
- ✅ Infrastructure clients come from `infrastructure.services` only
- ❌ No cross-package dependencies between feature packages
- ❌ No business logic in route handlers

---

## Routes Pattern (HTTP Interface)

**Decision**: Route handlers validate input, call the service, and map the result to an HTTP response. No business logic.

Routes consume services and settings through Protocol-typed `Annotated[..., Depends(factory)]` parameters. Each route file declares a local structural Protocol for each dependency — this decouples the handler from the concrete implementation and makes test substitution straightforward. Factory functions come from `providers.py`.

```python
# packages/feature/interactions/http.py
from typing import Annotated, Protocol

import structlog
from fastapi import APIRouter, Depends, HTTPException

from infrastructure.operations import OperationResult, OperationStatus
from packages.feature.providers import get_feature_service, get_feature_settings
from packages.feature.schemas import FeatureRequest, FeatureResponse

logger = structlog.get_logger()
router = APIRouter(prefix="/feature", tags=["Feature"])


class _FeatureSettingsPort(Protocol):
    """Structural contract for settings consumed by route handlers."""

    enabled: bool


class _FeatureServicePort(Protocol):
    """Structural contract for the service consumed by route handlers."""

    def do_action(self, param: str, request_id: str = "") -> OperationResult: ...


@router.post("/actions", response_model=FeatureResponse)
def action_endpoint(
    request: FeatureRequest,
    service: Annotated[_FeatureServicePort, Depends(get_feature_service)],
    settings: Annotated[_FeatureSettingsPort, Depends(get_feature_settings)],
) -> FeatureResponse:
    """Perform a feature action."""
    log = logger.bind(param=request.param)
    log.info("action_request")

    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Feature is not enabled")

    result = service.do_action(param=request.param)

    if result.is_success:
        return FeatureResponse(success=True, data=result.data)

    status_code, detail = _to_public_error(result)
    log.warning("action_failed", error=result.message, error_code=result.error_code)
    raise HTTPException(status_code=status_code, detail=detail)


def _to_public_error(result: OperationResult) -> tuple[int, str]:
    """Map OperationResult errors to safe public HTTP responses."""
    if result.status == OperationStatus.NOT_FOUND:
        return 404, result.message or "Resource not found"
    if result.status == OperationStatus.UNAUTHORIZED:
        return 403, "Not authorized"
    if result.status == OperationStatus.PERMANENT_ERROR:
        return 400, result.message or "Request could not be completed"
    return 500, "An internal error occurred"
```

**Rules**:
- ✅ `Annotated[Protocol, Depends(factory)]` for all service and settings dependencies
- ✅ Factory functions imported from `providers.py`
- ✅ Local Protocol declares only the surface the route actually uses
- ✅ Error mapping extracted to a private `_to_public_error` helper — never expose raw internal messages
- ✅ Module-level logger; request-scoped context via `logger.bind()`
- ✅ Route returns Pydantic response model — no raw dict returns
- ❌ No business logic in route handlers
- ❌ No direct service instantiation in routes
- ❌ No platform-specific logic (Slack, Teams) in route handlers

---

## Providers Pattern (DI Assembly)

**Decision**: `providers.py` assembles the object graph using `@lru_cache(maxsize=1)` singleton factories. It is the only file that calls `infrastructure.services` to obtain clients.

Provider functions are the patch target in tests. Patching `providers.get_feature_service` is sufficient to substitute the entire service tree without touching infrastructure singletons.

```python
# packages/feature/providers.py
from functools import lru_cache

from infrastructure.services import get_directory_provider, get_storage_service
from packages.feature.config.settings import FeatureSettings
from packages.feature.service import FeatureService


@lru_cache(maxsize=1)
def get_feature_settings() -> FeatureSettings:
    """Return the singleton feature settings instance."""
    return FeatureSettings()


@lru_cache(maxsize=1)
def get_feature_service() -> FeatureService:
    """Return the singleton feature service.

    Infrastructure clients are obtained from infrastructure.services.
    To substitute dependencies in tests, patch this function at module scope.
    """
    return FeatureService(
        directory=get_directory_provider(),
        storage=get_storage_service(),
        settings=get_feature_settings(),
    )
```

**Rules**:
- ✅ One `@lru_cache(maxsize=1)` per singleton
- ✅ All infrastructure clients from `infrastructure.services`
- ✅ Provider functions are the sole patch target in tests
- ❌ Do not instantiate infrastructure clients directly
- ❌ Do not call `get_settings()` or `get_*_clients()` inside service constructors

---

## Service / Coordinator Pattern (Business Logic)

**Decision**: Business logic is platform-agnostic. Services hold injected dependencies as constructor arguments. Features with multiple distinct logic stages use a `coordinator.py` to sequence those stages; simpler features use a single `service.py`.

Internal inputs and outputs use frozen dataclasses, not Pydantic models. Pydantic is used only at the HTTP boundary in `schemas.py`.

```python
# packages/feature/domain.py
from dataclasses import dataclass


@dataclass(frozen=True)
class ActionResult:
    item_id: str
    status: str
```

```python
# packages/feature/service.py
import structlog

from infrastructure.operations import OperationResult
from packages.feature.domain import ActionResult

logger = structlog.get_logger()


class FeatureService:
    def __init__(self, directory, storage, settings) -> None:
        self._directory = directory
        self._storage = storage
        self._settings = settings

    def do_action(
        self, param: str, request_id: str = ""
    ) -> OperationResult[ActionResult]:
        log = logger.bind(param=param, request_id=request_id)
        log.info("action_started")

        lookup = self._directory.get_item(param)
        if not lookup.is_success or lookup.data is None:
            return lookup

        log.info("action_completed")
        return OperationResult.success(
            data=ActionResult(item_id=lookup.data.id, status="complete")
        )
```

**Rules**:
- ✅ All dependencies injected via `__init__` — never call `get_*()` inside service methods
- ✅ Internal result shapes use `@dataclass(frozen=True)` in `domain.py`
- ✅ Return `OperationResult[T]` — never raise exceptions across service boundaries
- ✅ Check `result.is_success` (property, not method)
- ✅ Module-level logger; request-scoped context via `logger.bind()`
- ❌ No Pydantic models as internal service inputs or outputs
- ❌ No platform-specific logic

---

## Platform Adapters (Protocol Contract)

**Decision**: Platform adapters are defined by a `Protocol` in `adapters/__init__.py`. Concrete implementations live in `adapters/<platform>.py`. Providers inject the correct implementation — services and coordinators never instantiate adapters directly.

All adapter methods are idempotent and return `OperationResult`. Adapters execute actions; they never implement business rules.

```python
# packages/feature/adapters/__init__.py
from typing import Protocol

from infrastructure.operations import OperationResult


class FeatureAdapter(Protocol):
    """Contract for all external platform integrations.

    All methods are idempotent and return OperationResult.
    Adapters must not implement business logic.
    """

    def ensure_item(self, item_id: str) -> OperationResult: ...
    def remove_item(self, item_id: str) -> OperationResult: ...
```

**Rules**:
- ✅ Protocol defined in `adapters/__init__.py`
- ✅ Concrete implementations injected by `providers.py`
- ✅ All methods idempotent and returning `OperationResult`
- ❌ No business logic in adapters — they execute, not decide
- ❌ Do not instantiate adapters inside service or coordinator methods

---

## Schemas Pattern (HTTP Boundary)

**Decision**: Pydantic models are used only at the HTTP boundary in `schemas.py` — request validation and response serialisation. Internal business logic uses frozen dataclasses in `domain.py`.

```python
# packages/feature/schemas.py
from pydantic import BaseModel, Field


class FeatureRequest(BaseModel):
    """Feature action request."""

    param: str = Field(..., description="Target resource identifier.")
    dry_run: bool = Field(default=False, description="If true, plan without executing.")


class FeatureResponse(BaseModel):
    """Feature action response."""

    success: bool = Field(..., description="Whether the operation succeeded.")
    data: dict | None = Field(None, description="Result payload on success.")
    message: str | None = Field(None, description="Error message on failure.")
```

**Rules**:
- ✅ All fields have type hints and descriptions
- ✅ `Field(...)` for required fields; `Field(default=...)` for optional
- ✅ Platform-agnostic models only
- ❌ No Pydantic models outside `schemas.py` — use frozen dataclasses for internal shapes
- ❌ No platform-specific fields (Block Kit, Adaptive Cards)

---

## Package Registration (hookimpl)

**Decision**: Feature packages register themselves via hookimpl in `__init__.py`. The main application invokes hookspecs; each package responds. No feature router is imported by `main.py`.

```python
# packages/feature/__init__.py
from infrastructure.services import hookimpl
from packages.feature.providers import get_feature_settings, get_feature_service
from packages.feature.interactions.http import router as feature_router
from packages.feature.interactions import slack


@hookimpl
def startup_warmup(logger) -> None:
    """Log settings and eagerly initialize providers at startup."""
    settings = get_feature_settings()
    logger.info("feature_settings_loaded", enabled=settings.enabled)
    if settings.enabled:
        get_feature_service()  # warm the singleton on startup


@hookimpl
def register_routes(app) -> None:
    """Register HTTP routes under /api/v1."""
    app.include_router(feature_router, prefix="/api/v1")


@hookimpl
def register_slack_commands(provider) -> None:
    """Register Slack commands for this feature."""
    slack.register_commands(provider)
```

**Rules**:
- ✅ `register_routes` applies the `/api/v1` prefix at include time
- ✅ `startup_warmup` warms provider singletons so the first request is not delayed
- ✅ `__init__.py` does not export a bare `router`
- ❌ No `app.include_router()` calls outside hookimpl implementations
- ❌ Do not import feature `__init__.py` from other packages

---

## Testing Pattern

**Decision**: Feature package tests are in `app/tests/unit/packages/<feature>/`.

**Structure**:
```
app/tests/unit/packages/feature/
├── __init__.py
├── test_feature_routes.py
├── test_feature_service.py
└── test_feature_adapters.py
```

**Naming**: `test_<feature>_<module>.py`.

**Service test** — inject mocks directly as constructor arguments:

```python
# tests/unit/packages/feature/test_feature_service.py
from unittest.mock import MagicMock

from infrastructure.operations import OperationResult
from packages.feature.service import FeatureService


def test_do_action_success():
    mock_directory = MagicMock()
    mock_directory.get_item.return_value = OperationResult.success(
        data=MagicMock(id="item-1")
    )

    service = FeatureService(
        directory=mock_directory,
        storage=MagicMock(),
        settings=MagicMock(enabled=True),
    )
    result = service.do_action(param="item-1", request_id="test-123")

    assert result.is_success
    assert result.data.item_id == "item-1"
```

**Route test** — patch provider functions, use `TestClient`:

```python
# tests/unit/packages/feature/test_feature_routes.py
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from infrastructure.operations import OperationResult
from server.main import app

client = TestClient(app)


def test_action_endpoint_success():
    mock_service = MagicMock()
    mock_service.do_action.return_value = OperationResult.success(
        data=MagicMock(item_id="item-1", status="complete")
    )
    mock_settings = MagicMock(enabled=True)

    with (
        patch("packages.feature.providers.get_feature_service", return_value=mock_service),
        patch("packages.feature.providers.get_feature_settings", return_value=mock_settings),
    ):
        response = client.post("/api/v1/feature/actions", json={"param": "item-1"})

    assert response.status_code == 200
    assert response.json()["success"] is True
```

**Rules**:
- ✅ Service tests inject mocks directly as constructor arguments
- ✅ Route tests patch `providers.get_*` functions at module scope
- ✅ Use `OperationResult.success()` / `OperationResult.error()` for mock return values
- ❌ Do not patch `infrastructure.services` directly in route tests — patch providers instead
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

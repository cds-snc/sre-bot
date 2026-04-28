---
adr_id: ADR-0032
title: "Features Organization"
status: Accepted
decision_type: Feature
tier: Tier-4
date_created: 2024-01-01
last_updated: 2026-04-27
last_reviewed: 2026-04-27
next_review_due: 2026-10-27
owners:
  - Platform Engineering
supersedes: []
superseded_by: []
related_records:
  - ADR-0033
  - ADR-0040
  - ADR-0030
related_packages:
  - app/packages/access
  - app/packages/geolocate
review_state: current
---
# Features Organization

## Context

- **Problem statement:** Feature packages need a consistent, unambiguous internal layout. The original ADR prescribed `coordinator.py` for complex orchestration modules, but that term is not found in authoritative Python or DDD literature, has caused naming ambiguity in practice, and does not account for a third complexity tier needed by features like `access/sync`.
- **Business/operational drivers:** Developer onboarding speed; consistent mental model for where to find and place business logic across all feature packages.
- **Constraints:** Must align with DDD application-service vocabulary, PEP 8 module naming, FastAPI dependency-injection patterns, and existing codebase shape (`access/request` uses `service.py`, `access/sync` uses `application.py`).
- **Non-goals:** This record does not prescribe infrastructure service naming under `app/infrastructure`.

---

## Decision

### Chosen approach

Feature packages follow vertical-slice architecture with three layout tiers determined by orchestration complexity. All layouts use the same hookimpl registration, Pydantic-at-boundary, frozen-dataclass-internal, and `providers.py`-assembly rules. The distinguishing factor is the module that owns orchestration:

| Tier | Orchestration module | Class name pattern | When to use |
|------|---------------------|--------------------|-------------|
| Lean | `service.py` | `<Feature>Service` | Single-domain logic, one or two infrastructure calls, no adapters |
| Standard | `service.py` | `<Feature>Service` | Policies + store + events, no multi-platform adapter dispatch |
| Rich Workflow | `application.py` | `<Feature>ApplicationService` | Multi-adapter dispatch, cross-cutting event lifecycle, explicit policy planning |

The term `coordinator.py` is retired. It was a local invention without grounding in DDD or Python ecosystem vocabulary.

### Why this approach

"Architecture Patterns with Python" (Percival & Gregory, O'Reilly 2020, Chapter 4) names this layer the **service layer**, also called **orchestration layer** or **use-case layer**. The same source distinguishes **application service** (orchestrates use cases: fetch → validate → call domain → persist → emit events) from **domain service** (stateless business logic with no natural home in an entity). The term "coordinator" appears in neither source.

`service.py` maps to the standard "application service" pattern and is adequate for the vast majority of features. `application.py` is reserved for the rich-workflow tier where the orchestration surface is large enough that naming it simply "service" would understate its cross-cutting scope — the existing `access/sync` package is the canonical example.

### Principles established

- Orchestration module naming follows DDD application-service vocabulary, not project-local invention.
- Complexity tier determines module name; within each tier the naming is uniform.
- `coordinator.py` must not be introduced in new packages.

---

## Feature Package Layouts

### Lean layout — `service.py`

For features with single-domain logic, minimal infrastructure surface, and no platform adapters.

```
packages/feature/
├── __init__.py          — hookimpl registrations
├── schemas.py           — Pydantic HTTP request/response models
├── domain.py            — internal frozen dataclass models
├── service.py           — application service (orchestration + business rules)
├── providers.py         — @lru_cache DI factory functions
└── interactions/
    └── http.py          — FastAPI route handlers
```

Reference implementation: `app/packages/geolocate`.

### Standard layout — `service.py` with policies and store

For features that separate business rules into `policies.py`, persist state, and emit domain events, but dispatch to a single backend.

```
packages/feature/
├── __init__.py          — hookimpl registrations and startup wiring
├── schemas.py           — Pydantic HTTP request/response models
├── domain.py            — internal frozen dataclass models
├── service.py           — application service (orchestration)
├── policies.py          — pure business rule functions
├── store.py             — persistence layer
├── events.py            — domain event name constants
├── providers.py         — @lru_cache DI factory functions
├── presenters.py        — response shape mapping (optional)
├── config/              — feature settings
│   ├── __init__.py
│   └── settings.py
└── interactions/        — inbound channel handlers
    ├── ingress.py        — shared admission logic (optional)
    ├── http.py           — FastAPI route handlers
    └── slack.py          — Slack interaction handlers
```

Reference implementation: `app/packages/access/request`.

### Rich Workflow layout — `application.py`

For features that dispatch across multiple platform adapters, manage cross-cutting event lifecycles, or implement explicit policy-planning phases.

```
packages/feature/
├── __init__.py          — hookimpl registrations and startup wiring
├── schemas.py           — Pydantic HTTP request/response models
├── domain.py            — internal frozen dataclass models
├── application.py       — application service (multi-adapter orchestration + event lifecycle)
├── policies.py          — business rules and planning context
├── store.py             — persistence layer
├── events.py            — domain event name constants
├── providers.py         — @lru_cache DI factory functions
├── presenters.py        — response shape mapping (optional)
├── adapters/            — Protocol-defined external integrations
│   ├── __init__.py      — adapter Protocol contract
│   └── <platform>.py   — platform-specific implementation
├── config/              — feature settings and config loaders
│   ├── __init__.py
│   └── settings.py
└── interactions/        — inbound channel handlers (HTTP, Slack, Teams)
    ├── ingress.py        — shared admission logic (optional)
    ├── http.py           — FastAPI route handlers
    └── slack.py          — Slack interaction handlers
```

Reference implementation: `app/packages/access/sync`.

**Rules (all layouts)**:
- ✅ Each package is a complete vertical slice — no cross-package feature imports
- ✅ HTTP schemas (Pydantic) in `schemas.py`; internal models (frozen dataclasses) in `domain.py`
- ✅ Platform adapters conform to a Protocol defined in `adapters/__init__.py`
- ✅ `providers.py` is the only place that assembles the object graph
- ✅ Package registers itself via hookimpl in `__init__.py` — no bare router export
- ✅ Infrastructure clients come from `infrastructure.services` only
- ✅ Orchestration module named `service.py` (lean/standard) or `application.py` (rich workflow)
- ❌ No `coordinator.py` — the term is retired; use `service.py` or `application.py`
- ❌ No cross-package dependencies between feature packages
- ❌ No business logic in route handlers

---

## Alternatives Considered

### 1. Keep `coordinator.py` for complex features
- **Pros:** No renaming of existing `access/sync` class references; familiar to current team.
- **Cons:** Not grounded in DDD or Python ecosystem vocabulary; "coordinator" is an informal term that means different things across frameworks (e.g., Kubernetes coordinator has a different meaning); causes onboarding confusion when new contributors look for standard patterns.
- **Why not chosen:** Authoritative sources use "application service" / "service layer" consistently. Retiring the term aligns the codebase with industry vocabulary.

### 2. Use `service.py` for all tiers (no `application.py`)
- **Pros:** Maximum naming uniformity; simpler decision rule.
- **Cons:** `access/sync` already uses `application.py`; the rich-workflow tier genuinely has a different character (multi-adapter, explicit policy planner, background event dispatch) that benefits from a distinct name to set reader expectations.
- **Why not chosen:** The existing codebase already split on this boundary; the `application.py` name communicates "this is the application-level orchestrator" which is a meaningful signal for complex features.

### 3. Use `use_case.py` following Clean Architecture vocabulary
- **Pros:** Clean Architecture (Robert C. Martin) term; maps 1:1 to the "Interactor" concept.
- **Cons:** Unfamiliar to most Python developers; not used in the Python-ecosystem reference text (Cosmic Python); would require renaming both `service.py` and `application.py`.
- **Why not chosen:** `service.py` is already established in the codebase and aligns with Cosmic Python which is the authoritative Python-specific reference for this pattern.

---

## Consequences

- **Positive impacts:** Consistent vocabulary; onboarding developers can map the codebase to Cosmic Python and DDD application-service patterns without a translation step.
- **Tradeoffs accepted:** The `access/sync` `AccessSyncCoordinator` class retains its current name (class rename is a separate decision); only the module and documentation vocabulary changes.
- **Risks introduced:** Transitional inconsistency where `application.py` contains a class still named `...Coordinator`. This is a known and bounded risk; class rename is tracked separately.
- **Mitigations:** This record documents the canonical naming for new packages; existing `access/sync` is the reference for rich-workflow layout regardless of its internal class name.

---

## Compliance and Boundaries

- **Package/infrastructure boundary impact:** None. This record governs package-internal layout only.
- **Type boundary impact:** No change — `domain.py` (frozen dataclass), `schemas.py` (Pydantic), `protocols` (Protocol) rules remain unchanged. See tier-4-09.
- **Startup/plugin registration impact:** No change to hookimpl patterns.
- **Settings partitioning impact:** No change; per-package `config/settings.py` rule is unchanged.

---

## Freshness Review

- **Record age at review time:** Original record predates 2026; estimated >12 months old.
- **Is record older than 30 days:** Yes
- **Web validation completed:** Yes
- **Validation summary:** PEP 8 (April 2025 update) confirmed: no prescriptions on service vs application naming; short, lowercase, underscore-separated module names. FastAPI docs (0.136.x, April 2026): no prescriptions on orchestration-layer naming; confirm thin-handler/dependency-injection pattern. Cosmic Python (last updated 2023-11-24): uses "service layer" / "application service" as canonical vocabulary. "Coordinator" does not appear as a pattern name in any consulted source.
- **Follow-up actions:** Track class rename of `AccessSyncCoordinator` → `AccessSyncApplicationService` as a separate implementation task.

---

## Source References

1. **Architecture Patterns with Python — Chapter 4: Service Layer**
   - URL: https://www.cosmicpython.com/book/chapter_04_service_layer.html
   - Publisher/maintainer: Harry Percival & Bob Gregory (O'Reilly Media)
   - Accessed date: 2026-04-27
   - Relevance: Defines "application service" vs "domain service" distinction; coins "orchestration layer" and "use-case layer" as synonyms for the service layer. Provides the canonical Python-ecosystem vocabulary for this pattern. Quote: "It often makes sense to split out a service layer, sometimes called an orchestration layer or a use-case layer."

2. **Architecture Patterns with Python — Chapter 8: Events and the Message Bus**
   - URL: https://www.cosmicpython.com/book/chapter_08_events_and_message_bus.html
   - Publisher/maintainer: Harry Percival & Bob Gregory (O'Reilly Media)
   - Accessed date: 2026-04-27
   - Relevance: Confirms the service layer as the correct place for event orchestration; discusses the difference between "orchestration" and "choreography" in event-driven workflows.

3. **PEP 8 — Style Guide for Python Code: Package and Module Names**
   - URL: https://peps.python.org/pep-0008/#package-and-module-names
   - Publisher/maintainer: Python Software Foundation
   - Accessed date: 2026-04-27
   - Relevance: Confirms module names should be short, all-lowercase with underscores; no prescription on "service" vs "application" vs "coordinator" — leaves naming to project conventions.

4. **FastAPI Documentation — Bigger Applications: Multiple Files**
   - URL: https://fastapi.tiangolo.com/tutorial/bigger-applications/
   - Publisher/maintainer: Sebastián Ramírez / FastAPI maintainers
   - Accessed date: 2026-04-27
   - Relevance: Confirms thin-router/separate-module pattern; no naming prescription for the orchestration layer but reinforces the principle of separating HTTP concerns from business logic.

---

## Implementation Guidance

- **Required changes for new packages:** Use `service.py` (lean/standard) or `application.py` (rich workflow). Do not create `coordinator.py`.
- **Existing packages:** `access/sync` layout already matches rich-workflow layout; `access/request` matches standard layout; `geolocate` matches lean layout.
- **Validation and quality gates:** `mypy`, `flake8`, `black --check`, `pytest app/tests --ignore=app/tests/smoke`.
- **Test strategy:** Service tests inject mocks directly; route tests patch `providers.get_*` functions.

---

## Change Log

- 2026-04-27: Full restructure to match decision-record-template. Retired `coordinator.py` terminology; introduced three-tier layout model (lean / standard / rich workflow); mapped tiers to existing reference implementations. Added metadata, alternatives, freshness audit, and source references per template. Web-validated against PEP 8, FastAPI 0.136.x docs, and Architecture Patterns with Python (Cosmic Python).

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

## Application Service Pattern (Business Logic)

**Decision**: Business logic is platform-agnostic. Application services hold injected dependencies as constructor arguments and return `OperationResult[T]`. The module is named `service.py` (lean/standard layouts) or `application.py` (rich workflow layout) — see the layout tier table above. `coordinator.py` is not a valid module name for new packages.

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
- ✅ Module named `service.py` (lean/standard) or `application.py` (rich workflow)
- ❌ No `coordinator.py` — use `service.py` or `application.py`
- ❌ No Pydantic models as internal service inputs or outputs
- ❌ No platform-specific logic

---

## Platform Adapters (Protocol Contract)

**Decision**: Platform adapters are defined by a `Protocol` in `adapters/__init__.py`. Concrete implementations live in `adapters/<platform>.py`. Providers inject the correct implementation — services and application services never instantiate adapters directly.

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
- ❌ Do not instantiate adapters inside application service or service methods

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

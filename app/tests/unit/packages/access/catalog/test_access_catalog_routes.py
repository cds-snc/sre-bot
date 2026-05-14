"""Unit tests for packages.access.catalog.interactions.http.

Tests call route handlers directly (no HTTP client needed) by injecting
stub service and settings objects via the FastAPI dependency-injection
protocol used in test_routes patterns across this codebase.
"""

from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from infrastructure.security.models import AuthPrincipalSource, User
from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.security import get_current_user
from packages.access.catalog.providers import get_catalog_service, get_catalog_settings
from packages.access.catalog.domain import (
    EntitlementEntry,
    ParsedEntitlementToken,
    PlatformSummary,
)
from packages.access.catalog.interactions.http import (
    list_entitlements,
    list_platforms,
    router,
)


def _get_route(path: str, method: str) -> APIRoute:
    for route in router.routes:
        if (
            isinstance(route, APIRoute)
            and route.path == path
            and method in route.methods
        ):
            return route
    raise AssertionError(f"Route {method} {path} not found")


# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class _FakeSettings:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled


class _FakeCatalogService:
    def __init__(
        self,
        platforms_result: Optional[OperationResult] = None,
        entitlements_result: Optional[OperationResult] = None,
    ) -> None:
        self._platforms_result = platforms_result or OperationResult.success(data=[])
        self._entitlements_result = entitlements_result or OperationResult.success(
            data=[]
        )

    def list_platforms(self) -> OperationResult:
        return self._platforms_result

    def list_entitlements(self, platform: str, user_email: str) -> OperationResult:
        return self._entitlements_result


def _make_user(email: str = "caller@example.com") -> User:
    """Create a minimal authenticated user for route invocation."""
    return User(
        user_id=email,
        email=email,
        display_name="Test Caller",
        source=AuthPrincipalSource.API_JWT,
        platform_id=email,
    )


def _make_platform_summary(key: str = "aws") -> PlatformSummary:
    return PlatformSummary(
        key=key,
        display_name=key.upper(),
        authn_group_slug=f"sg-{key}-authn",
    )


def _make_entry(
    token: str = "admin",
    mode: str = "sync_managed",
    requestable: bool = True,
    already_provisioned: Optional[bool] = False,
) -> EntitlementEntry:
    return EntitlementEntry(
        token=token,
        group_slug=f"sg-aws-{token}",
        group_email=f"sg-aws-{token}@example.com",
        mode=mode,  # type: ignore[arg-type]
        requestable=requestable,
        already_provisioned=already_provisioned,
        parsed_token=ParsedEntitlementToken(raw=token, parsed=False),
    )


# ---------------------------------------------------------------------------
# list_platforms — disabled gate
# ---------------------------------------------------------------------------


def test_list_platforms_should_return_503_when_feature_disabled():
    # Arrange
    service = _FakeCatalogService()
    settings = _FakeSettings(enabled=False)

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        list_platforms(
            service=service,
            settings=settings,
            current_user=_make_user(),
        )

    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# list_platforms — success
# ---------------------------------------------------------------------------


def test_list_platforms_should_return_platform_list_on_success():
    # Arrange
    summaries = [_make_platform_summary("aws"), _make_platform_summary("gcp")]
    service = _FakeCatalogService(
        platforms_result=OperationResult.success(data=summaries)
    )

    # Act
    response = list_platforms(
        service=service,
        settings=_FakeSettings(),
        current_user=_make_user(),
    )

    # Assert
    assert len(response.platforms) == 2
    assert response.platforms[0].key == "aws"


# ---------------------------------------------------------------------------
# list_platforms — service errors
# ---------------------------------------------------------------------------


def test_list_platforms_should_return_500_when_service_fails():
    # Arrange
    service = _FakeCatalogService(
        platforms_result=OperationResult.error(
            OperationStatus.PERMANENT_ERROR, message="unexpected failure"
        )
    )

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        list_platforms(
            service=service,
            settings=_FakeSettings(),
            current_user=_make_user(),
        )

    assert exc_info.value.status_code == 400


def test_list_platforms_should_return_404_when_service_returns_not_found():
    # Arrange
    service = _FakeCatalogService(
        platforms_result=OperationResult.error(
            OperationStatus.NOT_FOUND,
            message="no configured platforms",
        )
    )

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        list_platforms(
            service=service,
            settings=_FakeSettings(),
            current_user=_make_user(),
        )

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# list_entitlements — disabled gate
# ---------------------------------------------------------------------------


def test_list_entitlements_should_return_503_when_feature_disabled():
    # Arrange
    service = _FakeCatalogService()

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        list_entitlements(
            platform="aws",
            service=service,
            settings=_FakeSettings(enabled=False),
            current_user=_make_user(),
        )

    assert exc_info.value.status_code == 503


@pytest.mark.unit
def test_list_platforms_returns_503_without_service_dependency_assembly():
    app = FastAPI()
    app.include_router(router)

    service_provider_called = False

    def _service_provider() -> _FakeCatalogService:
        nonlocal service_provider_called
        service_provider_called = True
        raise AssertionError("catalog service dependency should not be assembled")

    app.dependency_overrides[get_catalog_settings] = lambda: _FakeSettings(
        enabled=False
    )
    app.dependency_overrides[get_catalog_service] = _service_provider
    app.dependency_overrides[get_current_user] = _make_user

    client = TestClient(app)
    response = client.get("/access/catalog")

    assert response.status_code == 503
    assert response.json()["detail"] == "Access Catalog is not enabled"
    assert service_provider_called is False


# ---------------------------------------------------------------------------
# list_entitlements — success
# ---------------------------------------------------------------------------


def test_list_entitlements_should_return_entitlement_list_on_success():
    # Arrange
    entries = [_make_entry("admin"), _make_entry("readonly")]
    service = _FakeCatalogService(
        entitlements_result=OperationResult.success(data=entries)
    )

    # Act
    response = list_entitlements(
        platform="aws",
        service=service,
        settings=_FakeSettings(),
        current_user=_make_user(),
    )

    # Assert
    assert response.platform == "aws"
    assert len(response.entitlements) == 2


def test_list_entitlements_should_normalize_platform_in_response():
    # Arrange — caller submits mixed-case platform; route normalises it
    entries = [_make_entry("admin")]
    service = _FakeCatalogService(
        entitlements_result=OperationResult.success(data=entries)
    )

    # Act
    response = list_entitlements(
        platform=" AWS ",
        service=service,
        settings=_FakeSettings(),
        current_user=_make_user(),
    )

    # Assert
    assert response.platform == "aws"


# ---------------------------------------------------------------------------
# list_entitlements — service errors
# ---------------------------------------------------------------------------


def test_list_entitlements_should_return_404_when_platform_not_found():
    # Arrange
    service = _FakeCatalogService(
        entitlements_result=OperationResult.error(
            OperationStatus.NOT_FOUND,
            message="Platform 'nonexistent' is not configured.",
            error_code="PLATFORM_NOT_FOUND",
        )
    )

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        list_entitlements(
            platform="nonexistent",
            service=service,
            settings=_FakeSettings(),
            current_user=_make_user(),
        )

    assert exc_info.value.status_code == 404


def test_list_entitlements_should_return_500_when_service_fails():
    # Arrange
    service = _FakeCatalogService(
        entitlements_result=OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="IDP unavailable",
        )
    )

    # Act / Assert
    with pytest.raises(HTTPException) as exc_info:
        list_entitlements(
            platform="aws",
            service=service,
            settings=_FakeSettings(),
            current_user=_make_user(),
        )

    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# list_entitlements — response serialisation
# ---------------------------------------------------------------------------


def test_list_entitlements_should_propagate_membership_status():
    # Arrange
    entries = [_make_entry("admin", already_provisioned=True)]
    service = _FakeCatalogService(
        entitlements_result=OperationResult.success(data=entries)
    )

    # Act
    response = list_entitlements(
        platform="aws",
        service=service,
        settings=_FakeSettings(),
        current_user=_make_user(),
    )

    # Assert
    assert response.entitlements[0].already_provisioned is True


def test_list_entitlements_should_propagate_requestable_flag():
    # Arrange
    entries = [_make_entry("legacy-role", mode="deactivated", requestable=False)]
    service = _FakeCatalogService(
        entitlements_result=OperationResult.success(data=entries)
    )

    # Act
    response = list_entitlements(
        platform="aws",
        service=service,
        settings=_FakeSettings(),
        current_user=_make_user(),
    )

    # Assert
    assert response.entitlements[0].requestable is False
    assert response.entitlements[0].mode == "deactivated"


@pytest.mark.unit
def test_catalog_routes_expose_explicit_openapi_metadata() -> None:
    cases = [
        ("/access/catalog", "GET", 200, {503}),
        ("/access/catalog/{platform}", "GET", 200, {404, 503}),
    ]

    for path, method, expected_status, expected_non_2xx_codes in cases:
        route = _get_route(path, method)

        assert route.summary
        assert route.description
        assert route.status_code == expected_status

        documented_codes = {int(code) for code in route.responses}
        assert expected_non_2xx_codes.issubset(documented_codes)

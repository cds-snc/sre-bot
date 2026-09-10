"""Unit tests for integrations.google_workspace.client primitives.

These tests define expected error-classification and service-construction
behavior for Google Directory API adapter wiring.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError
from googleapiclient.http import HttpRequest

from infrastructure.operations.status import OperationStatus


def _http_error(status: int, reason: str = "boom", retry_after: str | None = None) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = reason
            if retry_after is not None:
                self["retry-after"] = retry_after

    return HttpError(resp=FakeResp(), content=b"{}")


@pytest.fixture
def google_client_module() -> Any:
    try:
        return importlib.import_module("integrations.google_workspace.client")
    except ModuleNotFoundError as exc:
        pytest.fail(f"Expected integrations.google_workspace.client module to exist: {exc}")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [
        (404, OperationStatus.NOT_FOUND),
        (401, OperationStatus.UNAUTHORIZED),
        (403, OperationStatus.UNAUTHORIZED),
        (429, OperationStatus.TRANSIENT_ERROR),
        (500, OperationStatus.TRANSIENT_ERROR),
        (502, OperationStatus.TRANSIENT_ERROR),
        (503, OperationStatus.TRANSIENT_ERROR),
        (504, OperationStatus.TRANSIENT_ERROR),
    ],
)
def test_classify_google_error_expected_mappings(
    google_client_module: Any,
    status_code: int,
    expected_status: OperationStatus,
) -> None:
    status, error_code, retry_after = google_client_module.classify_google_error(_http_error(status_code))

    assert status is expected_status
    assert error_code == str(status_code)
    assert retry_after is None


@pytest.mark.unit
def test_classify_google_error_uses_retry_after_header(google_client_module: Any) -> None:
    status, error_code, retry_after = google_client_module.classify_google_error(_http_error(429, retry_after="120"))

    assert status is OperationStatus.TRANSIENT_ERROR
    assert error_code == "429"
    assert retry_after == 120


@pytest.mark.unit
def test_classify_google_error_propagates_unmapped_http_status(google_client_module: Any) -> None:
    with pytest.raises(HttpError):
        google_client_module.classify_google_error(_http_error(418))


@pytest.mark.unit
def test_classify_google_error_propagates_non_http_error(google_client_module: Any) -> None:
    with pytest.raises(KeyError):
        google_client_module.classify_google_error(KeyError("not-http"))


@pytest.mark.unit
def test_get_admin_directory_service_builds_with_static_discovery_and_no_cache(
    monkeypatch: pytest.MonkeyPatch,
    google_client_module: Any,
) -> None:
    captured: dict[str, Any] = {}

    settings = SimpleNamespace(
        GCP_SRE_SERVICE_ACCOUNT_KEY_FILE='{"client_email":"sre-bot@example.com","private_key":"FAKE"}',
        SRE_BOT_EMAIL="sre-bot@example.com",
        GOOGLE_API_NUM_RETRIES=3,
    )

    class FakeCredentials:
        def with_scopes(self, scopes: list[str]) -> FakeCredentials:
            captured["scopes"] = scopes
            return self

        def with_subject(self, subject: str) -> FakeCredentials:
            captured["delegated_subject"] = subject
            return self

    fake_service = MagicMock()

    monkeypatch.setattr(google_client_module, "get_google_workspace_settings", lambda: settings)
    monkeypatch.setattr(
        google_client_module.service_account.Credentials,
        "from_service_account_info",
        lambda info: FakeCredentials(),
    )

    def fake_build(api_name: str, api_version: str, **kwargs: Any) -> Any:
        captured["build_api_name"] = api_name
        captured["build_api_version"] = api_version
        captured["build_kwargs"] = kwargs
        return fake_service

    monkeypatch.setattr(google_client_module, "build", fake_build)

    returned_service = google_client_module.get_admin_directory_service(
        scopes=["https://www.googleapis.com/auth/admin.directory.user.readonly"],
    )

    assert returned_service is fake_service
    assert captured["build_api_name"] == "admin"
    assert captured["build_api_version"] == "directory_v1"
    assert captured["build_kwargs"]["cache_discovery"] is False
    assert captured["build_kwargs"]["static_discovery"] is True
    assert callable(captured["build_kwargs"]["requestBuilder"])
    assert captured["delegated_subject"] == "sre-bot@example.com"


def _install_fake_build(
    monkeypatch: pytest.MonkeyPatch,
    google_client_module: Any,
    captured: dict[str, Any],
) -> Any:
    settings = SimpleNamespace(
        GCP_SRE_SERVICE_ACCOUNT_KEY_FILE='{"client_email":"sre-bot@example.com","private_key":"FAKE"}',
        SRE_BOT_EMAIL="sre-bot@example.com",
        GOOGLE_API_NUM_RETRIES=3,
    )

    class FakeCredentials:
        def with_scopes(self, scopes: list[str]) -> FakeCredentials:
            captured["scopes"] = scopes
            return self

        def with_subject(self, subject: str) -> FakeCredentials:
            captured["delegated_subject"] = subject
            return self

    fake_service = MagicMock()

    monkeypatch.setattr(google_client_module, "get_google_workspace_settings", lambda: settings)
    monkeypatch.setattr(
        google_client_module.service_account.Credentials,
        "from_service_account_info",
        lambda info: FakeCredentials(),
    )

    def fake_build(api_name: str, api_version: str, **kwargs: Any) -> Any:
        captured["build_api_name"] = api_name
        captured["build_api_version"] = api_version
        captured["build_kwargs"] = kwargs
        return fake_service

    monkeypatch.setattr(google_client_module, "build", fake_build)
    return fake_service


@pytest.mark.unit
@pytest.mark.parametrize(
    ("factory_name", "api_name", "api_version", "scope"),
    [
        (
            "get_calendar_service",
            "calendar",
            "v3",
            "https://www.googleapis.com/auth/calendar",
        ),
        (
            "get_meet_service",
            "meet",
            "v2",
            "https://www.googleapis.com/auth/meetings.space.created",
        ),
        (
            "get_docs_service",
            "docs",
            "v1",
            "https://www.googleapis.com/auth/documents",
        ),
        (
            "get_sheets_service",
            "sheets",
            "v4",
            "https://www.googleapis.com/auth/spreadsheets",
        ),
    ],
)
def test_service_factories_build_with_static_discovery_and_no_cache(
    monkeypatch: pytest.MonkeyPatch,
    google_client_module: Any,
    factory_name: str,
    api_name: str,
    api_version: str,
    scope: str,
) -> None:
    captured: dict[str, Any] = {}
    fake_service = _install_fake_build(monkeypatch, google_client_module, captured)

    factory = getattr(google_client_module, factory_name, None)
    if factory is None:
        pytest.fail(f"Expected integrations.google_workspace.client.{factory_name} to exist")

    returned_service = factory(scopes=[scope])

    assert returned_service is fake_service
    assert captured["build_api_name"] == api_name
    assert captured["build_api_version"] == api_version
    assert captured["build_kwargs"]["cache_discovery"] is False
    assert captured["build_kwargs"]["static_discovery"] is True
    assert callable(captured["build_kwargs"]["requestBuilder"])
    assert captured["scopes"] == [scope]
    assert captured["delegated_subject"] == "sre-bot@example.com"


@pytest.mark.unit
def test_request_builder_defaults_and_honors_explicit_retry_count(
    monkeypatch: pytest.MonkeyPatch,
    google_client_module: Any,
) -> None:
    captured: list[int] = []

    def fake_parent_execute(self: HttpRequest, http: Any = None, num_retries: int = 0, **kwargs: Any) -> Any:
        captured.append(num_retries)
        return {"ok": True}

    monkeypatch.setattr(HttpRequest, "execute", fake_parent_execute)
    request_builder = google_client_module._build_request_builder(3)
    request = request_builder(None, MagicMock(), "https://example.test")

    assert request.execute() == {"ok": True}
    assert request.execute(num_retries=0) == {"ok": True}
    assert captured == [3, 0]


@pytest.mark.unit
def test_google_workspace_settings_retry_count_defaults_and_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from infrastructure.configuration.integrations.google import GoogleWorkspaceSettings

    assert GoogleWorkspaceSettings().GOOGLE_API_NUM_RETRIES == 3
    monkeypatch.setenv("GOOGLE_API_NUM_RETRIES", "7")
    assert GoogleWorkspaceSettings().GOOGLE_API_NUM_RETRIES == 7


@pytest.mark.unit
@pytest.mark.parametrize(
    "factory_name",
    ["get_calendar_service", "get_meet_service", "get_docs_service", "get_sheets_service"],
)
def test_service_factories_use_explicit_delegated_user_email(
    monkeypatch: pytest.MonkeyPatch,
    google_client_module: Any,
    factory_name: str,
) -> None:
    captured: dict[str, Any] = {}
    _install_fake_build(monkeypatch, google_client_module, captured)

    factory = getattr(google_client_module, factory_name, None)
    if factory is None:
        pytest.fail(f"Expected integrations.google_workspace.client.{factory_name} to exist")

    factory(scopes=["https://www.googleapis.com/auth/calendar"], delegated_user_email="delegate@example.com")

    assert captured["delegated_subject"] == "delegate@example.com"

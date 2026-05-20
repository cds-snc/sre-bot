"""Unit tests for packages.access.request package initialization behavior."""

import importlib
from typing import get_args, get_origin, get_type_hints

import pytest

from infrastructure.operations import OperationResult
from infrastructure.events import get_event_dispatcher
from packages.access.common.events import SYNC_COMPLETED, SYNC_FAILED
from packages.access.request.domain import AccessRequest, ApprovalDecision
from packages.access.request.service import AccessRequestServicePort


def _reload_request_package():
    module = importlib.import_module("packages.access.request")
    return importlib.reload(module)


@pytest.mark.unit
def test_request_package_import_has_no_event_registration_side_effects():
    get_event_dispatcher.cache_clear()

    _reload_request_package()
    dispatcher = get_event_dispatcher()

    assert dispatcher.get_handler_count(SYNC_COMPLETED) == 0
    assert dispatcher.get_handler_count(SYNC_FAILED) == 0


@pytest.mark.unit
def test_request_startup_warmup_registers_handlers_and_warms_runtime_config(
    monkeypatch,
):
    get_event_dispatcher.cache_clear()
    request_pkg = _reload_request_package()

    runtime_config_called = False
    provider_warm_called = False

    def _runtime_config() -> object:
        nonlocal runtime_config_called
        runtime_config_called = True
        return object()

    class _Settings:
        enabled = True
        manager_group_slug = "sg-managers"
        fallback_approver_slug = "sg-org-admins"
        min_approver_count = 1
        request_ttl_hours = 72

    def _warm_provider() -> object:
        nonlocal provider_warm_called
        provider_warm_called = True
        return object()

    monkeypatch.setattr(
        request_pkg, "get_access_runtime_config", _runtime_config, raising=False
    )
    monkeypatch.setattr(request_pkg, "get_access_request_settings", lambda: _Settings())
    monkeypatch.setattr(request_pkg, "get_access_request_service", _warm_provider)

    request_pkg.startup_warmup(
        logger=type(
            "L",
            (),
            {
                "info": lambda *a, **k: None,
                "warning": lambda *a, **k: None,
                "error": lambda *a, **k: None,
            },
        )()
    )

    assert runtime_config_called is True
    assert provider_warm_called is True
    dispatcher = get_event_dispatcher()
    assert dispatcher.get_handler_count(SYNC_COMPLETED) == 1
    assert dispatcher.get_handler_count(SYNC_FAILED) == 1


@pytest.mark.unit
def test_request_startup_warmup_registers_handlers_via_event_dispatcher(monkeypatch):
    request_pkg = _reload_request_package()

    class _Settings:
        enabled = True
        manager_group_slug = "sg-managers"
        fallback_approver_slug = "sg-org-admins"
        min_approver_count = 1
        request_ttl_hours = 72

    class _Dispatcher:
        def __init__(self) -> None:
            self._handlers: dict[str, list[object]] = {}

        def get_handler_count(self, event_type: str) -> int:
            return len(self._handlers.get(event_type, []))

        def register_handler(self, event_type: str, handler) -> None:
            self._handlers.setdefault(event_type, []).append(handler)

    dispatcher = _Dispatcher()

    monkeypatch.setattr(request_pkg, "get_access_runtime_config", lambda: object())
    monkeypatch.setattr(request_pkg, "get_access_request_settings", lambda: _Settings())
    monkeypatch.setattr(request_pkg, "get_access_request_service", lambda: object())
    monkeypatch.setattr(request_pkg, "get_event_dispatcher", lambda: dispatcher)

    # Enforce DI boundary: package code must not call module-level registration.
    monkeypatch.setattr(
        request_pkg,
        "register_event_handler",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("direct register_event_handler usage is forbidden")
        ),
        raising=False,
    )
    monkeypatch.setattr(
        request_pkg,
        "get_handlers_for_event",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("direct get_handlers_for_event usage is forbidden")
        ),
        raising=False,
    )

    request_pkg.startup_warmup(
        logger=type(
            "L",
            (),
            {
                "info": lambda *a, **k: None,
                "warning": lambda *a, **k: None,
                "error": lambda *a, **k: None,
            },
        )()
    )

    assert dispatcher.get_handler_count(SYNC_COMPLETED) == 1
    assert dispatcher.get_handler_count(SYNC_FAILED) == 1


@pytest.mark.unit
def test_access_request_service_port_uses_parameterized_operation_result_returns():
    expected_returns = {
        "submit_request": OperationResult[AccessRequest],
        "approve_request": OperationResult[
            tuple[AccessRequest, list[ApprovalDecision]]
        ],
        "reject_request": OperationResult[tuple[AccessRequest, list[ApprovalDecision]]],
        "cancel_request": OperationResult[tuple[AccessRequest, list[ApprovalDecision]]],
        "retry_request": OperationResult[tuple[AccessRequest, list[ApprovalDecision]]],
        "get_request_status": OperationResult[
            tuple[AccessRequest, list[ApprovalDecision]]
        ],
    }

    for method_name, expected in expected_returns.items():
        method = getattr(AccessRequestServicePort, method_name)
        return_type = get_type_hints(method)["return"]

        assert get_origin(return_type) is get_origin(expected)
        assert get_args(return_type) == get_args(expected)

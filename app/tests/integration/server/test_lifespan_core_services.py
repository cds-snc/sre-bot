"""Integration tests for lifecycle phase 2: resolving the core services at boot.

The real lifespan runs with later startup phases stubbed. A raising factory in
the core service table must stop startup before the lifespan yields, and phase 2
must run before plugin loading. The no-network case runs the real host
registration with real boto3 clients and replaces socket.connect with a recording
spy. It sets static AWS credentials and disables the instance metadata endpoint,
because the ambient credential chain contacts that endpoint when a client is
built (TASK-149 removes the need for this).
"""

import socket
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
import structlog
import svcs
from fastapi import FastAPI

from contracts.records import RecordStore
from server.lifespan import lifespan
from server.services import CoreService, initialize_core_services

pytestmark = pytest.mark.integration


class _FactoryFailedError(Exception):
    pass


def _raising_build() -> RecordStore:
    raise _FactoryFailedError("record store construction failed")


def _stub_later_phases(stack: ExitStack) -> None:
    provider = MagicMock()
    provider.app = None
    stack.enter_context(patch("server.lifespan._initialize_security_services"))
    stack.enter_context(patch("server.lifespan._initialize_directory_provider"))
    stack.enter_context(patch("server.lifespan.get_slack_provider", return_value=provider))
    stack.enter_context(patch("server.lifespan.load_plugins"))
    stack.enter_context(patch("server.lifespan._initialize_translation_service"))
    stack.enter_context(patch("server.lifespan.register_feature_integrations"))
    stack.enter_context(patch("server.lifespan._register_legacy_slack_commands"))


async def test_lifespan_aborts_before_yield_when_a_core_service_factory_raises() -> None:
    reached_yield = False

    with ExitStack() as stack, pytest.raises(_FactoryFailedError):
        _stub_later_phases(stack)
        stack.enter_context(patch("server.services.CORE_SERVICES", (CoreService(RecordStore, _raising_build),)))
        async with lifespan(FastAPI()):
            reached_yield = True

    assert reached_yield is False


async def test_core_services_phase_runs_before_plugin_loading() -> None:
    order: list[str] = []

    async def _record_core_services(registry: svcs.Registry, logger: object) -> None:
        order.append("core_services")

    with ExitStack() as stack:
        _stub_later_phases(stack)
        stack.enter_context(patch("server.lifespan.initialize_core_services", _record_core_services))
        stack.enter_context(patch("server.lifespan.load_plugins", side_effect=lambda pm, logger: order.append("plugin_loading")))
        async with lifespan(FastAPI()):
            pass

    assert order == ["core_services", "plugin_loading"]


@pytest.mark.usefixtures("static_aws_credentials")
async def test_resolving_every_core_service_opens_no_outbound_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    connects: list[object] = []
    real_connect = socket.socket.connect

    def _spy_connect(self: socket.socket, address: object) -> None:
        connects.append(address)
        real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", _spy_connect)

    async with svcs.Registry() as registry:
        await initialize_core_services(registry, structlog.get_logger())

    assert connects == []

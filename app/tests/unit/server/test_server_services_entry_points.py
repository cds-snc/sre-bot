"""Unit tests for route-level resolution from the svcs registry.

An HTTP route takes svcs.fastapi.DepContainer, on an app whose svcs lifespan
runs the host registration. The fake is registered after startup, because the
lifespan would otherwise overwrite it. A route that resolves a record store gets
the registered fake, and an unregistered contract raises the registry's error.
Slack handlers and jobs open their service scopes through the host opener; see
test_server_services_scope_entry_points.py.
"""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
import svcs
from fastapi import FastAPI
from fastapi.testclient import TestClient

from contracts.records import RecordStore
from server.services import register_core_services

pytestmark = pytest.mark.unit


def _test_app() -> FastAPI:
    @svcs.fastapi.lifespan
    async def lifespan(app: FastAPI, registry: svcs.Registry) -> AsyncGenerator[None]:
        register_core_services(registry)
        yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/record-store")
    async def record_store_route(services: svcs.fastapi.DepContainer) -> dict[str, str]:
        store = await services.aget(RecordStore)
        return {"store": type(store).__name__}

    return app


def test_route_resolves_a_service_through_dep_container() -> None:
    fake = MagicMock(spec=RecordStore)

    with TestClient(_test_app()) as client:
        svcs.fastapi.get_registry(client).register_value(RecordStore, fake)
        response = client.get("/record-store")

    assert response.status_code == 200
    assert response.json() == {"store": type(fake).__name__}


def test_resolving_an_unregistered_contract_raises() -> None:
    with svcs.Container(svcs.Registry()) as container, pytest.raises(svcs.exceptions.ServiceNotFoundError):
        container.get(RecordStore)

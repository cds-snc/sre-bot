"""Reference entry points that resolve services from the svcs registry.

No production route, Slack handler or job resolves from the registry yet, so
these tests define one of each on a test app and show the convention works:
- an HTTP route takes svcs.fastapi.DepContainer, on an app whose svcs lifespan
  runs the host registration; the fake is registered after startup, because
  the lifespan would otherwise overwrite it;
- a Slack-style async handler and a job-style sync function each open their own
  container per invocation.
A generator factory records when its cleanup runs, which proves each container
is closed when the invocation ends, including when the invocation raises.
"""

from collections.abc import AsyncGenerator, Iterator
from unittest.mock import MagicMock

import pytest
import svcs
from fastapi import FastAPI
from fastapi.testclient import TestClient

from contracts.coordination import ConditionalWriteStore
from contracts.records import RecordStore
from server.services import register_core_services

pytestmark = pytest.mark.unit


class _HandlerFailedError(Exception):
    pass


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


async def _slack_style_handler(registry: svcs.Registry, *, fail: bool = False) -> ConditionalWriteStore:
    async with svcs.Container(registry) as container:
        store = await container.aget(ConditionalWriteStore)
        if fail:
            raise _HandlerFailedError
        return store


def _job_style_function(registry: svcs.Registry) -> ConditionalWriteStore:
    with svcs.Container(registry) as container:
        return container.get(ConditionalWriteStore)


@pytest.fixture
def cleanup_tracking_registry() -> tuple[svcs.Registry, list[str], ConditionalWriteStore]:
    store = MagicMock(spec=ConditionalWriteStore)
    cleanups: list[str] = []

    def factory() -> Iterator[ConditionalWriteStore]:
        yield store
        cleanups.append("closed")

    registry = svcs.Registry()
    registry.register_factory(ConditionalWriteStore, factory)
    return registry, cleanups, store


def test_route_resolves_a_service_through_dep_container() -> None:
    fake = MagicMock(spec=RecordStore)

    with TestClient(_test_app()) as client:
        svcs.fastapi.get_registry(client).register_value(RecordStore, fake)
        response = client.get("/record-store")

    assert response.status_code == 200
    assert response.json() == {"store": type(fake).__name__}


async def test_slack_style_handler_closes_its_container_after_each_invocation(
    cleanup_tracking_registry: tuple[svcs.Registry, list[str], ConditionalWriteStore],
) -> None:
    registry, cleanups, store = cleanup_tracking_registry

    assert await _slack_style_handler(registry) is store
    assert await _slack_style_handler(registry) is store

    assert cleanups == ["closed", "closed"]


async def test_slack_style_handler_closes_its_container_when_it_raises(
    cleanup_tracking_registry: tuple[svcs.Registry, list[str], ConditionalWriteStore],
) -> None:
    registry, cleanups, _ = cleanup_tracking_registry

    with pytest.raises(_HandlerFailedError):
        await _slack_style_handler(registry, fail=True)

    assert cleanups == ["closed"]


def test_job_style_function_closes_its_container_after_each_invocation(
    cleanup_tracking_registry: tuple[svcs.Registry, list[str], ConditionalWriteStore],
) -> None:
    registry, cleanups, store = cleanup_tracking_registry

    assert _job_style_function(registry) is store
    assert cleanups == ["closed"]


def test_resolving_an_unregistered_contract_raises() -> None:
    with svcs.Container(svcs.Registry()) as container, pytest.raises(svcs.exceptions.ServiceNotFoundError):
        container.get(RecordStore)

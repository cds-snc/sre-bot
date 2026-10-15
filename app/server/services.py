"""Host registration of core services in the svcs registry.

Each contracts Protocol the host provides is registered under its own type. The
concrete classes are named here and nowhere else outside infrastructure/.
Entry points resolve services from a container; services receive their
dependencies through their constructors.
"""

import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

import svcs
from structlog.stdlib import BoundLogger

from contracts.coordination import ConditionalWriteStore
from contracts.records import RecordStore
from contracts.services import ServiceResolver
from infrastructure.coordination import DynamoDBConditionalWriteStore, get_conditional_write_settings
from infrastructure.records.service import DynamoDBRecordStore
from integrations.aws.client import get_aws_client


@dataclass(frozen=True)
class CoreService:
    """One registration: the contract it is resolved by and how to build it.

    build does no network I/O: it constructs the service and validates its
    settings only.
    """

    contract: type
    build: Callable[[], object]


def _build_record_store() -> RecordStore:
    return DynamoDBRecordStore(get_aws_client("dynamodb"))


def _build_conditional_write_store() -> ConditionalWriteStore:
    return DynamoDBConditionalWriteStore(get_aws_client("dynamodb"), settings=get_conditional_write_settings())


CORE_SERVICES: tuple[CoreService, ...] = (
    CoreService(RecordStore, _build_record_store),
    CoreService(ConditionalWriteStore, _build_conditional_write_store),
)


def _once(build: Callable[[], object]) -> Callable[[], object]:
    """Return a factory that builds on its first call and returns that instance afterwards."""
    lock = threading.Lock()
    instances: list[object] = []

    def factory() -> object:
        with lock:
            if not instances:
                instances.append(build())
            return instances[0]

    return factory


def register_core_services(registry: svcs.Registry) -> None:
    """Register every core service; each registry builds its own instances, once."""
    for service in CORE_SERVICES:
        registry.register_factory(service.contract, _once(service.build))


async def initialize_core_services(registry: svcs.Registry, logger: BoundLogger) -> None:
    """Lifecycle phase 2: register the core services and resolve each one once.

    A factory that raises propagates, so startup stops before the app serves.
    """
    log = logger.bind(phase="core_services")
    register_core_services(registry)
    async with svcs.Container(registry) as container:
        for service in CORE_SERVICES:
            await container.aget(service.contract)
            log.info("core_service_resolved", contract=service.contract.__name__)
    log.info("core_services_initialized", count=len(CORE_SERVICES))


class SvcsServiceScopeOpener:
    """Opens one svcs container per invocation for non-HTTP entry points.

    The only place a container is opened for Slack handlers and jobs. Each
    create_scope() builds its own container, so worker threads never share one, and the
    container is closed on exit, including when the body raises.
    """

    def __init__(self, registry: svcs.Registry) -> None:
        self._registry = registry

    def create_scope(self) -> AbstractContextManager[ServiceResolver]:
        """Return a fresh container; it is its own resolver and closes itself on exit."""
        return svcs.Container(self._registry)

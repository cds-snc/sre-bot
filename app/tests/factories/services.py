"""Protocol-conformant fake for the per-invocation service scope contract."""

from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from typing import Any, cast

from contracts.services import ServiceResolver


class FakeServiceResolver:
    """Resolves contracts from a fixed mapping; an unregistered contract raises KeyError."""

    def __init__(self, services: Mapping[type, object]) -> None:
        self._services = services

    def get[T](self, contract: type[T]) -> T:
        """Return the service registered under ``contract``."""
        return cast(T, self._services[contract])


class FakeServiceScopeOpener:
    """Opens scopes over a fixed service mapping and counts the scopes opened and closed."""

    def __init__(self, services: Mapping[type, Any]) -> None:
        self.services = dict(services)
        self.opened = 0
        self.closed = 0

    def create_scope(self) -> AbstractContextManager[ServiceResolver]:
        """Return a scope yielding a resolver over the mapping; it is closed on exit, including on raise."""
        return self._scope()

    @contextmanager
    def _scope(self) -> Iterator[ServiceResolver]:
        self.opened += 1
        try:
            yield FakeServiceResolver(self.services)
        finally:
            self.closed += 1

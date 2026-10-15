"""Protocols for opening a per-invocation service scope at a non-HTTP entry point.

Slack handlers, scheduled jobs and other entry points open a scope with
``ServiceScopeOpener.create_scope()``, resolve the contracts they need from the yielded
``ServiceResolver``, build their services from those resolved contracts and call
one service method. The resolver is never handed to a service: resolving at the
entry point is dependency injection, resolving inside a service is service
location.

The scope is synchronous until async Bolt lands (TASK-33), which adds an async
variant beside ``create_scope()``. This module imports no container library; the host
implements the Protocols over its own registry.

See: decisions/dependency-injection.md
"""

from contextlib import AbstractContextManager
from typing import Protocol


class ServiceResolver(Protocol):
    """Resolves a registered contract to its service within one scope."""

    def get[T](self, contract: type[T]) -> T:
        """Return the service registered under ``contract``.

        Raises:
            Exception: The host's not-found error when ``contract`` is not registered.
        """
        ...


class ServiceScopeOpener(Protocol):
    """Opens one resolver scope per invocation and releases it on exit."""

    def create_scope(self) -> AbstractContextManager[ServiceResolver]:
        """Open a scope; it is closed when the context exits, including on raise."""
        ...

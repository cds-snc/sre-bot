"""Extension points: how a capability collects the strategies other plugins contribute to it.

A capability declares one ``ExtensionPoint`` through the ``register_extension_points``
hookspec. In lifespan phase 4 the host adds the point's hookspec class, then calls its
``initialize`` once, after the capabilities it depends on, and registers the returned
value in the service registry under ``provides``. At runtime the capability reads that
value; no pluggy hook is called per request.

See: decisions/plugins.md, decisions/lifecycle.md
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from contracts.services import ServiceResolver, ServiceScopeOpener


class ExtensionPointContext(Protocol):
    """What a capability's ``initialize`` receives.

    ``collect`` and ``services`` refuse use once ``initialize`` returns; ``service_scopes``
    is meant to be kept by the strategies the capability builds.
    """

    @property
    def services(self) -> ServiceResolver:
        """Resolve a value registered before this point, such as the content catalogue or a dependency's value."""
        ...

    @property
    def service_scopes(self) -> ServiceScopeOpener:
        """The host's opener, handed on to contributed strategies for their per-invocation scopes."""
        ...

    def collect(self, hook_name: str, /, **kwargs: object) -> Mapping[str, object]:
        """Call one of the point's own hooks once on every plugin that implements it.

        Returns:
            Each contributing plugin's non-None result by entry-point name, in load order.
            The values come from other plugins: the capability validates them.
        """
        ...


@dataclass(frozen=True)
class ExtensionPoint[T]:
    """A capability's extension point; the host names it after the declaring plugin.

    Attributes:
        specs: The capability's hookspec class; contributing plugins implement its hooks.
        provides: The service-registry key the initialized value is registered under.
        initialize: Builds the value from the context. It decides how many contributions
            the capability needs and raises, failing boot, when they are not met.
        depends_on: Entry-point names of capabilities whose values ``initialize`` reads;
            they initialize first. This is the capabilities' declared order.
    """

    specs: type
    provides: type[T]
    initialize: Callable[[ExtensionPointContext], T]
    depends_on: tuple[str, ...] = ()


class ExtensionPointRegistrar(Protocol):
    """Receives a capability's extension point; a capability declares at most one."""

    def declare(self, point: ExtensionPoint[Any]) -> None:
        """Declare the calling capability's extension point."""
        ...

"""Lifespan phase 4: each capability's extension point, collected once before the capability initializes.

After plugin loading, every enabled capability declares at most one extension point
through ``register_extension_points``. The host adds each point's hookspec class, which
makes pluggy verify the hookimpls already registered for it, orders the points by
``depends_on`` (ties in plugin load order), and calls each ``initialize`` once with a
context that collects only the point's own hooks. Each value is registered in the svcs
registry under the point's ``provides`` type. ``collect`` and ``services`` refuse every
call once ``initialize`` returns, so no pluggy hook is reached per request.

A blocked (disabled) capability is not registered: its point is never declared, and the
hookimpls other plugins wrote for it stay unverified and are never called.

See: decisions/lifecycle.md, decisions/plugins.md
"""

import graphlib
from collections.abc import Mapping
from types import ModuleType
from typing import TYPE_CHECKING, Any

import pluggy
import svcs

from contracts.plugins.extension_points import ExtensionPoint
from contracts.services import ServiceResolver, ServiceScopeOpener
from server.plugins.boot import UNKNOWN_PLUGIN, attribute_built_slices, call_hook_per_plugin, log_plugin_boot_failed

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger

PHASE = "extension_points"
DECLARE_HOOK = "register_extension_points"
CAPABILITY_PACKAGE = "capabilities"


class ExtensionPointError(RuntimeError):
    """An extension point that cannot be declared, ordered or initialized; the message names the plugins."""


def run_extension_points(
    pm: pluggy.PluginManager, registry: svcs.Registry, service_scopes: ServiceScopeOpener, logger: BoundLogger
) -> None:
    """Declare, order and initialize every enabled capability's extension point, then log the phase.

    Every failure is logged once as ``plugin_boot_failed`` naming the plugin at fault and re-raised,
    so startup stops before the app serves.
    """
    points = _declare(pm, logger)
    for name, point in points.items():
        _add_specs(pm, name, point, logger)
    order = _order(points, logger)
    implementation_count = 0
    for name in order:
        implementation_count += _initialize(pm, registry, service_scopes, name, points[name], logger)
    logger.info("extension_points_initialized", phase=PHASE, extension_points=order, implementation_count=implementation_count)


class _PluginRegistrar:
    """The registrar one plugin's ``register_extension_points`` receives."""

    def __init__(self, plugin: str, module: str, points: dict[str, ExtensionPoint[Any]]) -> None:
        self._plugin = plugin
        self._module = module
        self._points = points

    def declare(self, point: ExtensionPoint[Any]) -> None:
        if self._module.partition(".")[0] != CAPABILITY_PACKAGE:
            raise ExtensionPointError(f"extension_point_outside_capability: plugin {self._plugin!r} is not a capability")
        if self._plugin in self._points:
            raise ExtensionPointError(f"extension_point_declared_twice: capability {self._plugin!r} declares at most one")
        self._points[self._plugin] = point


def _declare(pm: pluggy.PluginManager, logger: BoundLogger) -> dict[str, ExtensionPoint[Any]]:
    """Call each plugin's ``register_extension_points`` with a registrar scoped to it, in load order."""
    points: dict[str, ExtensionPoint[Any]] = {}
    plugins = [(name, plugin) for name, plugin in pm.list_name_plugin() if plugin is not None]
    for name, plugin in plugins:
        others = [other for _, other in plugins if other is not plugin]
        hook = pm.subset_hook_caller(DECLARE_HOOK, remove_plugins=others)
        try:
            with attribute_built_slices(name):
                hook(registrar=_PluginRegistrar(name, _module_name(plugin), points))
        except Exception as error:
            log_plugin_boot_failed(logger, plugin=name, phase=DECLARE_HOOK, error=error)
            raise
    return points


def _module_name(plugin: object) -> str:
    return plugin.__name__ if isinstance(plugin, ModuleType) else type(plugin).__module__


def _add_specs(pm: pluggy.PluginManager, name: str, point: ExtensionPoint[Any], logger: BoundLogger) -> None:
    """Add the point's hookspec class; pluggy verifies every hookimpl already registered for it."""
    try:
        pm.add_hookspecs(point.specs)
    except pluggy.PluginValidationError as error:
        log_plugin_boot_failed(logger, plugin=pm.get_name(error.plugin) or UNKNOWN_PLUGIN, phase=PHASE, error=error)
        raise
    except Exception as error:
        log_plugin_boot_failed(logger, plugin=name, phase=PHASE, error=error)
        raise


def _order(points: Mapping[str, ExtensionPoint[Any]], logger: BoundLogger) -> list[str]:
    """Return the point names with each after its dependencies; independent points keep plugin load order."""
    load_order = list(points)
    for name, point in points.items():
        missing = [dependency for dependency in point.depends_on if dependency not in points]
        if missing:
            error = ExtensionPointError(
                f"extension_point_dependency_undeclared: capability {name!r} depends on {missing}, which declare none"
            )
            log_plugin_boot_failed(logger, plugin=name, phase=PHASE, error=error)
            raise error
    sorter = graphlib.TopologicalSorter({name: point.depends_on for name, point in points.items()})
    try:
        sorter.prepare()
    except graphlib.CycleError as cycle:
        members: list[str] = cycle.args[1]
        error = ExtensionPointError(f"extension_point_cycle: {' -> '.join(members)}")
        log_plugin_boot_failed(logger, plugin=min(members, key=load_order.index), phase=PHASE, error=error)
        raise error from cycle
    order: list[str] = []
    while sorter.is_active():
        ready = sorted(sorter.get_ready(), key=load_order.index)
        order.extend(ready)
        sorter.done(*ready)
    return order


def _initialize(
    pm: pluggy.PluginManager,
    registry: svcs.Registry,
    service_scopes: ServiceScopeOpener,
    name: str,
    point: ExtensionPoint[Any],
    logger: BoundLogger,
) -> int:
    """Initialize one point, register its value and return how many hookimpls it has."""
    if point.provides in registry:
        error = ExtensionPointError(
            f"extension_point_provides_taken: capability {name!r} provides {point.provides.__name__}, already registered"
        )
        log_plugin_boot_failed(logger, plugin=name, phase=PHASE, error=error)
        raise error
    hooks = _hook_names(pm, point.specs)
    with svcs.Container(registry) as container:
        context = _Context(pm, name, hooks, _Resolver(container), service_scopes, logger)
        try:
            value = point.initialize(context)
        except Exception as error:
            if not context.hook_failed:
                log_plugin_boot_failed(logger, plugin=name, phase=PHASE, error=error)
            raise
        finally:
            context.close()
    registry.register_value(point.provides, value)
    logger.debug("extension_point_initialized", phase=PHASE, extension_point=name, plugins=sorted(context.contributors))
    return sum(len(getattr(pm.hook, hook).get_hookimpls()) for hook in hooks)


def _hook_names(pm: pluggy.PluginManager, specs: type) -> frozenset[str]:
    return frozenset(name for name in dir(specs) if pm.parse_hookspec_opts(specs, name) is not None)


class _Resolver:
    """The phase's resolver; it refuses every call once its ``initialize`` has returned."""

    def __init__(self, container: svcs.Container) -> None:
        self._container: svcs.Container | None = container

    def get[T](self, contract: type[T]) -> T:
        if self._container is None:
            raise ExtensionPointError("extension_point_closed: services resolve only during initialize")
        return self._container.get(contract)

    def close(self) -> None:
        self._container = None


class _Context:
    """The ``ExtensionPointContext`` one capability's ``initialize`` receives."""

    def __init__(
        self,
        pm: pluggy.PluginManager,
        name: str,
        hooks: frozenset[str],
        resolver: _Resolver,
        service_scopes: ServiceScopeOpener,
        logger: BoundLogger,
    ) -> None:
        self._pm = pm
        self._name = name
        self._hooks = hooks
        self._resolver = resolver
        self._service_scopes = service_scopes
        self._logger = logger
        self._closed = False
        self.hook_failed = False
        self.contributors: set[str] = set()

    @property
    def services(self) -> ServiceResolver:
        self._check_open()
        return self._resolver

    @property
    def service_scopes(self) -> ServiceScopeOpener:
        return self._service_scopes

    def collect(self, hook_name: str, /, **kwargs: object) -> Mapping[str, object]:
        self._check_open()
        if hook_name not in self._hooks:
            raise ExtensionPointError(f"extension_point_foreign_hook: capability {self._name!r} cannot collect {hook_name!r}")
        try:
            results = call_hook_per_plugin(self._pm, hook_name, self._logger, **kwargs)
        except Exception:
            self.hook_failed = True
            raise
        contributed = {plugin: values[0] for plugin, values in results.items() if values}
        self.contributors.update(contributed)
        return contributed

    def close(self) -> None:
        self._closed = True
        self._resolver.close()

    def _check_open(self) -> None:
        if self._closed:
            raise ExtensionPointError("extension_point_closed: collect only during initialize")

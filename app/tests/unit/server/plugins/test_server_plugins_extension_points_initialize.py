"""Unit tests for the lifespan extension-point phase (decisions/lifecycle.md phase 4).

Test capabilities and features are module-like plugins on a real pluggy manager with the
host hookspecs; a capability module is named under ``capabilities.`` as the entry point
targets it. Each test capability owns a hookspec class and declares one extension point
whose initialize collects that hook. The phase runs against a real svcs registry, and
structlog's ``capture_logs`` records the events. Assertions cover what a plugin author
and an operator observe: the value registered in the service registry, the order of
initialization, and the single CRITICAL ``plugin_boot_failed`` naming the plugin at
fault when the phase aborts boot.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import ModuleType

import pluggy
import pytest
import structlog
import svcs
from structlog.testing import capture_logs

from contracts.plugins.extension_points import ExtensionPoint, ExtensionPointContext, ExtensionPointRegistrar
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl, hookspec
from server.plugins.extension_points import ExtensionPointError, run_extension_points
from server.services import SvcsServiceScopeOpener

pytestmark = pytest.mark.unit


class AlphaSpecs:
    """The alpha test capability's extension point."""

    @hookspec
    def register_alpha_strategies(self) -> Sequence[str]:
        """Return the strategies a plugin contributes to alpha."""
        raise NotImplementedError


class BetaSpecs:
    """The beta test capability's extension point."""

    @hookspec
    def register_beta_strategies(self) -> Sequence[str]:
        """Return the strategies a plugin contributes to beta."""
        raise NotImplementedError


@dataclass(frozen=True)
class AlphaValue:
    strategies: Mapping[str, object]


@dataclass(frozen=True)
class BetaValue:
    strategies: Mapping[str, object]
    alpha: AlphaValue | None = None


@dataclass(frozen=True)
class Seed:
    label: str


def _module(name: str, **hookimpls: object) -> ModuleType:
    plugin = ModuleType(name)
    plugin.__dict__.update(hookimpls)
    return plugin


def _capability(name: str, *points: ExtensionPoint[object]) -> ModuleType:
    @hookimpl
    def register_extension_points(registrar: ExtensionPointRegistrar) -> None:
        for point in points:
            registrar.declare(point)

    return _module(f"capabilities.{name}.plugin", register_extension_points=register_extension_points)


def _alpha(
    initialize: Callable[[ExtensionPointContext], AlphaValue] | None = None, depends_on: tuple[str, ...] = ()
) -> ExtensionPoint[AlphaValue]:
    return ExtensionPoint(
        specs=AlphaSpecs,
        provides=AlphaValue,
        initialize=initialize or (lambda context: AlphaValue(context.collect("register_alpha_strategies"))),
        depends_on=depends_on,
    )


def _beta(
    initialize: Callable[[ExtensionPointContext], BetaValue] | None = None, depends_on: tuple[str, ...] = ()
) -> ExtensionPoint[BetaValue]:
    return ExtensionPoint(
        specs=BetaSpecs,
        provides=BetaValue,
        initialize=initialize or (lambda context: BetaValue(context.collect("register_beta_strategies"))),
        depends_on=depends_on,
    )


def _alpha_feature(*strategies: str) -> ModuleType:
    @hookimpl
    def register_alpha_strategies() -> list[str]:
        return list(strategies)

    return _module("features.fake_alpha_user", register_alpha_strategies=register_alpha_strategies)


def _manager(plugins: Mapping[str, ModuleType], blocked: Sequence[str] = ()) -> pluggy.PluginManager:
    pm = pluggy.PluginManager(PLUGIN_NAMESPACE)
    pm.add_hookspecs(FeatureLifecycleSpecs)
    for name in blocked:
        pm.set_blocked(name)
    for name, plugin in plugins.items():
        pm.register(plugin, name=name)
    return pm


@pytest.fixture
def registry() -> Iterator[svcs.Registry]:
    with svcs.Registry() as registry:
        yield registry


def _run(pm: pluggy.PluginManager, registry: svcs.Registry) -> None:
    run_extension_points(pm, registry, SvcsServiceScopeOpener(registry), structlog.stdlib.get_logger())


def _get[T](registry: svcs.Registry, contract: type[T]) -> T:
    with svcs.Container(registry) as container:
        return container.get(contract)


def _boot_failures(events: list[dict[str, object]]) -> list[tuple[object, object, object]]:
    return [(e["plugin"], e["phase"], e["error_type"]) for e in events if e["event"] == "plugin_boot_failed"]


def test_collected_strategies_are_registered_under_the_provided_type(registry: svcs.Registry) -> None:
    """The capability's value holds each contributing plugin's results by entry-point name and is in the registry."""
    pm = _manager({"alpha": _capability("alpha", _alpha()), "fake_user": _alpha_feature("one", "two")})

    _run(pm, registry)

    assert _get(registry, AlphaValue).strategies == {"fake_user": ["one", "two"]}


def test_initialize_runs_once_per_extension_point(registry: svcs.Registry) -> None:
    """Initialize is called exactly once, at startup."""
    calls: list[str] = []

    def initialize(context: ExtensionPointContext) -> AlphaValue:
        calls.append("alpha")
        return AlphaValue({})

    _run(_manager({"alpha": _capability("alpha", _alpha(initialize))}), registry)

    assert calls == ["alpha"]


def test_a_feature_cannot_declare_an_extension_point(registry: svcs.Registry) -> None:
    """Extension points belong to capabilities; a feature's declaration fails boot naming the feature."""

    @hookimpl
    def register_extension_points(registrar: ExtensionPointRegistrar) -> None:
        registrar.declare(_alpha())

    feature = _module("features.fake_feature", register_extension_points=register_extension_points)

    with capture_logs() as events, pytest.raises(ExtensionPointError, match="fake_feature"):
        _run(_manager({"fake_feature": feature}), registry)

    assert _boot_failures(events) == [("fake_feature", "register_extension_points", "ExtensionPointError")]


def test_a_capability_declares_at_most_one_extension_point(registry: svcs.Registry) -> None:
    """A second declaration from the same capability fails boot naming it."""
    pm = _manager({"alpha": _capability("alpha", _alpha(), _beta())})

    with capture_logs() as events, pytest.raises(ExtensionPointError, match="alpha"):
        _run(pm, registry)

    assert _boot_failures(events) == [("alpha", "register_extension_points", "ExtensionPointError")]


def test_a_hookimpl_whose_signature_does_not_match_fails_boot_naming_its_plugin(registry: svcs.Registry) -> None:
    """pluggy verifies the already-registered hookimpls when the spec class is added; the bad one is named."""

    @hookimpl
    def register_alpha_strategies(unknown_argument: object) -> list[str]:
        return []

    bad = _module("features.fake_bad", register_alpha_strategies=register_alpha_strategies)
    pm = _manager({"alpha": _capability("alpha", _alpha()), "fake_bad": bad})

    with capture_logs() as events, pytest.raises(pluggy.PluginValidationError):
        _run(pm, registry)

    assert _boot_failures(events) == [("fake_bad", "extension_points", "PluginValidationError")]


def test_extension_points_initialize_in_depends_on_order(registry: svcs.Registry) -> None:
    """A capability depending on another initializes after it, even when loaded first, and can read its value."""
    order: list[str] = []

    def alpha(context: ExtensionPointContext) -> AlphaValue:
        order.append("alpha")
        return AlphaValue({})

    def beta(context: ExtensionPointContext) -> BetaValue:
        order.append("beta")
        return BetaValue({}, alpha=context.services.get(AlphaValue))

    pm = _manager(
        {
            "beta": _capability("beta", _beta(beta, depends_on=("alpha",))),
            "alpha": _capability("alpha", _alpha(alpha)),
        }
    )

    _run(pm, registry)

    assert order == ["alpha", "beta"]
    assert _get(registry, BetaValue).alpha == AlphaValue({})


def test_independent_extension_points_initialize_in_plugin_load_order(registry: svcs.Registry) -> None:
    """Without dependencies the order is deterministic: the order the plugins were loaded."""
    with capture_logs() as events:
        _run(_manager({"beta": _capability("beta", _beta()), "alpha": _capability("alpha", _alpha())}), registry)

    (summary,) = [e for e in events if e["event"] == "extension_points_initialized"]
    assert summary["extension_points"] == ["beta", "alpha"]


def test_a_dependency_cycle_fails_boot_naming_the_capabilities(registry: svcs.Registry) -> None:
    """Two capabilities depending on each other cannot be ordered; boot stops naming both."""
    pm = _manager(
        {
            "alpha": _capability("alpha", _alpha(depends_on=("beta",))),
            "beta": _capability("beta", _beta(depends_on=("alpha",))),
        }
    )

    with capture_logs() as events, pytest.raises(ExtensionPointError, match=r"(?=.*alpha)(?=.*beta)"):
        _run(pm, registry)

    assert [(plugin, phase) for plugin, phase, _ in _boot_failures(events)] == [("alpha", "extension_points")]


def test_a_dependency_on_an_undeclared_extension_point_fails_boot_naming_both(registry: svcs.Registry) -> None:
    """Depending on a capability that declared no extension point (disabled or none) stops boot."""
    pm = _manager({"beta": _capability("beta", _beta(depends_on=("alpha",)))})

    with capture_logs() as events, pytest.raises(ExtensionPointError, match=r"(?=.*alpha)(?=.*beta)"):
        _run(pm, registry)

    assert _boot_failures(events) == [("beta", "extension_points", "ExtensionPointError")]


def test_a_provided_type_already_registered_fails_boot(registry: svcs.Registry) -> None:
    """Two values under one registry key would shadow each other; the second capability's boot fails."""
    duplicate = ExtensionPoint(specs=BetaSpecs, provides=AlphaValue, initialize=lambda context: AlphaValue({}))
    pm = _manager({"alpha": _capability("alpha", _alpha()), "beta": _capability("beta", duplicate)})

    with capture_logs() as events, pytest.raises(ExtensionPointError, match="AlphaValue"):
        _run(pm, registry)

    assert _boot_failures(events) == [("beta", "extension_points", "ExtensionPointError")]


def test_collect_refuses_a_hook_outside_the_capabilitys_own_spec_class(registry: svcs.Registry) -> None:
    """A capability collects only its own hooks, never a host hook or another capability's."""
    point = _alpha(lambda context: AlphaValue(context.collect("startup_warmup")))

    with capture_logs() as events, pytest.raises(ExtensionPointError, match="startup_warmup"):
        _run(_manager({"alpha": _capability("alpha", point)}), registry)

    assert _boot_failures(events) == [("alpha", "extension_points", "ExtensionPointError")]


def test_the_context_refuses_every_call_after_the_phase(registry: svcs.Registry) -> None:
    """A context kept past initialize cannot reach pluggy or the registry, so nothing is collected per request."""
    kept: list[ExtensionPointContext] = []

    def initialize(context: ExtensionPointContext) -> AlphaValue:
        kept.append(context)
        return AlphaValue({})

    _run(_manager({"alpha": _capability("alpha", _alpha(initialize))}), registry)

    (context,) = kept
    with pytest.raises(ExtensionPointError, match="closed"):
        context.collect("register_alpha_strategies")
    with pytest.raises(ExtensionPointError, match="closed"):
        context.services.get(AlphaValue)


def test_the_context_resolves_registered_values_and_hands_over_the_scope_opener(registry: svcs.Registry) -> None:
    """Values registered before the phase resolve during initialize; the opener is the host's."""
    registry.register_value(Seed, Seed("from-phase-3"))
    opener = SvcsServiceScopeOpener(registry)
    seen: dict[str, object] = {}

    def initialize(context: ExtensionPointContext) -> AlphaValue:
        seen["seed"] = context.services.get(Seed)
        seen["opener"] = context.service_scopes
        return AlphaValue({})

    run_extension_points(
        _manager({"alpha": _capability("alpha", _alpha(initialize))}), registry, opener, structlog.stdlib.get_logger()
    )

    assert seen == {"seed": Seed("from-phase-3"), "opener": opener}


def test_a_raising_hookimpl_is_attributed_to_its_own_plugin_once(registry: svcs.Registry) -> None:
    """A contributing feature that raises during collection is named, not the capability collecting from it."""

    @hookimpl
    def register_alpha_strategies() -> list[str]:
        raise LookupError("no such strategy")

    raising = _module("features.fake_raising", register_alpha_strategies=register_alpha_strategies)
    pm = _manager({"alpha": _capability("alpha", _alpha()), "fake_raising": raising})

    with capture_logs() as events, pytest.raises(LookupError):
        _run(pm, registry)

    assert _boot_failures(events) == [("fake_raising", "register_alpha_strategies", "LookupError")]


def test_a_raising_initialize_is_attributed_to_its_capability(registry: svcs.Registry) -> None:
    """A capability refusing its collection (for example an empty one it requires) stops boot naming it."""

    def initialize(context: ExtensionPointContext) -> AlphaValue:
        raise ValueError("alpha needs at least one strategy")

    with capture_logs() as events, pytest.raises(ValueError):
        _run(_manager({"alpha": _capability("alpha", _alpha(initialize))}), registry)

    assert _boot_failures(events) == [("alpha", "extension_points", "ValueError")]
    assert "at least one" not in repr(events)


def test_a_disabled_capability_is_never_declared_or_collected(registry: svcs.Registry) -> None:
    """A blocked capability registers nothing; a feature's hookimpl into it stays uncalled and boot continues."""
    called: list[str] = []

    @hookimpl
    def register_alpha_strategies() -> list[str]:
        called.append("feature")
        return []

    feature = _module("features.fake_optional_user", register_alpha_strategies=register_alpha_strategies)
    pm = _manager({"alpha": _capability("alpha", _alpha()), "fake_user": feature}, blocked=["alpha"])

    with capture_logs() as events:
        _run(pm, registry)

    assert called == []
    assert AlphaValue not in registry
    (summary,) = [e for e in events if e["event"] == "extension_points_initialized"]
    assert (summary["extension_points"], summary["implementation_count"]) == ([], 0)


def test_the_phase_logs_one_info_event_with_its_counts(registry: svcs.Registry) -> None:
    """One INFO event names the points in order and counts the hookimpls into them; per-point detail is debug."""
    pm = _manager({"alpha": _capability("alpha", _alpha()), "fake_user": _alpha_feature("one", "two")})

    with capture_logs() as events:
        _run(pm, registry)

    info = [e for e in events if e["log_level"] == "info"]
    assert [(e["event"], e["phase"], e["extension_points"], e["implementation_count"]) for e in info] == [
        ("extension_points_initialized", "extension_points", ["alpha"], 1)
    ]
    (detail,) = [e for e in events if e["event"] == "extension_point_initialized"]
    assert (detail["log_level"], detail["extension_point"], detail["plugins"]) == ("debug", "alpha", ["fake_user"])

"""Unit tests for the translation resource registrar Protocol in contracts.i18n.

A Protocol-conformant fake registrar stands in for the infrastructure registry:
a feature hookimpl is called with it and the recorded spec is asserted, so a
feature written against the contract works with any implementation. The
concrete infrastructure registry is assigned to the Protocol type (checked
statically by mypy) and driven through it to show it implements the contract.
"""

import inspect

import pytest

from contracts.i18n.resources import I18nResourceRegistrar, I18nResourceSpec
from infrastructure.i18n.resources import I18nResourceRegistry
from packages.geolocate import register_i18n_resources

pytestmark = pytest.mark.unit


class _FakeRegistrar:
    """Records every spec it receives."""

    def __init__(self) -> None:
        self.specs: list[I18nResourceSpec] = []

    def register(self, spec: I18nResourceSpec) -> None:
        self.specs.append(spec)


def test_registrar_register_takes_a_single_spec() -> None:
    params = inspect.signature(I18nResourceRegistrar.register).parameters

    assert list(params) == ["self", "spec"]


def test_hookimpl_registers_its_resources_through_a_fake_registrar() -> None:
    fake = _FakeRegistrar()
    registrar: I18nResourceRegistrar = fake

    register_i18n_resources(registrar)

    assert [(spec.owner, spec.domain, spec.required) for spec in fake.specs] == [("packages.geolocate", "geolocate", False)]


def test_infrastructure_registry_implements_the_registrar_protocol() -> None:
    registry = I18nResourceRegistry()
    registrar: I18nResourceRegistrar = registry
    spec = I18nResourceSpec(owner="packages.test", path="/test/locales")

    registrar.register(spec)

    assert registry.list_specs() == [spec]

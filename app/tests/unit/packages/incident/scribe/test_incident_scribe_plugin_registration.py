"""Unit tests for the incident scribe subdomain's plugin registration: one package, two commands, two catalogues."""

from pathlib import Path

import pytest

import packages.incident.scribe as scribe_pkg
from infrastructure.i18n.loader import YAMLTranslationLoader
from infrastructure.i18n.resources import I18nResourceRegistry
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit


def test_one_hookimpl_registers_both_commands_under_sre_incident() -> None:
    """The package's single Slack hookimpl registers ``draft``, ``summarize`` and ``status-update``, all children of ``sre.incident``.

    A recording fake registrar stands in for the Slack provider, so the
    assertion is on what the hookimpl asked to be registered.
    """
    registrar = FakeSlackRegistrar()

    scribe_pkg.register_slack_commands(registrar=registrar)

    registered = {(command["parent"], command["command"]) for command in registrar.commands}
    assert registered == {("sre.incident", "draft"), ("sre.incident", "summarize"), ("sre.incident", "status-update")}


def test_one_i18n_registration_covers_both_catalogues() -> None:
    """The package registers its ``locales`` directory once, owned by the subdomain.

    The real registry is used because it keys resources on their path: a second
    registration of the same directory would be skipped, so one is all there is.
    """
    registry = I18nResourceRegistry()

    scribe_pkg.register_i18n_resources(registry=registry)

    (spec,) = registry.list_specs()
    assert spec.owner == "packages.incident.scribe"
    assert Path(spec.path) == Path(scribe_pkg.__file__).parent / "locales"


def test_registered_locales_path_loads_both_i18n_domains_in_every_locale() -> None:
    """Loading the registered path yields the ``incident_draft``, ``incident_summary`` and ``incident_status_update`` domains in each locale.

    The catalogues are read with the production YAML loader from the path the
    package registered, which is what startup does with the collected specs.
    """
    registry = I18nResourceRegistry()
    scribe_pkg.register_i18n_resources(registry=registry)
    (spec,) = registry.list_specs()

    catalogs = YAMLTranslationLoader(Path(spec.path), use_cache=False).load_all()

    assert {locale.value for locale in catalogs} == {"en-US", "fr-FR"}
    for catalog in catalogs.values():
        assert {"incident_draft", "incident_summary", "incident_status_update"} <= set(catalog.messages)

"""Unit tests for the incident comms subdomain's plugin registration: one package, one command, the modal's listeners, one catalogue."""

from importlib.metadata import entry_points
from pathlib import Path

import pytest

import features.incident.comms as comms_pkg
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from features.incident.comms.entrypoints.slack import handle_review_submission
from features.incident.comms.entrypoints.slack_views import REVIEW_CALLBACK_ID
from infrastructure.i18n.loader import YAMLTranslationLoader
from infrastructure.i18n.resources import I18nResourceRegistry
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit


def test_entry_point_targets_the_comms_package_under_features() -> None:
    """The ``incident.comms`` entry point in the ``sre_bot`` group resolves to ``features.incident.comms``.

    The installed distribution metadata is read, which is what boot does when
    it loads plugins, so a stale entry-point target fails here rather than at
    startup.
    """
    (entry_point,) = [ep for ep in entry_points(group=PLUGIN_NAMESPACE) if ep.name == "incident.comms"]

    assert entry_point.value == "features.incident.comms"
    assert entry_point.load() is comms_pkg


def test_one_hookimpl_registers_the_status_update_command_under_sre_incident() -> None:
    """The package's single Slack hookimpl registers ``status-update`` as a child of ``sre.incident``, and nothing else.

    A recording fake registrar stands in for the Slack provider, so the
    assertion is on what the hookimpl asked to be registered.
    """
    registrar = FakeSlackRegistrar()

    comms_pkg.register_slack_commands(registrar=registrar)

    registered = [(command["parent"], command["command"]) for command in registrar.commands]
    assert registered == [("sre.incident", "status-update")]


def test_block_actions_are_the_status_update_buttons_with_the_plugin_prefix() -> None:
    """The package registers exactly the modal's seven buttons, each once, under ``incident.comms.status_update``."""
    registrar = FakeSlackRegistrar()

    comms_pkg.register_slack_commands(registrar=registrar)

    assert sorted(registrar.block_actions) == [
        f"incident.comms.status_update.{suffix}"
        for suffix in ("generate", "history", "new", "open", "published", "review", "save")
    ]


def test_hookimpl_registers_the_approval_submission_with_the_command() -> None:
    """One hookimpl call registers the approval view submission beside the ``status-update`` command.

    Both come from the comms Slack entry point's single ``register``, so the
    command that opens the modal never ships without the listener that
    approves from it.
    """
    registrar = FakeSlackRegistrar()

    comms_pkg.register_slack_commands(registrar=registrar)

    assert REVIEW_CALLBACK_ID == "incident.comms.status_update.approve"
    assert registrar.view_submissions == {REVIEW_CALLBACK_ID: handle_review_submission}


def test_registered_locales_path_loads_the_status_update_domain_in_every_locale() -> None:
    """The package registers its ``locales`` directory once; loading it yields only ``incident_status_update`` per locale.

    The real registry and the production YAML loader are used, which is what
    startup does with the collected specs.
    """
    registry = I18nResourceRegistry()
    comms_pkg.register_i18n_resources(registry=registry)
    (spec,) = registry.list_specs()

    catalogs = YAMLTranslationLoader(Path(spec.path), use_cache=False).load_all()

    assert spec.owner == "features.incident.comms"
    assert Path(spec.path) == Path(comms_pkg.__file__).parent / "locales"
    assert {locale.value for locale in catalogs} == {"en-US", "fr-FR"}
    for catalog in catalogs.values():
        assert set(catalog.messages) == {"incident_status_update"}

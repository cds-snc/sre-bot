"""Unit tests for the service scope opener that PluginSlackRegistrar exposes.

The host registrar is a FakeSlackRegistrar and the opener is a bare MagicMock,
since the plugin registrar only forwards it. The plugin registrar must hand back
the host's own object, and must not supply a default when the host has none.
"""

from unittest.mock import MagicMock

import pytest

from server.plugins.slack_registrar import PluginSlackRegistrar
from tests.factories.slack import FakeSlackRegistrar

pytestmark = pytest.mark.unit


def test_plugin_registrar_exposes_the_host_opener_by_identity() -> None:
    """The plugin registrar's service_scopes is the object the host registrar was given.

    Stub strategy: a MagicMock stands in for the opener, and FakeSlackRegistrar
    is constructed with it.
    Assertion rationale: identity shows the plugin registrar neither wraps nor
    copies the opener, so every plugin and the host share one opener.
    """
    opener = MagicMock(name="scope_opener")
    registrar = PluginSlackRegistrar(FakeSlackRegistrar(service_scopes=opener), "demo.feature")

    assert registrar.service_scopes is opener


def test_plugin_registrar_raises_when_the_host_registrar_has_no_opener() -> None:
    """A plugin that reads service_scopes from a host without one gets RuntimeError, not a default.

    Stub strategy: FakeSlackRegistrar built without an opener, which is the
    state a host is in before it injects one.
    Assertion rationale: the error type matches the provider's, so a missing
    injection surfaces at the first use instead of as a silent fallback.
    """
    registrar = PluginSlackRegistrar(FakeSlackRegistrar(), "demo.feature")

    with pytest.raises(RuntimeError):
        _ = registrar.service_scopes

"""Unit tests for the service scope opener the host injects into SlackPlatformProvider.

The provider has no default opener: a feature that reads service_scopes before the host
injects one gets a RuntimeError rather than a silent fallback. The opener is a
MagicMock because the provider only stores it and returns it.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from integrations.slack.provider import SlackPlatformProvider

pytestmark = pytest.mark.unit


def _provider() -> SlackPlatformProvider:
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    return SlackPlatformProvider(settings=settings)


def test_scopes_raises_before_the_host_injects_an_opener() -> None:
    """Reading service_scopes on a provider that has not been given an opener raises RuntimeError.

    Stub strategy: a freshly constructed provider with no injection.
    Assertion rationale: the error is raised on read, so a feature that depends
    on the opener fails at its first use and not later at invocation time.
    """
    provider = _provider()

    with pytest.raises(RuntimeError):
        _ = provider.service_scopes


def test_scopes_returns_the_opener_the_host_injected() -> None:
    """After set_scope_opener, service_scopes returns that same object.

    Stub strategy: a MagicMock stands in for the host's opener.
    Assertion rationale: identity shows the provider stores the host's opener and
    does not wrap it, so every registrar hands out the same opener.
    """
    provider = _provider()
    opener = MagicMock(name="scope_opener")

    provider.set_scope_opener(opener)

    assert provider.service_scopes is opener

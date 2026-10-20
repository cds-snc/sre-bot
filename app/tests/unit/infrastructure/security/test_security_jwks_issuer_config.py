"""Tests for how JWKS resolves its issuers from the security settings slice.

get_security_settings is patched in the jwks module with a real SecuritySettings
built without the .env file, so the issuers come only from the test. The JWKS
manager singleton is cleared around each test because it caches the issuers it
was built with. The module logger is patched to assert the warning's context.
"""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from infrastructure.security.jwks import get_issuer_config, get_jwks_manager
from infrastructure.security.settings import SecuritySettings

pytestmark = pytest.mark.unit

_ISSUER = {
    "issuer-1": {
        "jwks_uri": "https://issuer.example.com/.well-known/jwks.json",
        "algorithms": ["RS256"],
        "audience": "aud-1",
    }
}


@pytest.fixture(autouse=True)
def _fresh_jwks_manager() -> Iterator[None]:
    """Clear the cached JWKS manager so each test builds it from its own settings."""
    get_jwks_manager.cache_clear()
    yield
    get_jwks_manager.cache_clear()


def test_get_issuer_config_returns_the_security_slice_issuers() -> None:
    """The issuers come from SecuritySettings.ISSUER_CONFIG."""
    settings = SecuritySettings(_env_file=None, ISSUER_CONFIG=_ISSUER)

    with patch("infrastructure.security.jwks.get_security_settings", return_value=settings):
        assert get_issuer_config() == _ISSUER


@patch("infrastructure.security.jwks.logger")
def test_get_issuer_config_warns_naming_the_key_when_unset(mock_logger: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
    """With no issuers configured the result is empty and the warning names the key and operation."""
    monkeypatch.delenv("ISSUER_CONFIG", raising=False)
    settings = SecuritySettings(_env_file=None)

    with patch("infrastructure.security.jwks.get_security_settings", return_value=settings):
        assert get_issuer_config() == {}

    mock_logger.bind.assert_called_once_with(key="ISSUER_CONFIG", operation="get_issuer_config")
    mock_logger.bind.return_value.warning.assert_called_once()
    assert mock_logger.bind.return_value.warning.call_args.args[0] == "issuer_config_not_set"


def test_get_jwks_manager_is_built_from_the_security_slice() -> None:
    """The JWKS manager singleton holds the security slice's issuers."""
    settings = SecuritySettings(_env_file=None, ISSUER_CONFIG=_ISSUER)

    with patch("infrastructure.security.jwks.get_security_settings", return_value=settings):
        manager = get_jwks_manager()

    assert manager.issuer_config == _ISSUER

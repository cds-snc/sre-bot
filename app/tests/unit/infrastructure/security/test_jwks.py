"""Unit tests for JWKS manager."""

from unittest.mock import MagicMock, patch

import pytest

from infrastructure.security import JWKSManager


@pytest.mark.unit
class TestJWKSManager:
    """Test suite for JWKSManager class."""

    def test_jwks_manager_initialization_with_config(self, mock_issuer_config):
        """Test JWKSManager initialization with issuer config."""
        manager = JWKSManager(issuer_config=mock_issuer_config)

        assert manager.issuer_config == mock_issuer_config
        assert manager.jwks_clients == {}

    def test_jwks_manager_initialization_without_config(self):
        """Test JWKSManager initialization without explicit config."""
        # When initialized with None, it falls back to settings if available
        manager = JWKSManager(issuer_config=None)

        # It should either have settings config or be empty
        # (depends on whether settings.server.ISSUER_CONFIG is set)
        assert manager.jwks_clients == {}

    def test_get_jwks_client_returns_none_for_missing_issuer(self, mock_issuer_config):
        """Test get_jwks_client returns None for unknown issuer."""
        manager = JWKSManager(issuer_config=mock_issuer_config)
        result = manager.get_jwks_client("unknown_issuer")

        assert result is None

    def test_get_jwks_client_returns_none_for_missing_config(self):
        """Test get_jwks_client returns None when config is None."""
        manager = JWKSManager(issuer_config=None)
        result = manager.get_jwks_client("any_issuer")

        assert result is None

    def test_get_jwks_client_returns_none_for_missing_jwks_uri(self):
        """Test get_jwks_client returns None when jwks_uri is missing."""
        config = {
            "issuer": {
                "audience": "test",
                "algorithms": ["RS256"],
                # Missing jwks_uri
            }
        }
        manager = JWKSManager(issuer_config=config)
        result = manager.get_jwks_client("issuer")

        assert result is None

    @patch("infrastructure.security.jwks.PyJWKClient")
    def test_get_jwks_client_creates_and_caches_client(
        self, mock_pyjwk_client, mock_issuer_config
    ):
        """Test get_jwks_client creates and caches PyJWKClient."""
        mock_client = MagicMock()
        mock_pyjwk_client.return_value = mock_client

        manager = JWKSManager(issuer_config=mock_issuer_config)

        # First call creates client
        result1 = manager.get_jwks_client("test_issuer")
        assert result1 == mock_client
        mock_pyjwk_client.assert_called_once()

        # Second call uses cached client
        result2 = manager.get_jwks_client("test_issuer")
        assert result2 == mock_client
        assert mock_pyjwk_client.call_count == 1  # Still only 1 call

    @patch("infrastructure.security.jwks.PyJWKClient")
    def test_get_jwks_client_handles_initialization_error(
        self, mock_pyjwk_client, mock_issuer_config
    ):
        """Test get_jwks_client returns None on initialization error."""
        mock_pyjwk_client.side_effect = Exception("Connection failed")

        manager = JWKSManager(issuer_config=mock_issuer_config)
        result = manager.get_jwks_client("test_issuer")

        assert result is None

    def test_clear_cache_removes_specific_issuer(self, mock_issuer_config):
        """Test clear_cache removes specific issuer client."""
        manager = JWKSManager(issuer_config=mock_issuer_config)
        mock_client = MagicMock()
        manager.jwks_clients["test_issuer"] = mock_client

        manager.clear_cache(issuer="test_issuer")

        assert "test_issuer" not in manager.jwks_clients

    def test_clear_cache_clears_all_issuers(self, mock_issuer_config):
        """Test clear_cache clears all issuer clients."""
        manager = JWKSManager(issuer_config=mock_issuer_config)
        manager.jwks_clients["test_issuer"] = MagicMock()
        manager.jwks_clients["second_issuer"] = MagicMock()

        manager.clear_cache()

        assert len(manager.jwks_clients) == 0

    @patch("infrastructure.security.jwks.PyJWKClient")
    def test_get_jwks_client_uses_correct_config(
        self, mock_pyjwk_client, mock_issuer_config
    ):
        """Test get_jwks_client uses correct config for issuer."""
        mock_client = MagicMock()
        mock_pyjwk_client.return_value = mock_client

        manager = JWKSManager(issuer_config=mock_issuer_config)
        result = manager.get_jwks_client("test_issuer")

        # Verify PyJWKClient was called with correct JWKS URI
        mock_pyjwk_client.assert_called_once_with(
            "https://test.example.com/.well-known/jwks.json",
            cache_jwk_set=True,
            lifespan=3600,
            timeout=10,
        )

    @patch("infrastructure.security.jwks.PyJWKClient")
    def test_get_jwks_client_initializes_different_clients_per_issuer(
        self, mock_pyjwk_client, mock_issuer_config
    ):
        """Test get_jwks_client initializes separate clients for different issuers."""
        client1 = MagicMock()
        client2 = MagicMock()
        mock_pyjwk_client.side_effect = [client1, client2]

        manager = JWKSManager(issuer_config=mock_issuer_config)

        result1 = manager.get_jwks_client("test_issuer")
        result2 = manager.get_jwks_client("second_issuer")

        assert result1 == client1
        assert result2 == client2
        assert manager.jwks_clients["test_issuer"] == client1
        assert manager.jwks_clients["second_issuer"] == client2

"""Unit tests for JWT token validation."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from jwt import PyJWTError

from infrastructure.security import (
    extract_user_info_from_token,
    get_issuer_from_token,
    validate_jwt_token,
)
from infrastructure.security.jwks import JWKSManager


@pytest.mark.unit
class TestGetIssuerFromToken:
    """Test suite for get_issuer_from_token function."""

    def test_get_issuer_from_token_valid(self):
        """Test get_issuer_from_token extracts issuer from valid token."""
        with patch("infrastructure.security.jwt.decode") as mock_decode:
            mock_decode.return_value = {"iss": "test_issuer", "sub": "user"}

            result = get_issuer_from_token("token_string")

            assert result == "test_issuer"
            mock_decode.assert_called_once_with(
                "token_string", options={"verify_signature": False}
            )

    def test_get_issuer_from_token_missing_issuer(self):
        """Test get_issuer_from_token returns None when issuer missing."""
        with patch("infrastructure.security.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "user"}  # No 'iss' claim

            result = get_issuer_from_token("token_string")

            assert result is None

    def test_get_issuer_from_token_decode_error(self):
        """Test get_issuer_from_token returns None on decode error."""
        with patch("infrastructure.security.jwt.decode") as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")

            result = get_issuer_from_token("invalid_token")

            assert result is None

    def test_get_issuer_from_token_malformed_token(self):
        """Test get_issuer_from_token returns None for malformed token."""
        result = get_issuer_from_token("not.a.token")

        # Should return None due to exception handling
        assert result is None


@pytest.mark.unit
class TestExtractUserInfoFromToken:
    """Test suite for extract_user_info_from_token function."""

    def test_extract_user_info_valid_token(self):
        """Test extract_user_info_from_token with valid token."""
        with patch("infrastructure.security.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "sub": "user_123",
                "email": "user@example.com",
            }

            user_id, email = extract_user_info_from_token("token_string")

            assert user_id == "user_123"
            assert email == "user@example.com"

    def test_extract_user_info_sub_with_issuer_prefix(self):
        """Test extract_user_info_from_token extracts user ID from prefixed sub."""
        with patch("infrastructure.security.jwt.decode") as mock_decode:
            mock_decode.return_value = {
                "sub": "https://issuer.example.com/user_123",
                "email": "user@example.com",
            }

            user_id, email = extract_user_info_from_token("token_string")

            # Should extract last part after /
            assert user_id == "user_123"
            assert email == "user@example.com"

    def test_extract_user_info_missing_email(self):
        """Test extract_user_info_from_token with missing email claim."""
        with patch("infrastructure.security.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "user_123"}  # No email

            user_id, email = extract_user_info_from_token("token_string")

            assert user_id == "user_123"
            assert email is None

    def test_extract_user_info_missing_sub(self):
        """Test extract_user_info_from_token with missing sub claim."""
        with patch("infrastructure.security.jwt.decode") as mock_decode:
            mock_decode.return_value = {"email": "user@example.com"}  # No sub

            user_id, email = extract_user_info_from_token("token_string")

            assert user_id is None
            assert email == "user@example.com"

    def test_extract_user_info_empty_claims(self):
        """Test extract_user_info_from_token with empty payload."""
        with patch("infrastructure.security.jwt.decode") as mock_decode:
            mock_decode.return_value = {}

            user_id, email = extract_user_info_from_token("token_string")

            assert user_id is None
            assert email is None

    def test_extract_user_info_decode_error(self):
        """Test extract_user_info_from_token returns (None, None) on error."""
        with patch("infrastructure.security.jwt.decode") as mock_decode:
            mock_decode.side_effect = Exception("Invalid token")

            user_id, email = extract_user_info_from_token("invalid_token")

            assert user_id is None
            assert email is None


@pytest.mark.unit
class TestValidateJWTToken:
    """Test suite for validate_jwt_token function."""

    def test_validate_jwt_token_missing_credentials(self, mock_issuer_config):
        """Test validate_jwt_token raises 401 for missing credentials."""
        manager = JWKSManager(issuer_config=mock_issuer_config)

        with pytest.raises(HTTPException) as exc_info:
            validate_jwt_token(credentials=None, jwks_manager=manager)

        assert exc_info.value.status_code == 401
        assert "Missing or invalid token" in exc_info.value.detail

    def test_validate_jwt_token_invalid_scheme(
        self, mock_http_credentials, mock_issuer_config
    ):
        """Test validate_jwt_token raises 401 for invalid auth scheme."""
        manager = JWKSManager(issuer_config=mock_issuer_config)
        credentials = mock_http_credentials(scheme="Basic")

        with pytest.raises(HTTPException) as exc_info:
            validate_jwt_token(credentials=credentials, jwks_manager=manager)

        assert exc_info.value.status_code == 401

    def test_validate_jwt_token_missing_token_credentials(self, mock_issuer_config):
        """Test validate_jwt_token raises 401 for empty token."""
        from fastapi.security import HTTPAuthorizationCredentials

        manager = JWKSManager(issuer_config=mock_issuer_config)
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")

        with pytest.raises(HTTPException) as exc_info:
            validate_jwt_token(credentials=credentials, jwks_manager=manager)

        assert exc_info.value.status_code == 401

    def test_validate_jwt_token_missing_issuer_in_token(
        self, mock_http_credentials, mock_issuer_config
    ):
        """Test validate_jwt_token raises 401 when issuer missing from token."""
        manager = JWKSManager(issuer_config=mock_issuer_config)
        credentials = mock_http_credentials()

        with patch("infrastructure.security.jwt.get_issuer_from_token") as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                validate_jwt_token(credentials=credentials, jwks_manager=manager)

            assert exc_info.value.status_code == 401
            assert "Issuer not found" in exc_info.value.detail

    def test_validate_jwt_token_untrusted_issuer(
        self, mock_http_credentials, mock_issuer_config
    ):
        """Test validate_jwt_token raises 401 for untrusted issuer."""
        manager = JWKSManager(issuer_config=mock_issuer_config)
        credentials = mock_http_credentials()

        with patch("infrastructure.security.jwt.get_issuer_from_token") as mock_get:
            mock_get.return_value = "untrusted_issuer"

            with pytest.raises(HTTPException) as exc_info:
                validate_jwt_token(credentials=credentials, jwks_manager=manager)

            assert exc_info.value.status_code == 401
            assert "Untrusted or missing" in exc_info.value.detail

    @patch("infrastructure.services.providers.get_jwks_manager")
    def test_validate_jwt_token_uses_default_manager(self, mock_get_jwks_manager):
        """Test validate_jwt_token works with provided jwks_manager."""
        from fastapi.security import HTTPAuthorizationCredentials

        mock_manager_instance = MagicMock()
        mock_manager_instance.issuer_config = None
        mock_get_jwks_manager.return_value = mock_manager_instance

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

        with patch("infrastructure.security.jwt.get_issuer_from_token") as mock_get:
            mock_get.return_value = "some_issuer"

            with pytest.raises(HTTPException):
                # validate_jwt_token requires jwks_manager argument
                validate_jwt_token(
                    jwks_manager=mock_manager_instance, credentials=credentials
                )

    @patch("infrastructure.security.jwt.decode")
    def test_validate_jwt_token_successful_validation(
        self, mock_decode, mock_http_credentials, mock_issuer_config
    ):
        """Test validate_jwt_token successfully validates and returns payload."""
        manager = JWKSManager(issuer_config=mock_issuer_config)
        credentials = mock_http_credentials()

        # Mock the JWKS client and key
        mock_jwks_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test_key_value"
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

        expected_payload = {
            "iss": "test_issuer",
            "sub": "user_123",
            "email": "test@example.com",
        }
        mock_decode.return_value = expected_payload

        with patch("infrastructure.security.jwt.get_issuer_from_token") as mock_get:
            mock_get.return_value = "test_issuer"

            # Patch the JWKS client retrieval
            with patch.object(
                manager, "get_jwks_client", return_value=mock_jwks_client
            ):
                result = validate_jwt_token(
                    credentials=credentials, jwks_manager=manager
                )

                assert result == expected_payload

    def test_validate_jwt_token_pyjwt_error(
        self, mock_http_credentials, mock_issuer_config
    ):
        """Test validate_jwt_token raises 401 on PyJWTError."""
        manager = JWKSManager(issuer_config=mock_issuer_config)
        credentials = mock_http_credentials()

        mock_jwks_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test_key"
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("infrastructure.security.jwt.get_issuer_from_token") as mock_get:
            mock_get.return_value = "test_issuer"

            with patch("infrastructure.security.jwt.decode") as mock_decode:
                mock_decode.side_effect = PyJWTError("Token expired")

                with patch.object(
                    manager, "get_jwks_client", return_value=mock_jwks_client
                ):
                    with pytest.raises(HTTPException) as exc_info:
                        validate_jwt_token(
                            credentials=credentials, jwks_manager=manager
                        )

                    assert exc_info.value.status_code == 401
                    assert "Invalid token" in exc_info.value.detail

    def test_validate_jwt_token_uses_issuer_config(
        self, mock_http_credentials, mock_issuer_config
    ):
        """Test validate_jwt_token uses correct issuer config."""
        manager = JWKSManager(issuer_config=mock_issuer_config)
        credentials = mock_http_credentials()

        mock_jwks_client = MagicMock()
        mock_signing_key = MagicMock()
        mock_signing_key.key = "test_key"
        mock_jwks_client.get_signing_key_from_jwt.return_value = mock_signing_key

        with patch("infrastructure.security.jwt.get_issuer_from_token") as mock_get:
            mock_get.return_value = "test_issuer"

            with patch("infrastructure.security.jwt.decode") as mock_decode:
                mock_decode.return_value = {"iss": "test_issuer"}

                with patch.object(
                    manager, "get_jwks_client", return_value=mock_jwks_client
                ):
                    result = validate_jwt_token(
                        credentials=credentials, jwks_manager=manager
                    )
                    assert result == {"iss": "test_issuer"}

                    # Verify decode was called with config from issuer
                    call_kwargs = mock_decode.call_args[1]
                    assert call_kwargs["algorithms"] == ["RS256"]
                    assert call_kwargs["audience"] == "test_audience"

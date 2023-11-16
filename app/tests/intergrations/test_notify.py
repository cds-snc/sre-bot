import jwt
import os
from integrations import notify
from unittest.mock import patch

# helper function to decode the token for testing


def decode_token(token, secret):
    return jwt.decode(token, key=secret, options={"verify_signature": True}, algorithms=["HS256"])


@patch("integrations.notify.create_jwt_token")
def test_create_jwt_token_secret_missing(jwt_token_mock):
    assert notify.create_jwt_token(secret=None, client_id="client_id") == "Missing secret key"
    jwt_token_mock.assert_called_once_with(secret=None, client_id="client_id")


@patch("integrations.notify.create_jwt_token")
def test_create_jwt_token_client_id_missing(jwt_token_mock):
    assert notify.create_jwt_token(secret="secret", client_id=None) == "Missing client id"
    jwt_token_mock.assert_called_once_with(secret="secret", client_id=None)


@patch("integrations.notify.create_jwt_token")
def test_create_jwt_token_contains_correct_headers(jwt_token_mock):
    token = notify.create_jwt_token(secret="secret", client_id="client_id")
    assert jwt_token_mock.called_once_with(secret="secret", client_id="client_id")
    headers = jwt.get_unverified_header(token)
    assert headers["typ"] == "JWT"
    assert headers["alg"] == "HS256"


@patch("integrations.notify.create_jwt_token")
def test_create_jwt_token_contains_correct_headers(jwt_token_mock):
    token = notify.create_jwt_token(secret="secret", client_id="client_id")
    decoded_token = decode_token(token, "secret")
    assert decoded_token["iss"] == "client_id"
    assert "iat" in decoded_token
    assert "req" not in decoded_token
    assert "pay" not in decoded_token


@freeze_time("2020-01-01 00:00:00")
@patch("integrations.notify.create_jwt_token")
def test_token_contains_correct_iat(jwt_token_mock):
    token = notify.create_jwt_token(secret="secret", client_id="client_id")
    decoded_token = decode_token(token, "secret")
    assert decoded_token["iat"] == 1577836800


@patch.dict(
    os.environ, {"SRE_USER_NAME": None, "SRE_CLIENT_SECRET": "foo"}, clear=True
)
@patch("integrations.notify.create_authorization_header")
def test_authorization_header_missing_client_id(header_mock):
    assert notify.create_authorization_header() == "SRE_USER_NAME or SRE_CLIENT_SECRET is missing"
    header_mock.assert_called_once()


@patch.dict(
    os.environ, {"SRE_USER_NAME": "foo", "SRE_CLIENT_SECRET": None}, clear=True
)
@patch("integrations.notify.create_authorization_header")
def test_authorization_header_missing_secret(header_mock):
    assert notify.create_authorization_header() == "SRE_USER_NAME or SRE_CLIENT_SECRET is missing"
    header_mock.assert_called_once()


@patch("integrations.notify.create_jwt_token")
@patch("integrations.notify.create_authorization_header")
def test_successful_creation_of_header(self, mock_header, mock_jwt_token):
    mock_jwt_token.return_value = "mocked_jwt_token"
    header_key, header_value = notify.create_authorization_header()

    # Check if the JWT token function was called with the right arguments
    mock_jwt_token.assert_called_with(secret="test_secret", client_id="test_user")

    # Assert the function returns the correct format of the authorization header
    self.assertEqual(header_key, "Authorization")
    self.assertEqual(header_value, "Bearer mocked_jwt_token")


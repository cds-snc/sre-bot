import jwt
import os
import pytest
from integrations import notify
from unittest.mock import patch
from freezegun import freeze_time


# helper function to decode the token for testing
def decode_token(token, secret):
    return jwt.decode(
        token, key=secret, options={"verify_signature": True}, algorithms=["HS256"]
    )


# Test that an exception is raised if the secret is missing
def test_create_jwt_token_secret_missing():
    with pytest.raises(AssertionError) as err:
        notify.create_jwt_token(None, "client_id")
    assert str(err.value) == "Missing secret key"


# Test that an exception is raised if the client_id is missing
def test_create_jwt_token_client_id_missing():
    with pytest.raises(AssertionError) as err:
        notify.create_jwt_token("secret", None)
    assert str(err.value) == "Missing client id"


# Test that the token is created correctly and the type and alg headers are set correctly
def test_create_jwt_token_contains_correct_headers():
    token = notify.create_jwt_token("secret", "client_id")
    headers = jwt.get_unverified_header(token)
    assert headers["typ"] == "JWT"
    assert headers["alg"] == "HS256"


# Test that the claims headers are set correctly
def test_create_jwt_token_contains_correct_claims_headers():
    token = notify.create_jwt_token("secret", "client_id")
    decoded_token = decode_token(token, "secret")
    assert decoded_token["iss"] == "client_id"
    assert "iat" in decoded_token
    assert "req" not in decoded_token
    assert "pay" not in decoded_token


# Test that the correct iat time in epoch seconds is set correctly
@freeze_time("2020-01-01 00:00:00")
def test_token_contains_correct_iat():
    token = notify.create_jwt_token("secret", "client_id")
    decoded_token = decode_token(token, "secret")
    assert decoded_token["iat"] == 1577836800


# Test that an assertion error is raised if the NOTIFY_SRE_USER_NAME is missing
@patch.dict(os.environ, {"NOTIFY_SRE_USER_NAME": "", "NOTIFY_SRE_CLIENT_SECRET": "foo"})
@patch("integrations.notify.create_jwt_token")
def test_authorization_header_missing_client_id(jwt_token_mock):
    with pytest.raises(AssertionError) as err:
        notify.create_authorization_header()
    assert str(err.value) == "NOTIFY_SRE_USER_NAME is missing"


# Test that an assertion error is raised if the NOTIFY_SRE_CLIENT_SECRET is missing
@patch.dict(os.environ, {"NOTIFY_SRE_USER_NAME": "foo", "NOTIFY_SRE_CLIENT_SECRET": ""})
@patch("integrations.notify.create_jwt_token")
def test_authorization_header_missing_secret(jwt_token_mock):
    with pytest.raises(AssertionError) as err:
        notify.create_authorization_header()
    assert str(err.value) == "NOTIFY_SRE_CLIENT_SECRET is missing"


# Test that the authorization header is created correctly and the correct header is generated
@patch("integrations.notify.create_jwt_token")
def test_successful_creation_of_header(mock_jwt_token):
    mock_jwt_token.return_value = "mocked_jwt_token"
    header_key, header_value = notify.create_authorization_header()

    assert header_key == "Authorization"
    assert header_value == "Bearer mocked_jwt_token"

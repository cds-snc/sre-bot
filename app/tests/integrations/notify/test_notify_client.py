import json
import jwt
import pytest
from integrations.notify import client as notify
from unittest.mock import patch, MagicMock
from freezegun import freeze_time


# helper function to decode the token for testing
def decode_token(token, secret):
    return jwt.decode(
        token, key=secret, options={"verify_signature": True}, algorithms=["HS256"]
    )


# Test that an exception is raised if the secret is missing
@patch("integrations.notify.client.logger")
def test_create_jwt_token_secret_missing(mock_logger):
    bound_logger_mock = mock_logger.bind.return_value
    with pytest.raises(ValueError) as err:
        notify.create_jwt_token(None, "client_id")
    assert str(err.value) == "Missing secret key"
    bound_logger_mock.error.assert_called_once_with(
        "jwt_token_creation_failed", error="Missing secret key"
    )


# Test that an exception is raised if the client_id is missing
@patch("integrations.notify.client.logger")
def test_create_jwt_token_client_id_missing(mock_logger):
    bound_logger_mock = mock_logger.bind.return_value
    with pytest.raises(ValueError) as err:
        notify.create_jwt_token("secret", None)
    assert str(err.value) == "Missing client id"
    bound_logger_mock.error.assert_called_once_with(
        "jwt_token_creation_failed", error="Missing client id"
    )


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


@patch("jwt.encode")
def test_create_jwt_token_with_bytes_return(mock_jwt_encode):
    mock_jwt_encode.return_value = b"encoded_token_as_bytes"

    token = notify.create_jwt_token("secret", "client_id")

    assert isinstance(token, str)
    assert token == "encoded_token_as_bytes"

    mock_jwt_encode.assert_called_once()
    call_args = mock_jwt_encode.call_args[1]
    assert call_args["key"] == "secret"
    assert call_args["headers"] == {"typ": "JWT", "alg": "HS256"}
    assert call_args["payload"]["iss"] == "client_id"


# Test that the correct iat time in epoch seconds is set correctly
@freeze_time("2020-01-01 00:00:00")
def test_token_contains_correct_iat():
    token = notify.create_jwt_token("secret", "client_id")
    decoded_token = decode_token(token, "secret")
    assert decoded_token["iat"] == 1577836800


# Test that an assertion error is raised if the NOTIFY_SRE_USER_NAME is missing
@patch.object(notify, "NOTIFY_SRE_USER_NAME", "")
@patch.object(notify, "NOTIFY_SRE_CLIENT_SECRET", "foo")
@patch("integrations.notify.client.logger")
@patch("integrations.notify.client.create_jwt_token")
def test_authorization_header_missing_client_id(jwt_token_mock, mock_logger):
    with pytest.raises(ValueError) as err:
        notify.create_authorization_header()
    assert str(err.value) == "NOTIFY_SRE_USER_NAME is missing"
    mock_logger.error.assert_called_once_with(
        "authorization_header_creation_failed",
        error="NOTIFY_SRE_USER_NAME is missing",
    )
    jwt_token_mock.assert_not_called()


# Test that an assertion error is raised if the NOTIFY_SRE_CLIENT_SECRET is missing
@patch.object(notify, "NOTIFY_SRE_USER_NAME", "foo")
@patch.object(notify, "NOTIFY_SRE_CLIENT_SECRET", "")
@patch("integrations.notify.client.logger")
@patch("integrations.notify.client.create_jwt_token")
def test_authorization_header_missing_secret(jwt_token_mock, mock_logger):
    with pytest.raises(ValueError) as err:
        notify.create_authorization_header()
    assert str(err.value) == "NOTIFY_SRE_CLIENT_SECRET is missing"
    mock_logger.error.assert_called_once_with(
        "authorization_header_creation_failed",
        error="NOTIFY_SRE_CLIENT_SECRET is missing",
    )
    jwt_token_mock.assert_not_called()


# Test that the authorization header is created correctly and the correct header is generated
@patch("integrations.notify.client.logger")
@patch("integrations.notify.client.create_jwt_token")
def test_successful_creation_of_header(mock_jwt_token, mock_logger):
    # bound_logger_mock = mock_logger.bind.return_value
    mock_jwt_token.return_value = "mocked_jwt_token"
    header_key, header_value = notify.create_authorization_header()

    assert header_key == "Authorization"
    assert header_value == "Bearer mocked_jwt_token"


@patch("integrations.notify.client.requests.post")
@patch("integrations.notify.client.create_authorization_header")
def test_post_event(mock_auth_header, mock_post):
    # Set up mock return values
    mock_auth_header.return_value = ("Auth-Header", "auth-value")
    mock_response = mock_post.return_value

    # Test data
    test_url = "https://api.notify.example.com/endpoint"
    test_payload = {"key1": "value1", "key2": "value2"}

    # Call the function
    response = notify.post_event(test_url, test_payload)

    # Verify the response is returned correctly
    assert response == mock_response

    # Verify create_authorization_header was called
    mock_auth_header.assert_called_once()

    # Verify requests.post was called with the correct parameters
    mock_post.assert_called_once_with(
        test_url,
        data=json.dumps(test_payload),
        headers={"Auth-Header": "auth-value", "Content-Type": "application/json"},
        timeout=60,
    )


# Test the revoke_api_key function when NOTIFY_API_URL is None
@patch.object(notify, "NOTIFY_API_URL", None)
@patch("integrations.notify.client.logger")
def test_revoke_api_key_missing_url(mock_logger):
    bound_logger_mock = mock_logger.bind.return_value
    result = notify.revoke_api_key("api-key-123", "api-type", "github.com/repo", "test")

    assert result is False
    bound_logger_mock.error.assert_called_once_with(
        "revoke_api_key_error", error="NOTIFY_API_URL is missing"
    )


# Test successful API key revocation (status code 201)
@patch.object(notify, "NOTIFY_API_URL", "https://notify.example.com")
@patch("integrations.notify.client.post_event")
@patch("integrations.notify.client.logger")
def test_revoke_api_key_success(mock_logger, mock_post_event):
    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_post_event.return_value = mock_response

    # Test data
    api_key = "test-api-key-123"
    api_type = "test-type"
    github_repo = "github.com/test/repo"
    source = "test-source"

    # Call the function
    result = notify.revoke_api_key(api_key, api_type, github_repo, source)

    # Verify results
    assert result is True

    # Verify post_event was called with correct parameters
    expected_url = "https://notify.example.com/sre-tools/api-key-revoke"
    expected_payload = {
        "token": api_key,
        "type": api_type,
        "url": github_repo,
        "source": source,
    }
    mock_post_event.assert_called_once_with(expected_url, expected_payload)

    # Verify logger was called correctly
    bound_logger_mock = mock_logger.bind.return_value
    bound_logger_mock.info.assert_called_once_with(
        "revoke_api_key_success", api_key=api_key
    )


# Test failed API key revocation (non-201 status code)
@patch.object(notify, "NOTIFY_API_URL", "https://notify.example.com")
@patch("integrations.notify.client.post_event")
@patch("integrations.notify.client.logger")
def test_revoke_api_key_failure(mock_logger, mock_post_event):
    # Mock failed response
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_post_event.return_value = mock_response

    # Test data
    api_key = "test-api-key-123"

    # Call the function
    result = notify.revoke_api_key(
        api_key, "test-type", "github.com/test/repo", "test-source"
    )

    # Verify results
    assert result is False

    # Verify logger was called correctly
    bound_logger_mock = mock_logger.bind.return_value
    bound_logger_mock.error.assert_called_once_with(
        "revoke_api_key_error",
        api_key=api_key,
        response_code=400,
    )

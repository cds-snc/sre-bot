from unittest import mock
from unittest.mock import ANY, call, MagicMock, patch, PropertyMock, Mock, AsyncMock
from server import bot_middleware, server
import urllib.parse
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse
from httpx import AsyncClient


import os
import pytest
from fastapi.testclient import TestClient
from fastapi import Request

app = server.handler
app.add_middleware(bot_middleware.BotMiddleware, bot=MagicMock())
client = TestClient(app)


@patch("server.server.maxmind.geolocate")
def test_geolocate_success(mock_geolocate):
    mock_geolocate.return_value = "country", "city", "latitude", "longitude"
    response = client.get("/geolocate/111.111.111.111")
    assert response.status_code == 200
    assert response.json() == {
        "country": "country",
        "city": "city",
        "latitude": "latitude",
        "longitude": "longitude",
    }


@patch("server.server.maxmind.geolocate")
def test_geolocate_failure(mock_geolocate):
    mock_geolocate.return_value = "error"
    response = client.get("/geolocate/111")
    assert response.status_code == 404
    assert response.json() == {"detail": "error"}


@patch("server.server.append_incident_buttons")
@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_to_sentinel")
def test_handle_webhook_found(
    _log_to_sentinel_mock,
    increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
    append_incident_buttons_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = {"channel": "channel"}
    append_incident_buttons_mock.return_value.json.return_value = "[]"
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert get_webhook_mock.call_count == 1
    assert increment_invocation_count_mock.call_count == 1
    assert append_incident_buttons_mock.call_count == 1


@patch("server.server.append_incident_buttons")
@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_to_sentinel")
def test_handle_webhook_disabled(
    _log_to_sentinel_mock,
    increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
    append_incident_buttons_mock,
):
    is_active_mock.return_value = False
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    payload = {"channel": "channel"}
    append_incident_buttons_mock.return_value.json.return_value = "[]"
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not active"}
    assert get_webhook_mock.call_count == 1
    assert increment_invocation_count_mock.call_count == 0
    assert append_incident_buttons_mock.call_count == 0


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_webhook_with_invalid_aws_json_payload(
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = "not a json payload"
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 500
    assert response.json() == {"detail": ANY}


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_webhook_with_bad_aws_signature(
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = '{"Type": "foo"}'
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 500
    assert response.json() == {"detail": ANY}


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_webhook_with_bad_aws_message_type(
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = '{"Type": "foo"}'
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Failed to parse AWS event message due to InvalidMessageTypeException: foo is not a valid message type."
    }


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_webhook_with_bad_aws_invalid_cert_version(
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = (
        '{"Type": "Notification", "SignatureVersion": "foo", "SigningCertURL": "foo"}'
    )
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 500
    assert response.json() == {
        "detail": "Failed to parse AWS event message due to InvalidSignatureVersionException: Invalid signature version. Unable to verify signature."
    }


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_webhook_with_bad_aws_invalid_signature_version(
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = '{"Type":"Notification", "SigningCertURL":"https://foo.pem", "SignatureVersion":"1"}'
    response = client.post("/hook/id", json=payload)

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Failed to parse AWS event message due to InvalidCertURLException: Invalid certificate URL."
    }


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
@patch("server.server.sns_message_validator.validate_message")
@patch("server.server.requests.get")
def test_handle_webhook_with_SubscriptionConfirmation_payload(
    get_mock,
    validate_message_mock,
    log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    validate_message_mock.return_value = True
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = '{"Type": "SubscriptionConfirmation", "SubscribeURL": "SubscribeURL", "TopicArn": "TopicArn"}'
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert log_ops_message_mock.call_count == 1


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.sns_message_validator.validate_message")
@patch("server.server.log_ops_message")
def test_handle_webhook_with_UnsubscribeConfirmation_payload(
    log_ops_message_mock,
    validate_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    validate_message_mock.return_value = True
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = '{"Type": "UnsubscribeConfirmation"}'
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert log_ops_message_mock.call_count == 1


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.sns_message_validator.validate_message")
@patch("server.server.aws.parse")
@patch("server.server.log_to_sentinel")
def test_handle_webhook_with_Notification_payload(
    _log_to_sentinel_mock,
    parse_mock,
    validate_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    validate_message_mock.return_value = True
    parse_mock.return_value = ["foo", "bar"]
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = '{"Type": "Notification"}'
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@patch("server.server.append_incident_buttons")
@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_webhook_found_but_exception(
    log_ops_message_mock,
    increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
    append_incident_buttons_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = MagicMock()
    append_incident_buttons_mock.return_value.json.return_value = "[]"
    request = MagicMock()
    request.state.bot.client.api_call.side_effect = Exception("error")
    with pytest.raises(Exception):
        server.handle_webhook("id", payload, request)
        assert log_ops_message_mock.call_count == 1


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.sns_message_validator.validate_message")
@patch("server.server.aws.parse")
@patch("server.server.log_to_sentinel")
def test_handle_webhook_with_empty_text_for_payload(
    _log_to_sentinel_mock,
    parse_mock,
    validate_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    # Test that we don't post to slack if we have an empty message
    validate_message_mock.return_value = True
    parse_mock.return_value = []
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = '{"Type": "Notification", "Message": "{}"}'
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() is None


@patch("server.server.webhooks.get_webhook")
def test_handle_webhook_not_found(get_webhook_mock):
    get_webhook_mock.return_value = None
    payload = {"channel": "channel"}
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not found"}
    assert get_webhook_mock.call_count == 1


def test_get_version_unkown():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": "unknown"}


@patch.dict(os.environ, {"GIT_SHA": "foo"}, clear=True)
def test_get_version_known():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": "foo"}


def test_append_incident_buttons():
    payload = MagicMock()
    attachments = PropertyMock(return_value=[])
    type(payload).attachments = attachments
    type(payload).text = PropertyMock(return_value="text")
    webhook_id = "bar"
    resp = server.append_incident_buttons(payload, webhook_id)
    assert payload == resp
    assert attachments.call_count == 2
    assert attachments.call_args_list == [
        call(),
        call(
            [
                {
                    "fallback": "Incident",
                    "callback_id": "handle_incident_action_buttons",
                    "color": "#3AA3E3",
                    "attachment_type": "default",
                    "actions": [
                        {
                            "name": "call-incident",
                            "text": "🎉   Call incident ",
                            "type": "button",
                            "value": "text",
                            "style": "primary",
                        },
                        {
                            "name": "ignore-incident",
                            "text": "🙈   Acknowledge and ignore",
                            "type": "button",
                            "value": "bar",
                            "style": "default",
                        },
                    ],
                }
            ]
        ),
    ]


# Unit test the react app
def test_react_app():
    # test the react app
    response = client.get("/some/path")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# Test the logout endpoint
def test_logout_endpoint():
    # Test that the endpoint returns a 200 status code
    response = client.get("/logout")
    assert response.status_code == 200

    # Test that the user session is removed
    response = client.get("/home")
    assert response.status_code == 200
    assert "user" not in response.cookies


# Test the login endpoint and that it redirects to the Google OAuth page
def test_login_endpoint():
    response = client.get("/login")
    assert response.status_code == 200
    assert "https://accounts.google.com/o/oauth2/v2/auth" in str(response.url)


# Test the login endpoint converts the redirect_uri to https
@mock.patch.dict(os.environ, {"ENVIRONMENT": "prod"})
def test_login_endpoint_redirect_uri_prod():
    # Make a test request to the login endpoint
    response = client.get("/login")

    # assert the call is successful
    assert response.status_code == 200

    if os.environ.get("ENVIRONMENT") == "prod":
        redirect_uri = urllib.parse.quote_plus("http://testserver/auth")
        redirect_uri = redirect_uri.__str__().replace("http", "https")

    # assert that the response url we get from the login endpoint contains the redirect_uri replaced with https
    assert response.url.__str__().__contains__("redirect_uri=" + redirect_uri)


# Test the login endpoing that does not convert the redirect uri
@mock.patch.dict(os.environ, {"ENVIRONMENT": "dev"})
def test_login_endpoint_redirect_uri_dev():
    # Make a test request to the login endpoint
    response = client.get("/login")

    # assert the call is successful
    assert response.status_code == 200

    if os.environ.get("ENVIRONMENT") == "dev":
        redirect_uri = urllib.parse.quote_plus("http://testserver/auth")

    # assert that the response url we get from the login endpoint contains the redirect_uri is not replaced with https (we need to keep the http)
    assert response.url.__str__().__contains__("redirect_uri=" + redirect_uri)


# Test the auth endpoint
def test_auth_endpoint():
    response = client.get("/auth")
    assert response.status_code == 200
    assert "http://testserver/auth" in str(response.url)


# Test the user endpoint, logged in
def test_user_route_logged_in():
    # Simulate a logged-in session by creating a mock request with session data
    session_data = {"user": {"given_name": "FirstName"}}
    headers = {"Cookie": f"session={session_data}"}
    response = client.get("/user", headers=headers)
    assert response.status_code == 200


# Test the user endpoing, not logged in
def test_user_endpoint_with_no_logged_in_user():
    response = client.get("/user")
    assert response.status_code == 200
    assert response.json() == {"error": "Not logged in"}


def test_header_exists_and_not_empty():
    # Create a mock request with the header 'X-Sentinel-Source'
    mock_request = Mock(spec=Request)
    mock_request.headers = {"X-Sentinel-Source": "some_value"}

    # Call the function
    result = server.sentinel_key_func(mock_request)

    # Assert that the result is None (no rate limiting)
    assert result is None


def test_header_not_present():
    # Create a mock request without the header 'X-Sentinel-Source'
    mock_request = Mock(spec=Request)
    mock_request.headers = {}

    # Mock the client attribute to return the expected IP address
    mock_request.client.host = "192.168.1.1"

    # Mock the get_remote_address function to return a specific value
    with patch("slowapi.util.get_remote_address", return_value="192.168.1.1"):
        result = server.sentinel_key_func(mock_request)
    # Assert that the result is the IP address (rate limiting applied)
    assert result == "192.168.1.1"


def test_header_empty():
    # Create a mock request with an empty 'X-Sentinel-Source' header
    mock_request = Mock(spec=Request)
    mock_request.headers = {"X-Sentinel-Source": ""}

    # Mock the client attribute to return the expected IP address
    mock_request.client.host = "192.168.1.1"

    # Mock the get_remote_address function to return a specific value
    with patch("slowapi.util.get_remote_address", return_value="192.168.1.1"):
        result = server.sentinel_key_func(mock_request)

    # Assert that the result is the IP address (rate limiting applied)
    assert result == "192.168.1.1"


@pytest.mark.asyncio
async def test_rate_limit_handler():
    # Create a mock request
    mock_request = Mock(spec=Request)

    # Create a mock exception
    mock_exception = Mock(spec=RateLimitExceeded)

    # Call the handler function
    response = await server.rate_limit_handler(mock_request, mock_exception)

    # Assert the response is a JSONResponse
    assert isinstance(response, JSONResponse)

    # Assert the status code is 429
    assert response.status_code == 429

    # Assert the content of the response
    assert response.body.decode("utf-8") == '{"message":"Rate limit exceeded"}'


@pytest.mark.asyncio
async def test_logout_rate_limiting():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Make 5 requests to the logout endpoint
        for _ in range(5):
            response = await client.get("/logout")
            assert response.status_code == 307
            assert response.url.path == "/logout"

        # The 6th request should be rate limited
        response = await client.get("/logout")
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}


@pytest.mark.asyncio
async def test_login_rate_limiting():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Set the environment variable for the test
        os.environ["ENVIRONMENT"] = "dev"

        # Make 5 requests to the login endpoint
        for _ in range(5):
            response = await client.get("/login")
            assert response.status_code == 302

        # The 6th request should be rate limited
        response = await client.get("/login")
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}


@pytest.mark.asyncio
async def test_auth_rate_limiting():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Mock the OAuth process
        with patch(
            "server.server.oauth.google.authorize_access_token", new_callable=AsyncMock
        ) as mock_auth:
            mock_auth.return_value = {"userinfo": {"name": "Test User"}}

            # Make 5 requests to the auth endpoint
            for _ in range(5):
                response = await client.get("/auth")
                assert response.status_code == 307

            # The 6th request should be rate limited
            response = await client.get("/auth")
            assert response.status_code == 429
            assert response.json() == {"message": "Rate limit exceeded"}


@pytest.mark.asyncio
async def test_user_rate_limiting():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Simulate a logged in session
        session_data = {"user": {"given_name": "FirstName"}}
        headers = {"Cookie": f"session={session_data}"}
        # Make 5 requests to the user endpoint
        for _ in range(5):
            response = await client.get("/user", headers=headers)
            assert response.status_code == 200

        # The 6th request should be rate limited
        response = await client.get("/user", headers=headers)
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}


@pytest.mark.asyncio
async def test_webhooks_rate_limiting():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Mock the webhooks.get_webhook function
        with patch(
            "server.server.webhooks.get_webhook",
            return_value={"channel": {"S": "test-channel"}},
        ):
            with patch("server.server.webhooks.is_active", return_value=True):
                with patch("server.server.webhooks.increment_invocation_count"):
                    with patch("server.server.sns_message_validator.validate_message"):
                        # Make 30 requests to the handle_webhook endpoint
                        payload = '{"Type": "Notification"}'
                        for _ in range(30):
                            response = await client.post("/hook/test-id", json=payload)
                            assert response.status_code == 200

                        # The 31st request should be rate limited
                        response = await client.post("/hook/test-id", json=payload)
                        assert response.status_code == 429
                        assert response.json() == {"message": "Rate limit exceeded"}


@pytest.mark.asyncio
async def test_version_rate_limiting():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Make 5 requests to the version endpoint
        for _ in range(50):
            response = await client.get("/version")
            assert response.status_code == 200

        # The 51th request should be rate limited
        response = await client.get("/version")
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}


@pytest.mark.asyncio
async def test_react_app_rate_limiting():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Make 10 requests to the react_app endpoint
        for _ in range(10):
            response = await client.get("/some-path")
            assert response.status_code == 200

        # The 11th request should be rate limited
        response = await client.get("/some-path")
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}

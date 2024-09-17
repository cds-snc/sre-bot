from unittest import mock
from unittest.mock import call, MagicMock, patch, PropertyMock, Mock, AsyncMock
from server import bot_middleware, server
from server.server import AccessRequest
import urllib.parse
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse
from httpx import AsyncClient
from starlette.types import Scope
from starlette.datastructures import Headers, MutableHeaders
import os
import pytest
import datetime
from fastapi.testclient import TestClient
from fastapi import Request, HTTPException, status

from models.webhooks import AwsSnsPayload, WebhookPayload

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


@patch("server.server.webhooks.get_webhook")
def test_handle_webhook_not_found(get_webhook_mock):
    get_webhook_mock.return_value = None
    payload = {"channel": "channel"}
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 404
    assert response.json() == {"detail": "Webhook not found"}
    assert get_webhook_mock.call_count == 1


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
@patch("server.server.log_ops_message")
@patch("server.server.handle_string_payload")
def test_handle_webhook_string_returns_webhook_payload(
    handle_string_payload_mock,
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
    caplog,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = '{"channel": "channel"}'
    handle_string_payload_mock.return_value = {"channel": "channel", "blocks": "blocks"}
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"channel": "channel", "blocks": "blocks"}
    assert handle_string_payload_mock.call_count == 1


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
@patch("server.server.handle_string_payload")
def test_handle_webhook_string_payload_returns_OK_status(
    handle_string_payload_mock,
    _log_ops_message_mock,
    _increment_invocation_count_mock,
    is_active_mock,
    get_webhook_mock,
):
    get_webhook_mock.return_value = {"channel": {"S": "channel"}}
    is_active_mock.return_value = True
    payload = "test"
    handle_string_payload_mock.return_value = {"ok": True}
    response = client.post("/hook/id", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert handle_string_payload_mock.call_count == 1


@patch("server.server.webhooks.validate_string_payload_type")
def test_handle_string_payload_with_webhook_string(
    validate_string_payload_type_mock,
):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "WebhookPayload",
        {"channel": "channel"},
    )
    payload = '{"channel": "channel"}'
    response = server.handle_string_payload(payload, request)
    assert response.channel == "channel"


@patch("server.server.aws.parse")
@patch("server.server.aws.validate_sns_payload")
@patch("server.server.webhooks.validate_string_payload_type")
def test_handle_string_payload_with_aws_sns_notification_without_message(
    validate_string_payload_type_mock,
    validate_sns_payload_mock,
    parse_mock,
):
    request = MagicMock()
    payload = '{"Type": "Notification", "Message": "{}"}'
    validate_string_payload_type_mock.return_value = (
        "AwsSnsPayload",
        {"Type": "Notification", "Message": ""},
    )
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="Notification", Message=""
    )
    parse_mock.return_value = ""
    response = server.handle_string_payload(payload, request)
    assert response == {"ok": True}


@patch("server.server.aws.parse")
@patch("server.server.aws.validate_sns_payload")
@patch("server.server.webhooks.validate_string_payload_type")
def test_handle_string_payload_with_aws_sns_notification(
    validate_string_payload_type_mock, validate_sns_payload_mock, parse_mock
):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "AwsSnsPayload",
        {"Type": "Notification", "Message": "message"},
    )
    payload = '{"Type": "Notification", "Message": "message"}'
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="Notification", Message="message"
    )
    parse_mock.return_value = "parsed_blocks"
    response = server.handle_string_payload(payload, request)
    assert response.blocks == "parsed_blocks"


@patch("server.server.log_ops_message")
@patch("server.server.requests.get")
@patch("server.server.aws.validate_sns_payload")
@patch("server.server.webhooks.validate_string_payload_type")
def test_handle_string_payload_with_aws_sns_subscription_confirmation(
    validate_string_payload_type_mock,
    validate_sns_payload_mock,
    get_mock,
    log_ops_message_mock,
):
    request = MagicMock()
    payload = (
        '{"Type": "SubscriptionConfirmation", "SubscribeURL": "http://example.com"}'
    )
    validate_string_payload_type_mock.return_value = (
        "AwsSnsPayload",
        {"Type": "SubscriptionConfirmation", "SubscribeURL": "http://example.com"},
    )
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="SubscriptionConfirmation", SubscribeURL="http://example.com"
    )
    response = server.handle_string_payload(payload, request)
    assert response == {"ok": True}
    assert log_ops_message_mock.call_count == 1


@patch("server.server.aws.validate_sns_payload")
@patch("server.server.webhooks.validate_string_payload_type")
def test_handle_string_payload_with_aws_sns_unsubscribe_confirmation(
    validate_string_payload_type_mock, validate_sns_payload_mock
):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "AwsSnsPayload",
        {
            "Type": "UnsubscribeConfirmation",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic",
        },
    )
    payload = '{"Type": "UnsubscribeConfirmation", "TopicArn": "arn:aws:sns:us-east-1:123456789012:MyTopic"}'
    validate_sns_payload_mock.return_value = AwsSnsPayload(
        Type="UnsubscribeConfirmation",
        TopicArn="arn:aws:sns:us-east-1:123456789012:MyTopic",
    )
    response = server.handle_string_payload(payload, request)
    assert response == {"ok": True}


@patch("server.server.webhooks.validate_string_payload_type")
def test_handle_string_payload_with_access_request(validate_string_payload_type_mock):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "AccessRequest",
        {"user": "user1"},
    )
    payload = '{"user": "user1"}'
    response = server.handle_string_payload(payload, request)
    assert response.text == '{"user": "user1"}'


@patch("server.server.webhooks.validate_string_payload_type")
def test_handle_string_payload_with_upptime_payload(validate_string_payload_type_mock):
    request = MagicMock()
    payload = '{"text": "🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222"}'
    validate_string_payload_type_mock.return_value = (
        "UpptimePayload",
        {
            "text": "🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222"
        },
    )
    response = server.handle_string_payload(payload, request)
    assert response.blocks == [
        {"text": {"text": " ", "type": "mrkdwn"}, "type": "section"},
        {
            "text": {"text": "📈 Web Application Down!", "type": "plain_text"},
            "type": "header",
        },
        {
            "text": {
                "text": "🟥 Payload Test (https://not-valid.cdssandbox.xyz/) is **down** : https://github.com/cds-snc/status-statut/issues/222",
                "type": "mrkdwn",
            },
            "type": "section",
        },
    ]


@patch("server.server.webhooks.validate_string_payload_type")
def test_handle_string_payload_with_invalid_payload_type(
    validate_string_payload_type_mock,
):
    request = MagicMock()
    validate_string_payload_type_mock.return_value = (
        "InvalidPayloadType",
        {},
    )
    payload = "{}"
    with pytest.raises(HTTPException) as exc_info:
        server.handle_string_payload(payload, request)
    assert exc_info.value.status_code == 500
    assert (
        exc_info.value.detail
        == "Invalid payload type. Must be a WebhookPayload object or a recognized string payload type."
    )


@patch("server.server.webhooks.get_webhook")
@patch("server.server.webhooks.is_active")
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.log_ops_message")
def test_handle_string_payload_with_invalid_json_payload(
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
    assert response.json() == {
        "detail": "Invalid payload type. Must be a WebhookPayload object or a recognized string payload type."
    }


def test_handle_string_payload_with_valid_json_payload():
    pass


def test_get_version_unkown():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": "unknown"}


@patch.dict(os.environ, {"GIT_SHA": "foo"}, clear=True)
def test_get_version_known():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": "foo"}


def test_append_incident_buttons_with_list_attachments():
    payload = MagicMock()
    attachments = PropertyMock(return_value=[])
    type(payload).attachments = attachments
    type(payload).text = PropertyMock(return_value="text")
    webhook_id = "bar"
    resp = server.append_incident_buttons(payload, webhook_id)
    assert payload == resp
    assert attachments.call_count == 4
    assert attachments.call_args_list == [
        call(),
        call(),
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


def test_append_incident_buttons_with_none_attachments():
    payload = MagicMock()
    payload.attachments = None
    payload.text = "text"
    webhook_id = "bar"

    resp = server.append_incident_buttons(payload, webhook_id)

    assert payload == resp
    assert payload.attachments == [
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


def test_append_incident_buttons_with_str_attachments():
    payload = MagicMock()
    payload.attachments = "existing_attachment"
    payload.text = "text"
    webhook_id = "bar"

    resp = server.append_incident_buttons(payload, webhook_id)
    assert payload == resp
    assert payload.attachments == [
        "existing_attachment",
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
        },
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
            mock_auth.return_value = {
                "userinfo": {"name": "Test User", "email": "test@test.com"}
            }

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
        session_data = {"user": {"given_name": "FirstName", "email": "test@test.com"}}
        headers = {"Cookie": f"session={session_data}"}
        # Make 10 requests to the user endpoint
        for _ in range(10):
            response = await client.get("/user", headers=headers)
            assert response.status_code == 200

        # The 11th request should be rate limited
        response = await client.get("/user", headers=headers)
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}


@patch(
    "server.server.webhooks.get_webhook",
    return_value={"channel": {"S": "test-channel"}},
)
@patch("server.server.webhooks.is_active", return_value=True)
@patch("server.server.webhooks.increment_invocation_count")
@patch("server.server.handle_string_payload", return_value=WebhookPayload())
@pytest.mark.asyncio
async def test_webhooks_rate_limiting(
    get_webhook_mock,
    is_active_mock,
    increment_invocation_count_mock,
    handle_string_payload_mock,
):
    async with AsyncClient(app=app, base_url="http://test") as client:
        get_webhook_mock.return_value = {"channel": {"S": "test-channel"}}
        payload = '{"Type": "Notification"}'
        handle_string_payload_mock.return_value = {"ok": True}
        # Make 30 requests to the handle_webhook endpoint
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
        # Make 20 requests to the react_app endpoint
        for _ in range(20):
            response = await client.get("/some-path")
            assert response.status_code == 200

        # The 21th request should be rate limited
        response = await client.get("/some-path")
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}


@pytest.fixture
def valid_access_request():
    return AccessRequest(
        account="ExampleAccount",
        reason="test_reason",
        startDate=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=10),
        endDate=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )


@pytest.fixture
def expired_access_request():
    return AccessRequest(
        account="ExampleAccount",
        reason="test_reason",
        startDate=datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(minutes=10),
        endDate=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )


@pytest.fixture
def invalid_dates_access_request():
    return AccessRequest(
        account="ExampleAccount",
        reason="test_reason",
        startDate=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
        endDate=datetime.datetime.now(datetime.timezone.utc),
    )


@pytest.fixture
def more_than_24hours_dates_access_request():
    return AccessRequest(
        account="ExampleAccount",
        reason="test_reason",
        startDate=datetime.datetime.now(datetime.timezone.utc),
        endDate=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=5),
    )


def get_mock_request(session_data=None, cookies=None):
    headers = Headers({"content-type": "application/json"})
    if cookies:
        cookie_header = "; ".join([f"{key}={value}" for key, value in cookies.items()])
        headers = MutableHeaders(headers)
        headers.append("cookie", cookie_header)

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "headers": headers.raw,
        "path": "/request_access",
        "raw_path": b"/request_access",
        "session": session_data or {},
    }
    return Request(scope)


@patch("server.utils.get_user_email_from_request")
@patch("server.server.get_current_user", new_callable=AsyncMock)
@patch("integrations.aws.identity_store.get_user_id")
@patch("integrations.aws.organizations.get_account_id_by_name")
@patch("integrations.aws.organizations.list_organization_accounts")
@patch("modules.aws.aws.aws_access_requests.create_aws_access_request")
@pytest.mark.asyncio
async def test_create_access_request_succes(
    create_aws_access_request_mock,
    mock_list_organization_accounts,
    mock_get_account_id_by_name,
    mock_get_user_id,
    mock_get_current_user,
    mock_get_user_email_from_request,
    valid_access_request,
):
    mock_accounts = [
        {
            "Id": "345678901234",
            "Arn": "arn:aws:organizations::345678901234:account/o-exampleorgid/345678901234",
            "Email": "example3@example.com",
            "Name": "ExampleAccount",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2023-02-15T12:00:00.000000+00:00",
        }
    ]

    session_data = {"user": {"username": "test_user", "email": "user@example.com"}}
    request = get_mock_request(session_data)
    mock_list_organization_accounts.return_value = mock_accounts
    mock_get_user_id.return_value = "user_id_456"
    mock_get_account_id_by_name.return_value = "345678901234"
    mock_get_current_user.return_value = {"username": "test_user"}
    mock_get_user_email_from_request.return_value = "user@example.com"
    create_aws_access_request_mock.return_value = True

    # Act
    response = await server.create_access_request(request, valid_access_request)

    # Assert
    assert response == {
        "message": "Access request created successfully",
        "data": valid_access_request,
    }


@patch("server.server.get_current_user", new_callable=AsyncMock)
@patch("server.utils.get_user_email_from_request")
@patch("modules.aws.aws.request_aws_account_access", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_access_request_missing_fields(
    mock_request_aws_account_access,
    mock_get_user_email_from_request,
    mock_get_current_user,
):
    # Arrange
    access_request = AccessRequest(
        account="",
        reason="",
        startDate=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=10),
        endDate=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
    )
    session_data = {"user": {"username": "test_user", "email": "user@example.com"}}
    request = get_mock_request(session_data)

    # Act & Assert
    with pytest.raises(HTTPException) as excinfo:
        await server.create_access_request(request, access_request)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Account and reason are required"


@patch("server.server.get_current_user", new_callable=AsyncMock)
@patch("server.utils.get_user_email_from_request")
@patch("modules.aws.aws.request_aws_account_access", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_access_request_start_date_in_past(
    mock_request_aws_account_access,
    mock_get_user_email_from_request,
    mock_get_current_user,
    expired_access_request,
):
    # Arrange
    session_data = {"user": {"username": "test_user", "email": "user@example.com"}}
    request = get_mock_request(session_data)
    mock_get_user_email_from_request.return_value = "user@example.com"
    mock_get_current_user.return_value = {"user": "test_user"}

    # Act & Assert
    with pytest.raises(HTTPException) as excinfo:
        await server.create_access_request(request, expired_access_request)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Start date must be in the future"


@patch("server.server.get_current_user", new_callable=AsyncMock)
@patch("server.utils.get_user_email_from_request")
@patch("modules.aws.aws.request_aws_account_access", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_create_access_request_end_date_before_start_date(
    mock_request_aws_account_access,
    mock_get_user_email_from_request,
    mock_get_current_user,
    invalid_dates_access_request,
):
    # Arrange
    session_data = {"user": {"username": "test_user", "email": "user@example.com"}}
    request = get_mock_request(session_data)
    mock_get_user_email_from_request.return_value = "user@example.com"
    mock_get_current_user.return_value = {"user": "test_user"}

    # Act & Assert
    with pytest.raises(HTTPException) as excinfo:
        await server.create_access_request(request, invalid_dates_access_request)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "End date must be after start date"


@patch("server.server.get_current_user", new_callable=AsyncMock)
@patch("server.utils.get_user_email_from_request")
@patch("integrations.aws.identity_store.get_user_id")
@patch("integrations.aws.organizations.list_organization_accounts")
@patch("modules.aws.aws.aws_access_requests.create_aws_access_request")
@pytest.mark.asyncio
async def test_create_access_request_more_than_24_hours(
    mock_create_aws_access_request,
    mock_get_organization_accounts,
    mock_get_user_id,
    mock_get_user_email_from_request,
    mock_get_current_user,
    more_than_24hours_dates_access_request,
):
    # Arrange
    session_data = {"user": {"username": "test_user", "email": "user@example.com"}}
    cookies = {"access_token": "mocked_jwt_token"}
    request = get_mock_request(session_data, cookies)
    mock_accounts = [
        {
            "Id": "345678901234",
            "Arn": "arn:aws:organizations::345678901234:account/o-exampleorgid/345678901234",
            "Email": "example3@example.com",
            "Name": "ExampleAccount",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2023-02-15T12:00:00.000000+00:00",
        }
    ]

    mock_get_organization_accounts.return_value = mock_accounts
    mock_get_user_email_from_request.return_value = "user@example.com"
    mock_get_user_id.return_value = "user_id_456"
    mock_get_current_user.return_value = {"user": "test_user"}
    mock_create_aws_access_request.return_value = True

    # Act & Assert
    with pytest.raises(HTTPException) as excinfo:
        await server.create_access_request(
            request, more_than_24hours_dates_access_request
        )
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "The access request cannot be for more than 24 hours"


@patch("server.server.get_current_user", new_callable=AsyncMock)
@patch("server.utils.get_user_email_from_request")
@patch("integrations.aws.identity_store.get_user_id")
@patch("integrations.aws.organizations.list_organization_accounts")
@patch("modules.aws.aws.aws_access_requests.create_aws_access_request")
@pytest.mark.asyncio
async def test_create_access_request_failure(
    mock_create_aws_access_request,
    mock_get_organization_accounts,
    mock_get_user_id,
    mock_get_user_email_from_request,
    mock_get_current_user,
    valid_access_request,
):
    # Arrange
    session_data = {"user": {"username": "test_user", "email": "user@example.com"}}
    request = get_mock_request(session_data)
    mock_accounts = [
        {
            "Id": "345678901234",
            "Arn": "arn:aws:organizations::345678901234:account/o-exampleorgid/345678901234",
            "Email": "example3@example.com",
            "Name": "ExampleAccount",
            "Status": "ACTIVE",
            "JoinedMethod": "INVITED",
            "JoinedTimestamp": "2023-02-15T12:00:00.000000+00:00",
        }
    ]

    mock_get_organization_accounts.return_value = mock_accounts
    mock_get_user_email_from_request.return_value = "user@example.com"
    mock_get_user_id.return_value = "user_id_456"
    mock_get_current_user.return_value = {"user": "test_user"}
    mock_create_aws_access_request.return_value = False

    # Act & Assert
    with pytest.raises(HTTPException) as excinfo:
        await server.create_access_request(request, valid_access_request)
    assert excinfo.value.status_code == 500
    assert excinfo.value.detail == "Failed to create access request"


@pytest.mark.asyncio
async def test_get_aws_active_requests_unauthenticated():
    # Mock get_current_user to raise an HTTPException
    with patch("modules.aws.aws_access_requests.get_active_requests"):
        with patch(
            "server.utils.get_current_user",
            side_effect=HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            ),
        ):
            # Create an invalid JWT token
            invalid_jwt_token = "invalid_jwt_token"

            # Mock the cookie in the request
            request = get_mock_request(cookies={"access_token": invalid_jwt_token})

            # Call the dependency function directly to see if it raises an exception
            with pytest.raises(HTTPException):
                await server.get_current_user(request)

            # If you need to test the actual endpoint, use the TestClient
            response = client.get(
                "/active_requests", cookies={"access_token": invalid_jwt_token}
            )

            # Assertions for the endpoint
            assert response.status_code == 401
            assert response.json() == {"detail": "Invalid token"}


@patch("server.utils.get_current_user", new_callable=AsyncMock)
@patch("modules.aws.aws_access_requests.dynamodb_client")
@patch("modules.aws.aws_access_requests.get_active_requests")
@pytest.mark.asyncio
async def test_get_aws_active_requests_success(
    mock_get_active_requests, mock_dynamodbscan, mock_get_current_user
):
    mock_get_current_user.return_value = {"username": "test_user"}

    mock_response = [
        {
            "id": {"S": "123"},
            "account_name": {"S": "ExampleAccount"},
            "access_type": {"S": "read"},
            "reason_for_access": {"S": "test_reason"},
            "start_date_time": {"S": "1720820150.452"},
            "end_date_time": {"S": "1720830150.452"},
            "expired": {"BOOL": False},
        },
        {
            "id": {"S": "456"},
            "account_name": {"S": "ExampleAccount2"},
            "access_type": {"S": "write"},
            "reason_for_access": {"S": "test_reason2"},
            "start_date_time": {"S": "1720820150.999"},
            "end_date_time": {"S": "1720830150.999"},
            "expired": {"BOOL": False},
        },
    ]
    mock_dynamo_response = {"Items": mock_response}
    mock_dynamodbscan.scan.return_value = mock_dynamo_response

    # Create a mock request with the cookie
    request = get_mock_request(cookies={"access_token": "mocked_jwt_token"})

    # Act
    mock_get_active_requests.return_value = mock_response
    response = await server.get_aws_active_requests(request)

    # Assertions
    assert response == mock_response


@pytest.mark.asyncio
async def test_get_aws_active_requests_exception_unauthenticated():
    # Mock get_current_user to raise an HTTPException
    with patch("modules.aws.aws_access_requests.get_active_requests"):
        with patch(
            "server.utils.get_current_user",
            side_effect=HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
            ),
        ):
            # Make the GET request
            response = client.get("/active_requests")

            # Assertions
            assert response.status_code == 401
            assert response.json() == {"detail": "Not authenticated"}

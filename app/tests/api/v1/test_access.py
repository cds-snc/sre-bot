import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from fastapi import Request, HTTPException, status
from fastapi.testclient import TestClient
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import Scope
from api.v1.routes import access
from models.webhooks import AccessRequest
from utils.tests import create_test_app
from server import bot_middleware

middlewares = [(bot_middleware.BotMiddleware, {"bot": MagicMock()})]
test_app = create_test_app(access.router, middlewares)
client = TestClient(test_app)


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
@patch("api.v1.routes.access.get_current_user", new_callable=AsyncMock)
@patch("integrations.aws.identity_store.get_user_id")
@patch("integrations.aws.organizations.get_account_id_by_name")
@patch("integrations.aws.organizations.list_organization_accounts")
@patch("modules.aws.aws.aws_access_requests.create_aws_access_request")
@pytest.mark.asyncio
async def test_create_access_request_success(
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
    response = await access.create_access_request(request, valid_access_request)

    # Assert
    assert response == {
        "message": "Access request created successfully",
        "data": valid_access_request,
    }


@patch("api.v1.routes.access.get_current_user", new_callable=AsyncMock)
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
        await access.create_access_request(request, access_request)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Account and reason are required"


@patch("api.v1.routes.access.get_current_user", new_callable=AsyncMock)
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
        await access.create_access_request(request, expired_access_request)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Start date must be in the future"


@patch("api.v1.routes.access.get_current_user", new_callable=AsyncMock)
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
        await access.create_access_request(request, invalid_dates_access_request)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "End date must be after start date"


@patch("api.v1.routes.access.get_current_user", new_callable=AsyncMock)
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
        await access.create_access_request(
            request, more_than_24hours_dates_access_request
        )
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "The access request cannot be for more than 24 hours"


@patch("api.v1.routes.access.get_current_user", new_callable=AsyncMock)
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
        await access.create_access_request(request, valid_access_request)
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
                await access.get_current_user(request, None)

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
    response = await access.get_aws_active_requests(request)

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

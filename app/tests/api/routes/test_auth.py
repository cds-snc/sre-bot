from unittest.mock import AsyncMock, PropertyMock, patch, MagicMock, ANY
import pytest
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from starlette.datastructures import URL
from authlib.integrations.starlette_client import OAuthError  # type: ignore
from api.routes import auth
from utils.tests import create_test_app, rate_limiting_helper

middlewares = [(SessionMiddleware, {"secret_key": "test-secret-key"})]
test_app = create_test_app(auth.router, middlewares)
client = TestClient(test_app)


# Test the logout endpoint
@patch("api.routes.auth.FRONTEND_URL", "http://testserver")
@patch("api.routes.auth.RedirectResponse")
@patch("api.routes.auth.Request.session", new_callable=PropertyMock)
def test_logout_endpoint(mock_session, mock_redirect):
    # Configure mocks
    mock_session.return_value = {"user": {"given_name": "FirstName"}}

    # Configure the RedirectResponse mock
    mock_redirect_instance = MagicMock()
    mock_redirect_instance.status_code = 200
    mock_redirect.return_value = mock_redirect_instance

    # Make the request
    response = client.get("/auth/logout")

    # Verify RedirectResponse was created with correct URL
    mock_redirect.assert_called_once_with(url="http://testserver")

    # Assert on the response from our mocked RedirectResponse
    assert response.status_code == 200


# Test the login endpoint and that it redirects to the Google OAuth page
@patch("authlib.integrations.starlette_client.StarletteOAuth2App.authorize_redirect")
def test_login_endpoint(mock_authorize_redirect):

    # Configure mock to return a redirect response
    redirect_url = "https://accounts.google.com/o/oauth2/v2/auth"
    mock_authorize_redirect.return_value = RedirectResponse(url=redirect_url)

    # Make the request with follow_redirects=False to see the actual redirect
    response = client.get("/auth/login", follow_redirects=False)

    # Assert on the correct status code for a redirect
    # (FastAPI default value for TemporaryRedirect is 307 and we won't go through the whole OAuth flow, which should be 302)
    assert response.status_code in (302, 307)

    # Check that location header has the correct redirect URL
    assert redirect_url in response.headers["location"]


# Test the login endpoint converts the redirect_uri to https
@patch("api.routes.auth.settings")
@patch("authlib.integrations.starlette_client.StarletteOAuth2App.authorize_redirect")
@patch("api.routes.auth.Request")
def test_login_endpoint_redirect_uri_prod(
    mock_request, mock_authorize_redirect, mock_settings
):
    mock_request.url_for.return_value = URL("http://testserver/auth/callback")
    redirect_url = "https://accounts.google.com/o/oauth2/v2/auth"
    mock_authorize_redirect.return_value = RedirectResponse(url=redirect_url)
    # Make a test request to the login endpoint
    response = client.get("/auth/login", follow_redirects=False)

    # assert the call is successful
    mock_authorize_redirect.assert_called_once_with(
        ANY, "https://testserver/auth/callback"
    )
    assert response.status_code in (302, 307)


# Test the login endpoint does not convert the redirect_uri to https
@patch("api.routes.auth.settings")
@patch("authlib.integrations.starlette_client.StarletteOAuth2App.authorize_redirect")
@patch("api.routes.auth.Request")
def test_login_endpoint_redirect_uri_dev(
    mock_request, mock_authorize_redirect, mock_settings
):
    mock_request.url_for.return_value = URL("http://testserver/auth/callback")
    mock_settings.is_production = False
    redirect_url = "https://accounts.google.com/o/oauth2/v2/auth"
    mock_authorize_redirect.return_value = RedirectResponse(url=redirect_url)
    # Make a test request to the login endpoint
    response = client.get("/auth/login", follow_redirects=False)

    # assert the call is successful
    mock_authorize_redirect.assert_called_once_with(
        ANY, URL("http://testserver/auth/callback")
    )
    assert response.status_code in (302, 307)


# Test the auth endpoint
def test_callback_endpoint():
    response = client.get("/auth/callback")
    assert response.status_code == 200
    assert "http://testserver/auth/callback" in str(response.url)


@pytest.mark.asyncio
async def test_auth_callback_oauth_error():
    """Test handling of OAuth errors during callback"""
    with patch(
        "api.routes.auth.oauth.google.authorize_access_token", new_callable=AsyncMock
    ) as mock_auth:
        mock_auth.side_effect = OAuthError("test_error", "error_description")
        response = client.get("/auth/callback")
        assert response.status_code == 200
        assert "OAuth Error" in response.text
        assert "test_error" in response.text


# Test the user endpoint, logged in
@patch("api.routes.auth.Request.session", new_callable=PropertyMock)
def test_user_route_logged_in(mock_session):
    # Mock the session property to return a dictionary with our test data
    mock_session.return_value = {"user": {"given_name": "FirstName"}}

    # Make the request to the /auth/me endpoint
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json() == {"name": "FirstName"}


# Test the user endpoing, not logged in
def test_user_endpoint_with_no_logged_in_user():
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json() == {"error": "Not logged in"}


@patch("api.routes.auth.settings")
@pytest.mark.asyncio
async def test_login_rate_limiting(mock_settings):
    mock_settings.is_production = False
    await rate_limiting_helper(
        app=test_app,
        endpoint="/auth/login",
        request_limit=5,
        expected_status=302,
    )


@pytest.mark.asyncio
async def test_auth_rate_limiting():
    """Test rate limiting on the /auth/callback endpoint."""
    with patch(
        "api.routes.auth.oauth.google.authorize_access_token",
        new_callable=AsyncMock,
    ) as mock_auth:
        mock_auth.return_value = {
            "userinfo": {"name": "Test User", "email": "test@test.com"}
        }

        await rate_limiting_helper(
            app=test_app,
            endpoint="/auth/callback",
            request_limit=5,
            expected_status=307,
        )


@pytest.mark.asyncio
async def test_user_rate_limiting():
    await rate_limiting_helper(
        app=test_app,
        endpoint="/auth/me",
        request_limit=10,
        expected_status=200,
    )

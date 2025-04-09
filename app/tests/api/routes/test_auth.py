from unittest.mock import PropertyMock, patch, MagicMock, ANY
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from starlette.datastructures import URL
from server import bot_middleware
from api.routes import auth

auth_router = auth.router


def create_test_app():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")
    app.add_middleware(bot_middleware.BotMiddleware, bot=MagicMock())
    app.include_router(auth_router)

    @app.get("/auth/callback", name="auth")
    async def auth_callback():
        return {"message": "This is a placeholder"}

    return app


test_app = create_test_app()
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
    mock_settings.is_production = True
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

# # Test the login endpoing that does not convert the redirect uri
# @patch("api.routes.auth.settings")
# @patch("authlib.integrations.starlette_client.StarletteOAuth2App.authorize_redirect")
# @patch("api.routes.auth.Request")
# def test_login_endpoint_redirect_uri_dev(
#     mock_request, mock_authorize_redirect, mock_settings
# ):
#     # Setup the mock to simulate dev environment
#     mock_request.url_for.return_value = URL("https://testserver/auth/callback")
#     mock_settings.is_production = True
#     redirect_url = "https://accounts.google.com/o/oauth2/v2/auth"
#     mock_authorize_redirect.return_value = RedirectResponse(url=redirect_url)

#     # Make a test request to the login endpoint
#     response = client.get("/auth/login", follow_redirects=False)

#     # assert the call is successful
#     assert response.status_code in (302, 307)

#     # Check that the redirect_uri is not converted to https
#     mock_authorize_redirect.assert_called_once_with(
#         ANY, "http://testserver/auth/callback"
#     )


# Test the auth endpoint
def test_callback_endpoint():
    response = client.get("/auth/callback")
    assert response.status_code == 200
    assert "http://testserver/auth/callback" in str(response.url)


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

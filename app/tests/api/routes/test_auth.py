import urllib.parse
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from server import bot_middleware, server
from api.routes.auth import router as auth_router

test_app = server.handler
test_app.add_middleware(bot_middleware.BotMiddleware, bot=MagicMock())

test_app.include_router(auth_router)
client = TestClient(test_app)


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
@patch("api.routes.auth.settings")
def test_login_endpoint_redirect_uri_prod(mock_settings):
    # Make a test request to the login endpoint
    mock_settings.is_production = True
    response = client.get("/login")

    # assert the call is successful
    assert response.status_code == 200

    # Set up the expected redirect_uri
    redirect_uri = urllib.parse.quote_plus("http://testserver/callback")
    # Convert to https for production
    redirect_uri = redirect_uri.__str__().replace("http", "https")

    # assert that the response url we get from the login endpoint contains the redirect_uri replaced with https
    assert response.url.__str__().__contains__("redirect_uri=" + redirect_uri)


# Test the login endpoing that does not convert the redirect uri
@patch("api.routes.auth.settings")
def test_login_endpoint_redirect_uri_dev(mock_settings):
    # Setup the mock to simulate dev environment
    mock_settings.is_production = False

    # Make a test request to the login endpoint
    response = client.get("/login")

    # assert the call is successful
    assert response.status_code == 200

    # Set up the expected redirect_uri (without https conversion for dev)
    redirect_uri = urllib.parse.quote_plus("http://testserver/callback")

    # assert that the response url we get from the login endpoint contains the redirect_uri is not replaced with https
    assert response.url.__str__().__contains__("redirect_uri=" + redirect_uri)


# Test the auth endpoint
def test_callback_endpoint():
    response = client.get("/callback")
    assert response.status_code == 200
    assert "http://testserver/callback" in str(response.url)


# Test the user endpoint, logged in
def test_user_route_logged_in():
    # Simulate a logged-in session by creating a mock request with session data
    session_data = {"user": {"given_name": "FirstName"}}
    headers = {"Cookie": f"session={session_data}"}
    response = client.get("/me", headers=headers)
    assert response.status_code == 200


# Test the user endpoing, not logged in
def test_user_endpoint_with_no_logged_in_user():
    response = client.get("/me")
    assert response.status_code == 200
    assert response.json() == {"error": "Not logged in"}

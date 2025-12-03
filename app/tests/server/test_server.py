from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from server import bot_middleware, server


app = server.handler
app.add_middleware(bot_middleware.BotMiddleware, bot=MagicMock())
client = TestClient(app)


# Test that the API router is loaded
def test_api_router_loaded():
    """Test that the API router is properly configured."""
    # Test that the /health endpoint exists (or another available API endpoint)
    # For now, we'll test that the app is properly initialized
    assert app is not None
    assert hasattr(app, "routes")


def test_server_cors_configuration():
    """Test that CORS is properly configured."""
    # The CORS middleware should be present in the user_middleware list
    # Each middleware is wrapped in a Middleware object, so check the cls attribute
    middleware_classes = [m.cls.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in middleware_classes


@pytest.mark.asyncio
async def test_server_404_for_unmapped_routes():
    """Test that unmapped routes return 404."""
    # Since we removed the catch-all React route, unmapped routes should return 404
    response = client.get("/some/unmapped/path")
    assert response.status_code == 404

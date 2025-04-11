from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient
from server import bot_middleware, server


app = server.handler
app.add_middleware(bot_middleware.BotMiddleware, bot=MagicMock())
client = TestClient(app)


# Unit test the react app
def test_react_app():
    # test the react app
    response = client.get("/some/path")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_react_app_rate_limiting():
    # Create a custom transport to mount the ASGI app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Make 20 requests to the react_app endpoint
        for _ in range(20):
            response = await client.get("/some-path")
            assert response.status_code == 200

        # The 21th request should be rate limited
        response = await client.get("/some-path")
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}

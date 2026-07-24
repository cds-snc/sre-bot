from unittest.mock import Mock

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from api.routes.system import router as system_router
from infrastructure.security import rate_limiter as rate_limits


@pytest.mark.asyncio
async def test_rate_limit_handler():
    # Create a mock request
    mock_request = Mock(spec=Request)

    # Create a mock exception
    mock_exception = Mock(spec=RateLimitExceeded)

    # Call the handler function
    response = await rate_limits._rate_limit_handler(mock_request, mock_exception)

    # Assert the response is a JSONResponse
    assert isinstance(response, JSONResponse)

    # Assert the status code is 429
    assert response.status_code == 429

    # Assert the content of the response
    assert response.body.decode("utf-8") == '{"message":"Rate limit exceeded"}'


@pytest.mark.asyncio
async def test_system_endpoint_rate_limiting():
    """Integration Test to ensure the rate limiting is enforced on the system endpoint, using the /version route as an example."""
    rate_limits.get_limiter.cache_clear()

    app = FastAPI()
    rate_limits.setup_rate_limiter(app)
    app.include_router(system_router)

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Make requests up to the limit
        for _ in range(50):
            response = await client.get("/version")
            assert response.status_code == 200

        # Verify rate limit is enforced
        response = await client.get("/version")
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}


@pytest.mark.asyncio
async def test_rate_limited_regardless_of_arbitrary_headers():
    """Integration test proving arbitrary client headers do not bypass the default rate limit."""
    rate_limits.get_limiter.cache_clear()

    app = FastAPI()
    rate_limits.setup_rate_limiter(app)
    app.include_router(system_router)

    transport = httpx.ASGITransport(app=app)

    legacy_header_name = "-".join(["X", "Sentinel", "Source"])
    headers = {
        legacy_header_name: "trusted",
        "X-Another-Header": "value",
        "X-Forwarded-For": "198.51.100.10",
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(50):
            response = await client.get("/version", headers=headers)
            assert response.status_code == 200

        response = await client.get("/version", headers=headers)
        assert response.status_code == 429
        assert response.json() == {"message": "Rate limit exceeded"}

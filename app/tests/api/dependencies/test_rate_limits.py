from unittest.mock import Mock, patch
import pytest
import httpx
from fastapi import Request, FastAPI
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from api.dependencies import rate_limits
from api.routes.system import router as system_router


def test_header_exists_and_not_empty():
    # Create a mock request with the header 'X-Sentinel-Source'
    mock_request = Mock(spec=Request)
    mock_request.headers = {"X-Sentinel-Source": "some_value"}

    # Call the function
    result = rate_limits.sentinel_key_func(mock_request)

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
        result = rate_limits.sentinel_key_func(mock_request)
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
        result = rate_limits.sentinel_key_func(mock_request)

    # Assert that the result is the IP address (rate limiting applied)
    assert result == "192.168.1.1"


@pytest.mark.asyncio
async def test_rate_limit_handler():
    # Create a mock request
    mock_request = Mock(spec=Request)

    # Create a mock exception
    mock_exception = Mock(spec=RateLimitExceeded)

    # Call the handler function
    response = await rate_limits.rate_limit_handler(mock_request, mock_exception)

    # Assert the response is a JSONResponse
    assert isinstance(response, JSONResponse)

    # Assert the status code is 429
    assert response.status_code == 429

    # Assert the content of the response
    assert response.body.decode("utf-8") == '{"message":"Rate limit exceeded"}'


@pytest.mark.asyncio
async def test_system_endpoint_rate_limiting():
    """Integration Test to ensure the rate limiting is enforced on the system endpoint, using the /version route as an example."""
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

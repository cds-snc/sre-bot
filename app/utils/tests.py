from typing import Optional

import httpx
from fastapi import FastAPI


def create_test_app(routers, middlewares=None) -> FastAPI:
    """
    Create a FastAPI test application with the given router and middlewares.

    Args:
        router: The router to include in the app.
        middlewares: Optional list of (middleware_class, config_dict) tuples.

    Returns:
        FastAPI: A configured FastAPI application.

    Example:
        app = create_test_app([router1, router2], middlewares=[(MiddlewareClass, config_dict)])
    """
    # Create a fresh app
    app = FastAPI()

    # Setup rate limiting
    from api.dependencies.rate_limits import setup_rate_limiter

    setup_rate_limiter(app)

    # Add any additional middlewares
    if middlewares:
        for middleware_class, middleware_config in middlewares:
            app.add_middleware(middleware_class, **middleware_config)

    # Include the router
    if not isinstance(routers, list):
        routers = [routers]
    for router in routers:
        app.include_router(router)

    return app


async def rate_limiting_helper(
    app,
    endpoint: str,
    request_limit: int,
    method: str = "get",
    expected_status: int = 200,
    headers: Optional[dict] = None,
):
    """
    Helper function to test rate limiting for an endpoint.

    Args:
        app: The FastAPI app instance.
        endpoint: The endpoint to test.
        request_limit: Number of requests allowed before rate limiting.
        method: HTTP method to use (e.g., "get", "post").
        headers: Optional headers to include in the requests.
        expected_status: Expected status code for successful requests.
    """
    transport = httpx.ASGITransport(app=app)
    headers = headers or {}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        http_method = getattr(client, method.lower())

        # Make requests up to the limit
        for i in range(request_limit):
            response = await http_method(endpoint, headers=headers)
            assert (
                response.status_code == expected_status
            ), f"Request {i+1} failed with status {response.status_code}"

        # The next request should be rate limited
        response = await http_method(endpoint, headers=headers)
        assert response.status_code == 429, "Expected rate limiting to trigger"
        assert response.json() == {"message": "Rate limit exceeded"}

"""Unit tests for server.body_size_middleware module.

Oversized webhook bodies must be rejected before reaching the route handler.
These tests exercise MaxBodySizeMiddleware.dispatch() in isolation, mirroring
the MagicMock-request/AsyncMock-call_next style used by test_bot_middleware.py.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from server.body_size_middleware import MaxBodySizeMiddleware


@pytest.mark.unit
async def test_max_body_size_middleware_rejects_oversized_hook_request():
    """An oversized /hook/... request should short-circuit to 413 without calling call_next."""
    app = MagicMock()
    middleware = MaxBodySizeMiddleware(app, max_bytes=1024)
    request = MagicMock()
    request.url.path = "/hook/some-webhook-id"
    request.headers = {"content-length": "2048"}
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    call_next.assert_not_called()
    assert response.status_code == 413
    assert json.loads(response.body) == {"detail": "Request body too large"}


@pytest.mark.unit
async def test_max_body_size_middleware_allows_request_under_cap():
    """A /hook/... request under the cap should call_next and return its response."""
    app = MagicMock()
    middleware = MaxBodySizeMiddleware(app, max_bytes=1024)
    request = MagicMock()
    request.url.path = "/hook/some-webhook-id"
    request.headers = {"content-length": "100"}
    call_next = AsyncMock()
    expected_response = MagicMock(status_code=200)
    call_next.return_value = expected_response

    response = await middleware.dispatch(request, call_next)

    call_next.assert_called_once_with(request)
    assert response is expected_response


@pytest.mark.unit
async def test_max_body_size_middleware_allows_request_at_exact_cap():
    """A body exactly at max_bytes should be allowed through (boundary case)."""
    app = MagicMock()
    middleware = MaxBodySizeMiddleware(app, max_bytes=1024)
    request = MagicMock()
    request.url.path = "/hook/some-webhook-id"
    request.headers = {"content-length": "1024"}
    call_next = AsyncMock()
    expected_response = MagicMock(status_code=200)
    call_next.return_value = expected_response

    response = await middleware.dispatch(request, call_next)

    call_next.assert_called_once_with(request)
    assert response is expected_response


@pytest.mark.unit
async def test_max_body_size_middleware_rejects_request_one_byte_over_cap():
    """A body one byte over max_bytes should be rejected (boundary case)."""
    app = MagicMock()
    middleware = MaxBodySizeMiddleware(app, max_bytes=1024)
    request = MagicMock()
    request.url.path = "/hook/some-webhook-id"
    request.headers = {"content-length": "1025"}
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    call_next.assert_not_called()
    assert response.status_code == 413


@pytest.mark.unit
async def test_max_body_size_middleware_ignores_non_hook_paths():
    """A request outside the webhook path prefixes is never capped, regardless of size."""
    app = MagicMock()
    middleware = MaxBodySizeMiddleware(app, max_bytes=1024)
    request = MagicMock()
    request.url.path = "/api/v1/groups"
    request.headers = {"content-length": "999999999"}
    call_next = AsyncMock()
    expected_response = MagicMock(status_code=200)
    call_next.return_value = expected_response

    response = await middleware.dispatch(request, call_next)

    call_next.assert_called_once_with(request)
    assert response is expected_response


@pytest.mark.unit
async def test_max_body_size_middleware_missing_content_length_falls_through():
    """A missing Content-Length header should fail open to call_next, not raise."""
    app = MagicMock()
    middleware = MaxBodySizeMiddleware(app, max_bytes=1024)
    request = MagicMock()
    request.url.path = "/hook/some-webhook-id"
    request.headers = {}
    call_next = AsyncMock()
    expected_response = MagicMock(status_code=200)
    call_next.return_value = expected_response

    response = await middleware.dispatch(request, call_next)

    call_next.assert_called_once_with(request)
    assert response is expected_response


@pytest.mark.unit
async def test_max_body_size_middleware_malformed_content_length_falls_through():
    """A non-integer Content-Length header should fail open to call_next, not raise."""
    app = MagicMock()
    middleware = MaxBodySizeMiddleware(app, max_bytes=1024)
    request = MagicMock()
    request.url.path = "/hook/some-webhook-id"
    request.headers = {"content-length": "not-a-number"}
    call_next = AsyncMock()
    expected_response = MagicMock(status_code=200)
    call_next.return_value = expected_response

    response = await middleware.dispatch(request, call_next)

    call_next.assert_called_once_with(request)
    assert response is expected_response

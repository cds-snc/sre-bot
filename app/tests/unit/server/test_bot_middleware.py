"""Unit tests for server.bot_middleware module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from server.bot_middleware import BotMiddleware


@pytest.mark.unit
async def test_bot_middleware_stores_bot_in_request_state():
    """Test that BotMiddleware stores bot in request state."""
    # Arrange
    app = MagicMock()
    bot = MagicMock()
    middleware = BotMiddleware(app, bot)
    request = MagicMock()
    request.state = MagicMock()
    call_next = AsyncMock()
    call_next.return_value = MagicMock(status_code=200)

    # Act
    response = await middleware.dispatch(request, call_next)

    # Assert
    assert request.state.bot == bot
    assert response.status_code == 200


@pytest.mark.unit
async def test_bot_middleware_calls_next_handler():
    """Test that BotMiddleware invokes the next handler."""
    # Arrange
    app = MagicMock()
    bot = MagicMock()
    middleware = BotMiddleware(app, bot)
    request = MagicMock()
    request.state = MagicMock()
    call_next = AsyncMock()
    expected_response = MagicMock(status_code=200)
    call_next.return_value = expected_response

    # Act
    response = await middleware.dispatch(request, call_next)

    # Assert
    call_next.assert_called_once_with(request)
    assert response == expected_response


@pytest.mark.unit
async def test_bot_middleware_preserves_response_from_next():
    """Test that BotMiddleware returns response from next handler unchanged."""
    # Arrange
    app = MagicMock()
    bot = MagicMock()
    middleware = BotMiddleware(app, bot)
    request = MagicMock()
    request.state = MagicMock()
    call_next = AsyncMock()
    expected_response = MagicMock(
        status_code=201, headers={"X-Custom": "header"}, body=b"test"
    )
    call_next.return_value = expected_response

    # Act
    response = await middleware.dispatch(request, call_next)

    # Assert
    assert response == expected_response
    assert response.status_code == 201
    assert response.headers["X-Custom"] == "header"

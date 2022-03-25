from server.bot_middleware import BotMiddleware

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_bot_middleware_dispatch():
    app = MagicMock()
    bot = MagicMock()
    call_next = AsyncMock()
    middleware = BotMiddleware(app, bot)
    assert middleware.bot == bot
    assert await middleware.dispatch(MagicMock(), call_next) == call_next.return_value

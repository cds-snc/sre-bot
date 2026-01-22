from starlette.middleware.base import BaseHTTPMiddleware

from infrastructure.services import get_platform_service


class BotMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, bot=None):
        super().__init__(app)
        self.bot = bot

    async def dispatch(self, request, call_next):
        # Lazily get bot from platform provider if not set at init
        if self.bot is None:
            try:
                platform_service = get_platform_service()
                slack_provider = platform_service.get_provider("slack")
                if slack_provider and slack_provider.app:
                    self.bot = slack_provider.app
            except Exception:
                pass  # Bot not available, continue without it

        request.state.bot = self.bot
        response = await call_next(request)
        return response

from starlette.middleware.base import BaseHTTPMiddleware


class BotMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, bot):
        super().__init__(app)
        self.bot = bot

    async def dispatch(self, request, call_next):
        request.state.bot = self.bot
        response = await call_next(request)
        return response

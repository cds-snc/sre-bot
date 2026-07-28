from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject oversized webhook requests early using the Content-Length header."""

    def __init__(
        self,
        app,
        max_bytes: int,
        path_prefixes: tuple[str, ...] = ("/hook/", "/api/v1/hook/"),
    ):
        super().__init__(app)
        self.max_bytes = max_bytes
        self.path_prefixes = path_prefixes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith(self.path_prefixes):
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    content_length_bytes = int(content_length)
                except ValueError:
                    content_length_bytes = None

                if content_length_bytes is not None and content_length_bytes > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large"},
                    )

        return await call_next(request)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sns_message_validator import SNSMessageValidator  # type: ignore

from api.router import api_router
from infrastructure.configuration.app import get_app_settings
from infrastructure.security import setup_rate_limiter
from infrastructure.security.settings import get_security_settings
from server.body_size_middleware import MaxBodySizeMiddleware
from server.lifespan import lifespan

sns_message_validator = SNSMessageValidator()
app_settings = get_app_settings()
security_settings = get_security_settings()

handler = FastAPI(lifespan=lifespan)
setup_rate_limiter(handler)


class ConfigurationError(Exception):
    """Custom exception for configuration errors."""


handler.add_middleware(
    CORSMiddleware,
    allow_origins=security_settings.CORS_ALLOWED_ORIGINS,
    # Bearer tokens travel in the Authorization header; no cookie or browser credential is needed.
    allow_credentials=False,
    allow_methods=security_settings.CORS_ALLOWED_METHODS,
    allow_headers=security_settings.CORS_ALLOWED_HEADERS,
)
handler.add_middleware(
    MaxBodySizeMiddleware,
    max_bytes=app_settings.WEBHOOK_MAX_BODY_BYTES,
)

handler.include_router(api_router)

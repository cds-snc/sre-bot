from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sns_message_validator import SNSMessageValidator  # type: ignore

from api.router import api_router
from infrastructure.configuration.app import get_app_settings
from infrastructure.security import setup_rate_limiter
from server.lifespan import lifespan

sns_message_validator = SNSMessageValidator()
app_settings = get_app_settings()

handler = FastAPI(lifespan=lifespan)
setup_rate_limiter(handler)


class ConfigurationError(Exception):
    """Custom exception for configuration errors."""


handler.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=app_settings.CORS_ALLOWED_METHODS,
    allow_headers=app_settings.CORS_ALLOWED_HEADERS,
)

handler.include_router(api_router)

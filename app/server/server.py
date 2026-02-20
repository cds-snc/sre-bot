from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sns_message_validator import SNSMessageValidator  # type: ignore

from api.router import api_router
from api.dependencies.rate_limits import setup_rate_limiter, get_limiter
from infrastructure.services import get_settings
from server.lifespan import lifespan

sns_message_validator = SNSMessageValidator()
settings = get_settings()


handler = FastAPI(lifespan=lifespan)
setup_rate_limiter(handler)
limiter = get_limiter()


class ConfigurationError(Exception):
    """Custom exception for configuration errors."""


allow_origins = (
    ["*"]
    if settings.is_production
    else [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
)
handler.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

handler.include_router(api_router)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sns_message_validator import SNSMessageValidator  # type: ignore

from api.router import api_router
from infrastructure.security import setup_rate_limiter
from server.body_size_middleware import MaxBodySizeMiddleware
from server.configuration import load_host_configuration
from server.lifespan import build_lifespan

sns_message_validator = SNSMessageValidator()


class ConfigurationError(Exception):
    """Custom exception for configuration errors."""


def create_app() -> FastAPI:
    """Build the application: run the configuration phase once, then wire middleware and routes.

    A missing ENVIRONMENT, an unreadable configuration file or an invalid host slice
    raises here, before any middleware is built. Start with ``uvicorn --factory``.
    """
    configuration = load_host_configuration()
    security_settings = configuration.security

    app = FastAPI(lifespan=build_lifespan(configuration))
    setup_rate_limiter(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=security_settings.cors_allowed_origins,
        # Bearer tokens travel in the Authorization header; no cookie or browser credential is needed.
        allow_credentials=False,
        allow_methods=security_settings.cors_allowed_methods,
        allow_headers=security_settings.cors_allowed_headers,
    )
    app.add_middleware(
        MaxBodySizeMiddleware,
        max_bytes=configuration.server.webhook_max_body_bytes,
    )
    app.include_router(api_router)
    return app

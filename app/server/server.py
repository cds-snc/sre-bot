import os
from core.config import settings
from core.logging import get_module_logger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sns_message_validator import SNSMessageValidator  # type: ignore
from starlette.middleware.sessions import SessionMiddleware

from api.router import api_router
from api.dependencies.rate_limits import setup_rate_limiter, get_limiter

SECRET_KEY = settings.server.SECRET_KEY

logger = get_module_logger()
sns_message_validator = SNSMessageValidator()


handler = FastAPI()
setup_rate_limiter(handler)
limiter = get_limiter()


# Set up the templates directory and static folder for the frontend with the build folder for production
if os.path.exists("../frontend/build"):
    # Sets the templates directory to the React build folder
    templates = Jinja2Templates(directory="../frontend/build")
    # Mounts the static folder within the build forlder to the /static route.
    handler.mount(
        "/static", StaticFiles(directory="../frontend/build/static"), "static"
    )
else:
    # Sets the templates directory to the React public folder for local dev
    templates = Jinja2Templates(directory="../frontend/public")
    handler.mount("/static", StaticFiles(directory="../frontend/public"), "static")


class ConfigurationError(Exception):
    """Custom exception for configuration errors."""


if settings.is_production:
    if SECRET_KEY is None:
        raise ConfigurationError("Missing SECRET_KEY in production")
else:
    if SECRET_KEY is None:
        SECRET_KEY = "dev-secret-key"

# add a session middleware to the app
handler.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

allow_origins = (
    ["*"]
    if settings.is_production
    else [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
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


# Defines a route handler for `/*` essentially.
@handler.get("/{rest_of_path:path}")
@limiter.limit("20/minute")
async def react_app(request: Request, rest_of_path: str):
    return templates.TemplateResponse("index.html", {"request": request})

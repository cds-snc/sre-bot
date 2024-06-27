import json
import logging
import os
import requests

from starlette.config import Config
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Extra
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from models import webhooks
from server.utils import log_ops_message, get_user_email_from_request
from integrations.sentinel import log_to_sentinel
from integrations import maxmind
from server.event_handlers import aws
from sns_message_validator import (
    SNSMessageValidator,
    InvalidMessageTypeException,
    InvalidCertURLException,
    InvalidSignatureVersionException,
    SignatureVerificationFailureException,
)
from functools import wraps
from fastapi import Depends, status
from datetime import datetime, timezone, timedelta
from integrations.aws.organizations import get_active_account_names
from modules.aws.aws import request_aws_account_access

logging.basicConfig(level=logging.INFO)
sns_message_validator = SNSMessageValidator()


class WebhookPayload(BaseModel):
    channel: str | None = None
    text: str | None = None
    as_user: bool | None = None
    attachments: str | list | None = []
    blocks: str | list | None = []
    thread_ts: str | None = None
    reply_broadcast: bool | None = None
    unfurl_links: bool | None = None
    unfurl_media: bool | None = None
    icon_emoji: str | None = None
    icon_url: str | None = None
    mrkdwn: bool | None = None
    link_names: bool | None = None
    username: str | None = None
    parse: str | None = None

    class Config:
        extra = Extra.forbid


class AwsSnsPayload(BaseModel):
    Type: str | None = None
    MessageId: str | None = None
    Token: str | None = None
    TopicArn: str | None = None
    Message: str | None = None
    SubscribeURL: str | None = None
    Timestamp: str | None = None
    SignatureVersion: str | None = None
    Signature: str | None = None
    SigningCertURL: str | None = None
    Subject: str | None = None
    UnsubscribeURL: str | None = None

    class Config:
        extra = Extra.forbid


class AccessRequest(BaseModel):
    """
    AccessRequest represents a request for access to an AWS account.

    This class defines the schema for an access request, which includes the following fields:
    - account: The name of the AWS account to which access is requested.
    - reason: The reason for requesting access to the AWS account.
    - startDate: The start date and time for the requested access period.
    - endDate: The end date and time for the requested access period.
    """

    account: str
    reason: str
    startDate: datetime
    endDate: datetime


# initialize the limiter
limiter = Limiter(key_func=get_remote_address)

handler = FastAPI()

# add the limiter to the handler
handler.state.limiter = limiter
handler.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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


# OAuth settings
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID") or None
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET") or None
if GOOGLE_CLIENT_ID is None or GOOGLE_CLIENT_SECRET is None:
    raise Exception("Missing env variables")

SECRET_KEY = os.environ.get("SESSION_SECRET_KEY") or None
if SECRET_KEY is None:
    raise Exception("Missing env variables")

# add a session middleware to the app
handler.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

handler.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Set up Google OAuth
config_data = {
    "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
}
starlette_config = Config(environ=config_data)
oauth = OAuth(starlette_config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


def sentinel_key_func(request: Request):
    # Check if the 'X-Sentinel-Source' exists and is not empty
    if request.headers.get("X-Sentinel-Source"):
        return None  # Skip rate limiting if the header exists and is not empty
    return get_remote_address(request)


# Rate limit handler for RateLimitExceeded exceptions
@handler.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"message": "Rate limit exceeded"})


# Logout route. If you log out of the application, you will be redirected to the homepage
@handler.route("/logout")
@limiter.limit("5/minute")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/")


# Login route. You will be redirected to the google login page
@handler.get("/login")
@limiter.limit("5/minute")
async def login(request: Request):
    # get the current environment (ie dev or prod)
    environment = os.environ.get("ENVIRONMENT")
    # this is the route that will be called after the user logs in
    redirect_uri = request.url_for(
        "auth",
    )
    # if the environment is production, then make sure to replace the http to https, else don't do anything (ie if you are in dev)
    if environment == "prod":
        redirect_uri = redirect_uri.__str__().replace("http", "https")

    return await oauth.google.authorize_redirect(request, redirect_uri)


# Authenticate route. This is the route that will be called after the user logs in and you are redirected to the /home page
@handler.route("/auth")
@limiter.limit("5/minute")
async def auth(request: Request):
    try:
        access_token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f"<h1>OAuth Error</h1><pre>{error.error}</pre>")
    user_data = access_token.get("userinfo")
    if user_data:
        request.session["user"] = dict(user_data)
    return RedirectResponse(url="/")


# User route. Returns the user's first name that is currently logged into the application
@handler.route("/user")
@limiter.limit("5/minute")
async def user(request: Request):
    user = request.session.get("user")
    if user:
        return JSONResponse({"name": user.get("given_name")})
    else:
        return JSONResponse({"error": "Not logged in"})


def get_current_user(request: Request):
    """
    Retrieves the currently logged-in user from the session.
    Args:
        request (Request): The HTTP request object containing session information.
    Returns:
        dict: The user information if the user is logged in.
    Raises:
        HTTPException: If the user is not authenticated.
    """
    # Retrieve the 'user' from the session stored in the request
    user = request.session.get("user")

    # If there is no 'user' in the session, raise an HTTP 401 Unauthorized exception
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Google login"},
        )
    return user


def login_required(route):
    """
    A decorator to ensure that the user is logged in before accessing the route.
    Args:
        route (function): The route function that requires login.
    Returns:
        function: The decorated route function with login check.
    """

    @wraps(route)
    async def decorated_route(*args, **kwargs):
        """
        The decorated route function that includes login check.
        Args:
            *args: Variable length argument list for the route function.
            **kwargs: Arbitrary keyword arguments for the route function.
        Returns:
            The result of the original route function if the user is logged in.
        """
        # Get the current request from the arguments
        request = kwargs.get("request")
        if request:
            # Check if the user is logged in
            user = get_current_user(request)  # noqa: F841
        # Call the original route function and return its result
        return await route(*args, **kwargs)

    # Return the decorated route function
    return decorated_route


@handler.post("/request_access")
@limiter.limit("10/minute")
@login_required
async def create_access_request(
    request: Request,
    access_request: AccessRequest,
    use: dict = Depends(get_current_user),
):
    """
    Endpoint to create an AWS access request.

    This asynchronous function handles POST requests to the "/request_access" endpoint. It performs several validation checks on the provided access request data and then attempts to create an access request in the system. The function is protected by a rate limiter and requires user authentication.

    Args:
        request (Request): The FastAPI request object.
        access_request (AccessRequest): The data model representing the access request.
        use (dict, optional): Dependency that provides the current user context. Defaults to Depends(get_current_user).

    Raises:
        HTTPException: If any validation checks fail or if the request creation fails.

    Returns:
        dict: A dictionary containing a success message and the access request data if the request is successfully created.
    """
    # Check if the account and reason fields are provided
    if not access_request.account or not access_request.reason:
        raise HTTPException(status_code=400, detail="Account and reason are required")

    # Check if the start date is at least 5 minutes in the future
    if (
        access_request.startDate.replace(tzinfo=timezone.utc) + timedelta(minutes=5)
    ) < datetime.now().replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="Start date must be in the future")

    # Check if the end date is after the start date
    if access_request.endDate.replace(tzinfo=timezone.utc) <= access_request.startDate:
        raise HTTPException(status_code=400, detail="End date must be after start date")

    # If the request is for more than 24 hours in the future, this is not allowed
    if access_request.endDate.replace(tzinfo=timezone.utc) > datetime.now().replace(
        tzinfo=timezone.utc
    ) + timedelta(days=1):
        raise HTTPException(
            status_code=400,
            detail="The access request cannot be for more than 24 hours",
        )

    # get the user email from the request
    user_email = get_user_email_from_request(request)

    # Store the request in the database
    response = request_aws_account_access(
        access_request.account,
        access_request.reason,
        access_request.startDate,
        access_request.endDate,
        user_email,
        "read",
    )
    # Return a success message and the access request data if the request is created successfully
    if response:
        return {
            "message": "Access request created successfully",
            "data": access_request,
        }
    else:
        # Raise an HTTP 500 error if the request creation fails
        raise HTTPException(status_code=500, detail="Failed to create access request")


# Geolocate route. Returns the country, city, latitude, and longitude of the IP address.
@handler.get("/geolocate/{ip}")
def geolocate(ip):
    reader = maxmind.geolocate(ip)
    if isinstance(reader, str):
        raise HTTPException(status_code=404, detail=reader)
    else:
        country, city, latitude, longitude = reader
        return {
            "country": country,
            "city": city,
            "latitude": latitude,
            "longitude": longitude,
        }


@handler.get("/accounts")
@limiter.limit("5/minute")
@login_required
async def get_accounts(request: Request, user: dict = Depends(get_current_user)):
    """
    Endpoint to retrieve active AWS account names.

    This asynchronous function handles GET requests to the "/accounts" endpoint.
    It retrieves a list of active AWS account names. The function is protected by a rate limiter and requires user authentication.

    Args:
        request (Request): The FastAPI request object.
        user (dict, optional): Dependency that provides the current user context. Defaults to Depends(get_current_user).

    Returns:
        list: A list of active AWS account names.
    """
    return get_active_account_names()


@handler.post("/hook/{id}")
@limiter.limit(
    "30/minute"
)  # since some slack channels use this for alerting, we want to be generous with the rate limiting on this one
def handle_webhook(id: str, payload: WebhookPayload | str, request: Request):
    webhook = webhooks.get_webhook(id)
    if webhook:
        # if the webhook is active, then send forward the response to the webhook
        if webhooks.is_active(id):
            webhooks.increment_invocation_count(id)
            if isinstance(payload, str):
                try:
                    payload = AwsSnsPayload.parse_raw(payload)
                    sns_message_validator.validate_message(message=payload.dict())
                except InvalidMessageTypeException as e:
                    logging.error(e)
                    log_ops_message(
                        request.state.bot.client,
                        f"Invalid message type ```{payload.Type}``` in message: ```{payload}```",
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to parse AWS event message due to {e.__class__.__qualname__}: {e}",
                    )
                except InvalidSignatureVersionException as e:
                    logging.error(e)
                    log_ops_message(
                        request.state.bot.client,
                        f"Unexpected signature version ```{payload.SignatureVersion}``` in message: ```{payload}```",
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to parse AWS event message due to {e.__class__.__qualname__}: {e}",
                    )
                except SignatureVerificationFailureException as e:
                    logging.error(e)
                    log_ops_message(
                        request.state.bot.client,
                        f"Failed to verify signature ```{payload.Signature}``` in message: ```{payload}```",
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to parse AWS event message due to {e.__class__.__qualname__}: {e}",
                    )
                except InvalidCertURLException as e:
                    logging.error(e)
                    log_ops_message(
                        request.state.bot.client,
                        f"Invalid certificate URL ```{payload.SigningCertURL}``` in message: ```{payload}```",
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to parse AWS event message due to {e.__class__.__qualname__}: {e}",
                    )
                except Exception as e:
                    logging.error(e)
                    log_ops_message(
                        request.state.bot.client,
                        f"Error parsing AWS event due to {e.__class__.__qualname__}: ```{payload}```",
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to parse AWS event message due to {e.__class__.__qualname__}: {e}",
                    )
                if payload.Type == "SubscriptionConfirmation":
                    requests.get(payload.SubscribeURL, timeout=60)
                    logging.info(f"Subscribed webhook {id} to topic {payload.TopicArn}")
                    log_ops_message(
                        request.state.bot.client,
                        f"Subscribed webhook {id} to topic {payload.TopicArn}",
                    )
                    return {"ok": True}

                if payload.Type == "UnsubscribeConfirmation":
                    log_ops_message(
                        request.state.bot.client,
                        f"{payload.TopicArn} unsubscribed from webhook {id}",
                    )
                    return {"ok": True}

                if payload.Type == "Notification":
                    blocks = aws.parse(payload, request.state.bot.client)
                    # if we have an empty message, log that we have an empty
                    # message and return without posting to slack
                    if not blocks:
                        logging.info("No blocks to post, returning")
                        return
                    payload = WebhookPayload(blocks=blocks)
            payload.channel = webhook["channel"]["S"]
            payload = append_incident_buttons(payload, id)
            try:
                message = json.loads(payload.json(exclude_none=True))
                request.state.bot.client.api_call("chat.postMessage", json=message)
                log_to_sentinel(
                    "webhook_sent", {"webhook": webhook, "payload": payload.dict()}
                )
                return {"ok": True}
            except Exception as e:
                logging.error(e)
                body = payload.json(exclude_none=True)
                log_ops_message(
                    request.state.bot.client, f"Error posting message: ```{body}```"
                )
                raise HTTPException(status_code=500, detail="Failed to send message")
        else:
            logging.info(f"Webhook id {id} is not active")
            raise HTTPException(status_code=404, detail="Webhook not active")
    else:
        raise HTTPException(status_code=404, detail="Webhook not found")


# Route53 uses this as a healthcheck every 30 seconds and the alb uses this as a checkpoint every 10 seconds.
# As a result, we are giving a generous rate limit of so that we don't run into any issues with the healthchecks
@handler.get("/version")
@limiter.limit("50/minute")
def get_version(request: Request):
    return {"version": os.environ.get("GIT_SHA", "unknown")}


def append_incident_buttons(payload, webhook_id):
    payload.attachments = payload.attachments + [
        {
            "fallback": "Incident",
            "callback_id": "handle_incident_action_buttons",
            "color": "#3AA3E3",
            "attachment_type": "default",
            "actions": [
                {
                    "name": "call-incident",
                    "text": "🎉   Call incident ",
                    "type": "button",
                    "value": payload.text,
                    "style": "primary",
                },
                {
                    "name": "ignore-incident",
                    "text": "🙈   Acknowledge and ignore",
                    "type": "button",
                    "value": webhook_id,
                    "style": "default",
                },
            ],
        }
    ]
    return payload


# Defines a route handler for `/*` essentially.
@handler.get("/{rest_of_path:path}")
@limiter.limit("20/minute")
async def react_app(request: Request, rest_of_path: str):
    return templates.TemplateResponse("index.html", {"request": request})

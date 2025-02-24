import json
import logging
import os
import requests  # type: ignore

from starlette.config import Config
from authlib.integrations.starlette_client import OAuth, OAuthError  # type: ignore
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from modules.slack import webhooks
from models.webhooks import WebhookPayload, AccessRequest, AwsSnsPayload
from server.utils import (
    log_ops_message,
    create_access_token,
    get_current_user,
    get_user_email_from_request,
)
from integrations.sentinel import log_to_sentinel
from integrations import maxmind
from server.event_handlers import aws
from sns_message_validator import (  # type: ignore
    SNSMessageValidator,
)
from fastapi import Depends
from datetime import datetime, timezone, timedelta
from integrations.aws.organizations import get_active_account_names
from modules.aws.aws import request_aws_account_access
from modules.aws.aws_access_requests import get_active_requests, get_past_requests

logging.basicConfig(level=logging.INFO)
sns_message_validator = SNSMessageValidator()


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
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response


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
        jwt_token = create_access_token(data={"sub": user_data["email"]})
        response = RedirectResponse(url="/")
        response.set_cookie(
            "access_token", jwt_token, httponly=True, secure=True, samesite="Strict"
        )
    return response


# User route. Returns the user's first name that is currently logged into the application
@handler.route("/user")
@limiter.limit("10/minute")
async def user(request: Request):
    user = request.session.get("user")
    if user:
        return JSONResponse({"name": user.get("given_name")})
    else:
        return JSONResponse({"error": "Not logged in"})


@handler.post("/request_access")
@limiter.limit("10/minute")
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


@handler.get("/active_requests")
@limiter.limit("5/minute")
async def get_aws_active_requests(
    request: Request, user: dict = Depends(get_current_user)
):
    """
    Retrieves the active access requests from the database.
    Args:
        request (Request): The HTTP request object.
    Returns:
        list: The list of active access requests.
    """
    return get_active_requests()


@handler.get("/past_requests")
@limiter.limit("5/minute")
async def get_aws_past_requests(
    request: Request, user: dict = Depends(get_current_user)
):
    """
    Retrieves the past access requests from the database.
    Args:
        request (Request): The HTTP request object.
    Returns:
        list: The list of past access requests.
    """
    return get_past_requests()


@handler.post("/hook/{id}")
@limiter.limit(
    "30/minute"
)  # since some slack channels use this for alerting, we want to be generous with the rate limiting on this one
def handle_webhook(
    id: str,
    payload: WebhookPayload | str,
    request: Request,
):
    webhook = webhooks.get_webhook(id)
    webhook_payload = WebhookPayload()
    if webhook:
        hook_type: str = webhook.get("hook_type", {"S": "alert"})["S"]
        # if the webhook is active, then send forward the response to the webhook
        if webhooks.is_active(id):
            webhooks.increment_invocation_count(id)
            if isinstance(payload, str):
                processed_payload = handle_string_payload(payload, request)
                if isinstance(processed_payload, dict):
                    return processed_payload
                else:
                    logging.info(f"Processed payload: {processed_payload}")
                    webhook_payload = processed_payload
            else:
                webhook_payload = payload
            webhook_payload.channel = webhook["channel"]["S"]
            if hook_type == "alert":
                webhook_payload = append_incident_buttons(webhook_payload, id)
            try:
                webhook_payload_parsed = webhook_payload.model_dump(exclude_none=True)
                request.state.bot.client.api_call(
                    "chat.postMessage", json=webhook_payload_parsed
                )
                log_to_sentinel(
                    "webhook_sent",
                    {"webhook": webhook, "payload": webhook_payload_parsed},
                )
                return {"ok": True}
            except Exception as e:
                logging.error(e)
                body = webhook_payload.model_dump(exclude_none=True)
                log_ops_message(
                    request.state.bot.client, f"Error posting message: ```{body}```"
                )
                raise HTTPException(status_code=500, detail="Failed to send message")
        else:
            logging.info(f"Webhook id {id} is not active")
            raise HTTPException(status_code=404, detail="Webhook not active")
    else:
        raise HTTPException(status_code=404, detail="Webhook not found")


def handle_string_payload(
    payload: str,
    request: Request,
) -> WebhookPayload | dict:

    string_payload_type, validated_payload = webhooks.validate_string_payload_type(
        payload
    )
    logging.info(f"String payload type: {string_payload_type}")
    match string_payload_type:
        case "WebhookPayload":
            webhook_payload = WebhookPayload(**validated_payload)
        case "AwsSnsPayload":
            awsSnsPayload = aws.validate_sns_payload(
                AwsSnsPayload(**validated_payload),
                request.state.bot.client,
            )
            if awsSnsPayload.Type == "SubscriptionConfirmation":
                requests.get(awsSnsPayload.SubscribeURL, timeout=60)
                logging.info(
                    f"Subscribed webhook {id} to topic {awsSnsPayload.TopicArn}"
                )
                log_ops_message(
                    request.state.bot.client,
                    f"Subscribed webhook {id} to topic {awsSnsPayload.TopicArn}",
                )
                return {"ok": True}
            if awsSnsPayload.Type == "UnsubscribeConfirmation":
                log_ops_message(
                    request.state.bot.client,
                    f"{awsSnsPayload.TopicArn} unsubscribed from webhook {id}",
                )
                return {"ok": True}
            if awsSnsPayload.Type == "Notification":
                blocks = aws.parse(awsSnsPayload, request.state.bot.client)
                # if we have an empty message, log that we have an empty
                # message and return without posting to slack
                if not blocks:
                    logging.info("No blocks to post, returning")
                    return {"ok": True}
                webhook_payload = WebhookPayload(blocks=blocks)
        case "AccessRequest":
            # Temporary fix for the Access Request payloads
            message = json.dumps(validated_payload)
            webhook_payload = WebhookPayload(text=message)
        case "UpptimePayload":
            # Temporary fix for Upptime payloads
            text = validated_payload.get("text", "")
            header_text = "📈 Web Application Status Changed!"
            blocks = [
                {"type": "section", "text": {"type": "mrkdwn", "text": " "}},
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": f"{header_text}"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{text}",
                    },
                },
            ]
            webhook_payload = WebhookPayload(blocks=blocks)
        case _:
            raise HTTPException(
                status_code=500,
                detail="Invalid payload type. Must be a WebhookPayload object or a recognized string payload type.",
            )
    return WebhookPayload(**webhook_payload.model_dump(exclude_none=True))


# Route53 uses this as a healthcheck every 30 seconds and the alb uses this as a checkpoint every 10 seconds.
# As a result, we are giving a generous rate limit of so that we don't run into any issues with the healthchecks
@handler.get("/version")
@limiter.limit("50/minute")
def get_version(request: Request):
    return {"version": os.environ.get("GIT_SHA", "unknown")}


def append_incident_buttons(payload: WebhookPayload, webhook_id):
    if payload.attachments is None:
        payload.attachments = []
    elif isinstance(payload.attachments, str):
        payload.attachments = [payload.attachments]
    payload.attachments += [
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

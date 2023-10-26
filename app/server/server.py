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
from models import webhooks
from commands.utils import log_ops_message, log_to_sentinel
from integrations import maxmind
from server.event_handlers import aws
from sns_message_validator import (
    SNSMessageValidator,
    InvalidMessageTypeException,
    InvalidCertURLException,
    InvalidSignatureVersionException,
    SignatureVerificationFailureException,
)

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


handler = FastAPI()

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


# Logout route. If you log out of the application, you will be redirected to the homepage
@handler.route("/logout")
async def logout(request: Request):
    request.session.pop("user", None)
    return RedirectResponse(url="/")


# Login route. You will be redirected to the google login page
@handler.get("/login")
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
async def user(request: Request):
    user = request.session.get("user")
    if user:
        return JSONResponse({"name": user.get("given_name")})
    else:
        return JSONResponse({"error": "Not logged in"})


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


@handler.post("/hook/{id}")
def handle_webhook(id: str, payload: WebhookPayload | str, request: Request):
    webhook = webhooks.get_webhook(id)
    if webhook:
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
                # try:
                #     msg = json.loads(payload.Message)
                # except Exception:
                #     msg = payload.Message
                # # if the message is for Notify API secret, unfurl links will be set to false
                # if "API Key with value token=" in msg:
                #     payload.unfurl_links = False

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
        raise HTTPException(status_code=404, detail="Webhook not found")


@handler.get("/version")
def get_version():
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
async def react_app(req: Request, rest_of_path: str):
    return templates.TemplateResponse("index.html", {"request": req})

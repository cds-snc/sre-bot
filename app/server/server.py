import json
import logging
import os
import requests


from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Extra
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

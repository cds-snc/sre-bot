import json
import os
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Extra
from models import webhooks


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


handler = FastAPI()


@handler.post("/hook/{id}")
def handle_webhook(id: str, payload: WebhookPayload, request: Request):
    webhook = webhooks.get_webhook(id)
    if webhook:
        webhooks.increment_invocation_count(id)
        payload.channel = webhook["channel"]["S"]
        payload = append_incident_buttons(payload, id)
        request.state.bot.client.api_call(
            "chat.postMessage", json=json.loads(payload.json(exclude_none=True))
        )
        return {"ok": True}
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

from datetime import datetime
from pydantic import BaseModel


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
        extra = "forbid"


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
        extra = "forbid"


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


class UpptimePayload(BaseModel):
    text: str


class WebhookResult(BaseModel):
    status: str
    action: str | None = None
    payload: WebhookPayload | None = None
    message: str | None = None

    class Config:
        extra = "forbid"

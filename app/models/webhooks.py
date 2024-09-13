import boto3  # type: ignore
import os
import uuid
from datetime import datetime
from pydantic import BaseModel


client = boto3.client(
    "dynamodb",
    endpoint_url=(
        "http://dynamodb-local:8000" if os.environ.get("PREFIX", None) else None
    ),
    region_name="ca-central-1",
)

table = "webhooks"


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


def create_webhook(channel, user_id, name):
    id = str(uuid.uuid4())
    response = client.put_item(
        TableName=table,
        Item={
            "id": {"S": id},
            "channel": {"S": channel},
            "name": {"S": name},
            "created_at": {"S": str(datetime.now())},
            "active": {"BOOL": True},
            "user_id": {"S": user_id},
            "invocation_count": {"N": "0"},
            "acknowledged_count": {"N": "0"},
        },
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        return id
    else:
        return None


def delete_webhook(id):
    response = client.delete_item(TableName=table, Key={"id": {"S": id}})
    return response


def get_webhook(id):
    response = client.get_item(TableName=table, Key={"id": {"S": id}})
    if "Item" in response:
        return response["Item"]
    else:
        return None


def increment_acknowledged_count(id):
    response = client.update_item(
        TableName=table,
        Key={"id": {"S": id}},
        UpdateExpression="SET acknowledged_count = acknowledged_count + :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}},
    )
    return response


def increment_invocation_count(id):
    response = client.update_item(
        TableName=table,
        Key={"id": {"S": id}},
        UpdateExpression="SET invocation_count = invocation_count + :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}},
    )
    return response


def list_all_webhooks():
    response = client.scan(TableName=table, Select="ALL_ATTRIBUTES")
    return response["Items"]


def revoke_webhook(id):
    response = client.update_item(
        TableName=table,
        Key={"id": {"S": id}},
        UpdateExpression="SET active = :active",
        ExpressionAttributeValues={":active": {"BOOL": False}},
    )
    return response


# function to return the status of the webhook (ie if it is active or not). If active, return True, else return False
def is_active(id):
    response = client.get_item(TableName=table, Key={"id": {"S": id}})
    if "Item" in response:
        return response["Item"]["active"]["BOOL"]
    else:
        return False


def toggle_webhook(id):
    response = client.update_item(
        TableName=table,
        Key={"id": {"S": id}},
        UpdateExpression="SET active = :active",
        ExpressionAttributeValues={
            ":active": {"BOOL": not get_webhook(id)["active"]["BOOL"]}
        },
    )
    return response

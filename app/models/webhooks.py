import boto3
import datetime
import os
import uuid

client = boto3.client(
    "dynamodb",
    endpoint_url=(
        "http://dynamodb-local:8000" if os.environ.get("PREFIX", None) else None
    ),
)

table = "webhooks"


def create_webhook(channel, user_id, name):
    id = str(uuid.uuid4())
    response = client.put_item(
        TableName=table,
        Item={
            "id": {"S": id},
            "channel": {"S": channel},
            "name": {"S": name},
            "created_at": {"S": str(datetime.datetime.now())},
            "active": {"BOOL": True},
            "user_id": {"S": user_id},
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
    return response["Item"]


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

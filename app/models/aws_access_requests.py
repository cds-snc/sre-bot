import boto3
import datetime
import os
import uuid

client = boto3.client(
    "dynamodb",
    endpoint_url=(
        "http://dynamodb-local:8000" if os.environ.get("PREFIX", None) else None
    ),
    region_name="ca-central-1",
)

table = "aws_access_requests"


def create_aws_access_request(user_id, account, access_type, rationale):
    id = str(uuid.uuid4())
    response = client.put_item(
        TableName=table,
        Item={
            "id": {"S": id},
            "user_id": {"S": user_id},
            "account": {"S": account},
            "access_type": {"S": access_type},
            "rationale": {"S": rationale},
            "created_at": {"S": str(datetime.datetime.now())},
            "expired": {"BOOL": False},
        },
    )
    return response

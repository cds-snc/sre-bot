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


def already_has_access(account_id, user_id, access_type):
    response = client.query(
        TableName=table,
        KeyConditionExpression="account_id = :account_id and created_at > :created_at",
        ExpressionAttributeValues={
            ":account_id": {"S": account_id},
            ":created_at": {
                "N": str(datetime.datetime.now().timestamp() - (4 * 60 * 60))
            },
        },
    )

    if response["Count"] == 0:
        return False

    for item in response["Items"]:
        if (
            item["user_id"]["S"] == user_id
            and item["access_type"]["S"] == access_type
            and item["expired"]["BOOL"] is False
        ):
            return round(
                (
                    float(item["created_at"]["N"])
                    + (4 * 60 * 60)
                    - datetime.datetime.now().timestamp()
                )
                / 60
            )

    return False


def create_aws_access_request(
    account_id,
    account_name,
    user_id,
    email,
    start_date_time,
    end_date_time,
    access_type,
    rationale,
):
    id = str(uuid.uuid4())
    response = client.put_item(
        TableName=table,
        Item={
            "id": {"S": id},
            "account_id": {"S": account_id},
            "account_name": {"S": account_name},
            "user_id": {"S": user_id},
            "email": {"S": email},
            "access_type": {"S": access_type},
            "rationale": {"S": rationale},
            "start_date_time": {"S": str(start_date_time.timestamp())},
            "end_date_time": {"S": str(end_date_time.timestamp())},
            "created_at": {"N": str(datetime.datetime.now().timestamp())},
            "expired": {"BOOL": False},
        },
    )
    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        return True
    else:
        return False


def expire_request(account_id, created_at):
    response = client.update_item(
        TableName=table,
        Key={
            "account_id": {"S": account_id},
            "created_at": {"N": created_at},
        },
        UpdateExpression="set expired = :expired",
        ExpressionAttributeValues={":expired": {"BOOL": True}},
    )
    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        return True
    else:
        return False


def get_expired_requests():
    response = client.scan(
        TableName=table,
        FilterExpression="expired = :expired and created_at < :created_at",
        ExpressionAttributeValues={
            ":expired": {"BOOL": False},
            ":created_at": {
                "N": str(datetime.datetime.now().timestamp() - (4 * 60 * 60))
            },
        },
    )
    return response.get("Items", [])


def get_active_requests():
    """
    Retrieves active requests from the DynamoDB table.

    This function fetches records where the current time is less than the 'end_date_time' attribute,
    indicating active requests.

    Returns:
        list: A list of active items from the DynamoDB table, or an empty list if none are found.
    """
    # Get the current timestamp
    current_timestamp = datetime.datetime.now().timestamp()

    # Query to get records where current date time is less than end_date_time
    response = client.scan(
        TableName=table,
        FilterExpression="end_date_time > :current_time",
        ExpressionAttributeValues={":current_time": {"S": str(current_timestamp)}},
    )
    return response.get("Items", [])


def get_past_requests():
    """
    Retrieves past requests from the DynamoDB table.

    This function fetches records where the current time is greater than the 'end_date_time' attribute,
    indicating past requests.

    Returns:
        list: A list of past items from the DynamoDB table, or an empty list if none are found.
    """
    # Get the current timestamp
    current_timestamp = datetime.datetime.now().timestamp()

    # Query to get records where current date time is greater than end_date_time
    response = client.scan(
        TableName=table,
        FilterExpression="end_date_time < :current_time",
        ExpressionAttributeValues={":current_time": {"S": str(current_timestamp)}},
    )
    return response.get("Items", [])

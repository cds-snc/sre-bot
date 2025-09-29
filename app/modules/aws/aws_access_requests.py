import datetime
import uuid

import boto3  # type: ignore
from core.config import settings
from integrations.aws import identity_store, organizations, sso_admin
from modules.ops.notifications import log_ops_message
from slack_sdk import WebClient

PREFIX = settings.PREFIX

dynamodb_client = boto3.client(
    "dynamodb",
    endpoint_url=("http://dynamodb-local:8000" if PREFIX != "" else None),
    region_name="ca-central-1",
)

table = "aws_access_requests"


def already_has_access(account_id, user_id, access_type):
    response = dynamodb_client.query(
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
    access_type,
    rationale,
    start_date_time=datetime.datetime.now(),
    end_date_time=datetime.datetime.now() + datetime.timedelta(hours=1),
):
    id = str(uuid.uuid4())
    response = dynamodb_client.put_item(
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
    response = dynamodb_client.update_item(
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
    response = dynamodb_client.scan(
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
    response = dynamodb_client.scan(
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
    response = dynamodb_client.scan(
        TableName=table,
        FilterExpression="end_date_time < :current_time",
        ExpressionAttributeValues={":current_time": {"S": str(current_timestamp)}},
    )
    return response.get("Items", [])


def access_view_handler(ack, body, logger, client: WebClient):
    ack()

    errors = {}

    rationale = body["view"]["state"]["values"]["rationale"]["rationale"]["value"]

    if len(rationale) > 2000:
        errors["rationale"] = "Please use less than 2000 characters"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    user_id = body["user"]["id"]

    user = client.users_info(user=user_id)["user"]
    email = user["profile"]["email"]

    account = body["view"]["state"]["values"]["account"]["account"]["selected_option"][
        "value"
    ]

    account_name = body["view"]["state"]["values"]["account"]["account"][
        "selected_option"
    ]["text"]["text"]

    access_type = body["view"]["state"]["values"]["access_type"]["access_type"][
        "selected_option"
    ]["value"]

    msg = f"<@{user_id}> ({email}) requested access to {account_name} ({account}) with {access_type} priviliges.\n\nRationale: {rationale}"

    logger.info(
        "aws_account_access_request",
        user_id=user_id,
        email=email,
        account_id=account,
        account_name=account_name,
        access_type=access_type,
        rationale=rationale,
    )
    log_ops_message(client, msg)
    aws_user_id = identity_store.get_user_id(email)

    if aws_user_id is None:
        msg = f"<@{user_id}> ({email}) is not registered with AWS SSO. Please contact your administrator.\n<@{user_id}> ({email}) n'est pas enregistré avec AWS SSO. SVP contactez votre administrateur."
    elif expires := already_has_access(account, user_id, access_type):
        msg = f"You already have access to {account_name} ({account}) with access type {access_type}. Your access will expire in {expires} minutes."
    elif create_aws_access_request(
        account, account_name, user_id, email, access_type, rationale
    ) and sso_admin.create_account_assignment(aws_user_id, account, access_type):
        msg = f"Provisioning {access_type} access request for {account_name} ({account}). This can take a minute or two. Visit <https://cds-snc.awsapps.com/start#/|https://cds-snc.awsapps.com/start#/> to gain access.\nTraitement de la requête d'accès {access_type} pour le compte {account_name} ({account}) en cours. Cela peut prendre quelques minutes. Visitez <https://cds-snc.awsapps.com/start#/|https://cds-snc.awsapps.com/start#/> pour y accéder"
    else:
        msg = f"Failed to provision {access_type} access request for {account_name} ({account}). Please drop a note in the <#sre-and-tech-ops> channel.\nLa requête d'accès {access_type} pour {account_name} ({account}) a échouée. Envoyez une note sur le canal <#sre-and-tech-ops>"

    client.chat_postEphemeral(
        channel=user_id,
        user=user_id,
        text=msg,
    )


def request_access_modal(client: WebClient, body):
    accounts = {
        account["Id"]: account["Name"]
        for account in organizations.list_organization_accounts()
    }
    accounts = dict(sorted(accounts.items(), key=lambda i: i[1]))

    options = [
        {
            "text": {"type": "plain_text", "text": value},
            "value": key,
        }
        for key, value in accounts.items()
    ]
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "aws_access_view",
            "title": {"type": "plain_text", "text": "AWS - Account access"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "block_id": "account",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select an account to access | Choisissez un compte à accéder",
                        },
                        "options": options,
                        "action_id": "account",
                    },
                    "label": {"type": "plain_text", "text": "Account", "emoji": True},
                },
                {
                    "block_id": "access_type",
                    "type": "input",
                    "label": {
                        "type": "plain_text",
                        "text": "What type of access do you want? :this-is-fine-fire: | Quel type d'accès désirez-vous? :this-is-fine-fire:",
                        "emoji": True,
                    },
                    "element": {
                        "type": "radio_buttons",
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "Read access - just need to check something \n Lecture seule - je dois juste regarder quelque chose",
                                    "emoji": True,
                                },
                                "value": "read",
                            },
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "Write access - need to modify something \n Écriture - je dois modifier quelque chose",
                                    "emoji": True,
                                },
                                "value": "write",
                            },
                        ],
                        "action_id": "access_type",
                    },
                },
                {
                    "type": "input",
                    "block_id": "rationale",
                    "element": {
                        "type": "plain_text_input",
                        "multiline": True,
                        "action_id": "rationale",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "What do you plan on doing? | Que planifiez-vous faire?",
                        "emoji": True,
                    },
                },
            ],
        },
    )

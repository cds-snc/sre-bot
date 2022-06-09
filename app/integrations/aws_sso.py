import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

ROLE_ARN = os.environ.get("AWS_SSO_ROLE_ARN")
SYSTEM_ADMIN_PERMISSIONS = os.environ.get("AWS_SSO_SYSTEM_ADMIN_PERMISSIONS")
VIEW_ONLY_PERMISSIONS = os.environ.get("AWS_SSO_VIEW_ONLY_PERMISSIONS")

ACCOUNTS = json.loads(os.environ.get("AWS_ACCOUNT_JSON", ""))
INSTANCE_ID = os.environ.get("AWS_SSO_INSTANCE_ID", "")
INSTANCE_ARN = os.environ.get("AWS_SSO_INSTANCE_ARN", "")


def add_permissions_for_user(user_id, account_id, permission_set):
    if permission_set == "write":
        permissions = SYSTEM_ADMIN_PERMISSIONS
    else:
        permissions = VIEW_ONLY_PERMISSIONS

    client = assume_role_client("sso-admin")
    resp = client.create_account_assignment(
        InstanceArn=INSTANCE_ARN,
        TargetId=account_id,
        TargetType="AWS_ACCOUNT",
        PermissionSetArn=permissions,
        PrincipalType="USER",
        PrincipalId=user_id,
    )

    if resp["AccountAssignmentCreationStatus"]["Status"] != "FAILED":
        return True
    else:
        return False


def assume_role_client(client_type):
    client = boto3.client("sts")

    response = client.assume_role(RoleArn=ROLE_ARN, RoleSessionName="SREBot_SSO_Rotate")

    session = boto3.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )

    return session.client(client_type)


def get_accounts():
    return dict(sorted(ACCOUNTS.items(), key=lambda i: i[1]))


def get_accounts_for_permission_set(permission_set_arn):
    client = assume_role_client("sso-admin")
    permission_sets = client.list_accounts_for_provisioned_permission_set(
        PermissionSetArn=permission_set_arn, InstanceArn=INSTANCE_ARN
    )
    return permission_sets.get("AccountIds", [])


def get_user_id(email):
    client = assume_role_client("identitystore")
    user_filter = {"AttributePath": "UserName", "AttributeValue": email}

    response = client.list_users(IdentityStoreId=INSTANCE_ID, Filters=[user_filter])
    if response["Users"] and len(response["Users"]) > 0:
        return response["Users"][0]["UserId"]

    return None


def remove_permissions_for_user(user_id, account_id, permission_set):
    if permission_set == "write":
        permissions = SYSTEM_ADMIN_PERMISSIONS
    else:
        permissions = VIEW_ONLY_PERMISSIONS

    client = assume_role_client("sso-admin")
    resp = client.delete_account_assignment(
        InstanceArn=INSTANCE_ARN,
        TargetId=account_id,
        TargetType="AWS_ACCOUNT",
        PermissionSetArn=permissions,
        PrincipalType="USER",
        PrincipalId=user_id,
    )

    if resp["AccountAssignmentDeletionStatus"]["Status"] != "FAILED":
        return True
    else:
        return False

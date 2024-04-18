import os
import boto3  # type: ignore

from dotenv import load_dotenv

load_dotenv()

# ROLE_ARN = os.environ.get("AWS_ORG_ACCOUNT_ROLE_ARN", "")
ROLE_ARN = os.environ.get("AWS_SSO_ROLE_ARN", "")
SYSTEM_ADMIN_PERMISSIONS = os.environ.get("AWS_SSO_SYSTEM_ADMIN_PERMISSIONS")
VIEW_ONLY_PERMISSIONS = os.environ.get("AWS_SSO_VIEW_ONLY_PERMISSIONS")


AWS_REGION = os.environ.get("AWS_REGION", "ca-central-1")


def get_boto3_client(client_type, region=AWS_REGION):
    """Gets the client for the specified service"""
    return boto3.client(client_type, region_name=region)


def paginate(client, operation, keys, **kwargs):
    """Generic paginator for AWS operations"""
    paginator = client.get_paginator(operation)
    results = []

    for page in paginator.paginate(**kwargs):
        for key in keys:
            if key in page:
                results.extend(page[key])

    return results


def assume_role_client(client_type, role_arn=None, role_session_name="SREBot"):
    if not role_arn:
        role_arn = ROLE_ARN

    # Create a new session using the credentials provided by the ECS task role
    session = boto3.Session()

    # Use the session to create an STS client
    sts_client = session.client("sts")

    # Assume the role
    response = sts_client.assume_role(
        RoleArn=role_arn, RoleSessionName=role_session_name
    )

    # Create a new session with the assumed role's credentials
    assumed_role_session = boto3.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )

    # Return a client created with the assumed role's session
    return assumed_role_session.client(client_type)


def test():
    sts = boto3.client("sts")
    print(sts.get_caller_identity())

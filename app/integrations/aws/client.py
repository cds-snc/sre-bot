import os
import logging
from functools import wraps

import boto3  # type: ignore
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore

from dotenv import load_dotenv

load_dotenv()

ROLE_ARN = os.environ.get("AWS_SSO_ROLE_ARN", "")
SYSTEM_ADMIN_PERMISSIONS = os.environ.get("AWS_SSO_SYSTEM_ADMIN_PERMISSIONS")
VIEW_ONLY_PERMISSIONS = os.environ.get("AWS_SSO_VIEW_ONLY_PERMISSIONS")
AWS_REGION = os.environ.get("AWS_REGION", "ca-central-1")


def handle_aws_api_errors(func):
    """Decorator to handle AWS API errors.

    Args:
        func (function): The function to decorate.

        Returns:
        The decorated function.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BotoCoreError as e:
            logging.error(f"A BotoCore error occurred in function '{func.__name__}': {e}")
        except ClientError as e:
            logging.error(f"A ClientError occurred in function '{func.__name__}': {e}")
        except Exception as e:  # Catch-all for any other types of exceptions
            logging.error(
                f"An unexpected error occurred in function '{func.__name__}': {e}"
            )
        return None

    return wrapper


def paginate(client, operation, keys, **kwargs):
    """Generic paginator for AWS operations"""
    paginator = client.get_paginator(operation)
    results = []

    for page in paginator.paginate(**kwargs):
        for key in keys:
            if key in page:
                results.extend(page[key])

    return results


def assume_role_client(service_name, role_arn):
    """Assume an AWS IAM role and return a service client.

    Args:
        service_name (str): The name of the AWS service.
        role_arn (str): The ARN of the IAM role to assume.

    Returns:
        botocore.client.BaseClient: The service client.

    Raises:
        botocore.exceptions.BotoCoreError: If any errors occur when assuming the role or creating the client.
    """
    try:
        sts_client = boto3.client("sts")
        assumed_role_object = sts_client.assume_role(
            RoleArn=role_arn, RoleSessionName="AssumeRoleSession1"
        )
        credentials = assumed_role_object["Credentials"]
        client = boto3.client(
            service_name,
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
        return client
    except (BotoCoreError, ClientError) as error:
        print(f"An error occurred: {error}")
        raise


def execute_aws_api_call(service_name, method, paginated=False, **kwargs):
    """Execute an AWS API call.

    Args:
        service_name (str): The name of the AWS service.
        method (str): The method to call on the service client.
        paginate (bool, optional): Whether to paginate the API call.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        list: The result of the API call. If paginate is True, returns a list of all results.
    """
    if "role_arn" not in kwargs:
        role_arn = ROLE_ARN
    client = assume_role_client(service_name, role_arn)
    api_method = getattr(client, method)
    if paginated:
        return paginator(client, method, **kwargs)
    else:
        return api_method(**kwargs)


def paginator(client, operation, keys=None, **kwargs):
    """Generic paginator for AWS operations

    Args:
        client (botocore.client.BaseClient): The service client.
        operation (str): The operation to paginate.
        keys (list, optional): The keys to extract from the paginated results.
        **kwargs: Additional keyword arguments for the operation.

    Returns:
        list: The paginated results.

    Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/paginators.html
    """
    paginator = client.get_paginator(operation)
    results = []

    for page in paginator.paginate(**kwargs):
        if keys is None:
            results.append(page)
        else:
            for key in keys:
                if key in page:
                    results.extend(page[key])

    return results

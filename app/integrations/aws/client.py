import os
import logging
from functools import wraps
import boto3  # type: ignore
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
from dotenv import load_dotenv
from integrations.utils.api import convert_kwargs_to_pascal_case

load_dotenv()

ROLE_ARN = os.environ.get("AWS_DEFAULT_ROLE_ARN", None)
SYSTEM_ADMIN_PERMISSIONS = os.environ.get("AWS_SSO_SYSTEM_ADMIN_PERMISSIONS")
VIEW_ONLY_PERMISSIONS = os.environ.get("AWS_SSO_VIEW_ONLY_PERMISSIONS")
AWS_REGION = os.environ.get("AWS_REGION", "ca-central-1")
THROTTLING_ERRORS = ["Throttling", "ThrottlingException", "RequestLimitExceeded"]
RESOURCE_NOT_FOUND_ERRORS = ["ResourceNotFoundException", "NoSuchEntity"]


logger = logging.getLogger()


def handle_aws_api_errors(func):
    """Decorator to handle AWS API errors.

    Args:
        func (function): The function to decorate.

    Returns:
        The decorated function with error handling.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except BotoCoreError as e:
            logger.error(f"{func.__module__}.{func.__name__}:BotoCore error: {e}")
        except ClientError as e:
            if e.response["Error"]["Code"] in THROTTLING_ERRORS:
                logger.info(f"{func.__module__}.{func.__name__}: {e}")
            elif e.response["Error"]["Code"] in RESOURCE_NOT_FOUND_ERRORS:
                logger.warn(f"{func.__module__}.{func.__name__}: {e}")
            else:
                logger.error(f"{func.__module__}.{func.__name__}: {e}")
        except Exception as e:  # Catch-all for any other types of exceptions
            logger.error(f"{func.__module__}.{func.__name__}: {e}")
        return False

    return wrapper


@handle_aws_api_errors
def assume_role_client(service_name, role_arn):
    """Assume an AWS IAM role and return a service client.

    Args:
        service_name (str): The name of the AWS service.
        role_arn (str): The ARN of the IAM role to assume.

    Returns:
        botocore.client.BaseClient: The service client.
    """
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


def execute_aws_api_call(service_name, method, paginated=False, **kwargs):
    """Execute an AWS API call.

    Args:
        service_name (str): The name of the AWS service.
        method (str): The method to call on the service client.
        paginate (bool, optional): Whether to paginate the API call.
        role_arn (str, optional): The ARN of the IAM role to assume. If not provided as an argument, it will be taken from the AWS_SSO_ROLE_ARN environment variable.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        list or dict: The result of the API call. If paginate is True, returns a list of all results. If paginate is False, returns the result as a dict.

    Raises:
        ValueError: If the role_arn is not provided.
    """

    role_arn = kwargs.pop("role_arn", os.environ.get("AWS_SSO_ROLE_ARN", None))
    keys = kwargs.pop("keys", None)
    if role_arn is None:
        raise ValueError(
            "role_arn must be provided either as a keyword argument or as the AWS_SSO_ROLE_ARN environment variable"
        )
    if service_name is None or method is None:
        raise ValueError("The AWS service name and method must be provided")
    client = assume_role_client(service_name, role_arn)
    if kwargs:
        kwargs = convert_kwargs_to_pascal_case(kwargs)
    api_method = getattr(client, method)
    if paginated:
        return paginator(client, method, keys, **kwargs)
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

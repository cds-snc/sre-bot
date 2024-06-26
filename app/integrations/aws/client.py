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
CLIENT_DEFAULTS = {
    "region_name": AWS_REGION,
}

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
                logger.warning(f"{func.__module__}.{func.__name__}: {e}")
            else:
                logger.error(f"{func.__module__}.{func.__name__}: {e}")
        except Exception as e:  # Catch-all for any other types of exceptions
            logger.error(f"{func.__module__}.{func.__name__}: {e}")
        return False

    return wrapper


@handle_aws_api_errors
def assume_role_client(role_arn):
    """Assume an IAM role to get temporary credentials.

    Args:
        role_arn (str): The ARN of the IAM role to assume.

    Returns:
        botocore.client.BaseClient: The service client.
    """
    sts_client = boto3.client("sts")
    assumed_role_object = sts_client.assume_role(
        RoleArn=role_arn, RoleSessionName="AssumeRoleSession1"
    )
    credentials = assumed_role_object["Credentials"]
    return credentials


def get_aws_service_client(service_name, **config):
    """Get an AWS service client. If a role_arn is provided in the config, assume the role to get temporary credentials.

    Args:
        service_name (str): The name of the AWS service.
        **config: Additional keyword arguments for the service client.

    Returns:
        botocore.client.BaseClient: The service client.
    """
    role_arn = config.get("role_arn", None)
    if role_arn is not None:
        credentials = assume_role_client(service_name, role_arn)
        config["aws_access_key_id"] = credentials["AccessKeyId"]
        config["aws_secret_access_key"] = credentials["SecretAccessKey"]
        config["aws_session_token"] = credentials["SessionToken"]
    return boto3.client(service_name, **config)


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

    keys = kwargs.pop("keys", None)
    client_config = kwargs.pop("client_config", CLIENT_DEFAULTS)
    client = get_aws_service_client(service_name, **client_config)
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

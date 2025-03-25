from functools import wraps

import boto3  # type: ignore
from botocore.client import BaseClient  # type: ignore
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
from core.config import settings
from core.logging import get_module_logger

logger = get_module_logger()

SYSTEM_ADMIN_PERMISSIONS = settings.aws.SYSTEM_ADMIN_PERMISSIONS
VIEW_ONLY_PERMISSIONS = settings.aws.VIEW_ONLY_PERMISSIONS
AWS_REGION = settings.aws.AWS_REGION
THROTTLING_ERRORS = settings.aws.THROTTLING_ERRORS
RESOURCE_NOT_FOUND_ERRORS = settings.aws.RESOURCE_NOT_FOUND_ERRORS


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
            logger.error(
                "boto_core_error",
                module=func.__module__,
                function=func.__name__,
                error=str(e),
            )
        except ClientError as e:
            if e.response["Error"]["Code"] in THROTTLING_ERRORS:
                logger.info(
                    "aws_throttling_error",
                    module=func.__module__,
                    function=func.__name__,
                    error=str(e),
                )
            elif e.response["Error"]["Code"] in RESOURCE_NOT_FOUND_ERRORS:
                logger.warning(
                    "aws_resource_not_found",
                    module=func.__module__,
                    function=func.__name__,
                    error=str(e),
                )
            else:
                logger.error(
                    "aws_client_error",
                    module=func.__module__,
                    function=func.__name__,
                    error=str(e),
                )
        except Exception as e:  # Catch-all for any other types of exceptions
            logger.error(
                "unexpected_error",
                module=func.__module__,
                function=func.__name__,
                error=str(e),
            )
        return False

    return wrapper


@handle_aws_api_errors
def assume_role_session(role_arn, session_name="DefaultSession"):
    """Assume an IAM role and return a session with temporary credentials.

    Args:
        role_arn (str): The ARN of the IAM role to assume.
        session_name (str): An identifier for the assumed role session.

    Returns:
        boto3.Session: A session with temporary credentials.
    """
    sts_client = boto3.client("sts")
    assumed_role = sts_client.assume_role(
        RoleArn=role_arn, RoleSessionName=session_name
    )
    credentials = assumed_role["Credentials"]

    return boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
    )


@handle_aws_api_errors
def get_aws_service_client(
    service_name,
    role_arn=None,
    session_name="DefaultSession",
    session_config=None,
    client_config=None,
):
    """Get an AWS service client. If a role_arn is provided in the config, assume the role to get temporary credentials.

    Args:
        service_name (str): The name of the AWS service.
        **config: Additional keyword arguments for the service client.

    Returns:
        botocore.client.BaseClient: The service client.
    """
    if session_config is None:
        session_config = {}
    if client_config is None:
        client_config = {}

    if role_arn:
        session = assume_role_session(role_arn, session_name)
    else:
        session = boto3.Session(**session_config)
    return session.client(service_name, **client_config)


def execute_aws_api_call(
    service_name,
    method,
    paginated=False,
    keys=None,
    role_arn=None,
    session_config=None,
    client_config=None,
    **kwargs,
):
    """Execute an AWS API call.

    Args:
        service_name (str): The name of the AWS service.
        method (str): The method to call on the service client.
        paginate (bool, optional): Whether to paginate the API call.
        role_arn (str, optional): The ARN of the IAM role to assume. If not provided as an argument, it will be taken from the AWS_ORG_ACCOUNT_ROLE_ARN environment variable.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        list or dict: The result of the API call. If paginate is True, returns a list of all results. If paginate is False, returns the result as a dict.

    Raises:
        ValueError: If the role_arn is not provided.
    """
    if session_config is None:
        session_config = {"region_name": AWS_REGION}
    if client_config is None:
        client_config = {"region_name": AWS_REGION}

    client = get_aws_service_client(
        service_name,
        role_arn,
        session_config=session_config,
        client_config=client_config,
    )
    api_method = getattr(client, method)
    if paginated:
        results = paginator(client, method, keys, **kwargs)
    else:
        results = api_method(**kwargs)

    if (
        "ResponseMetadata" in results
        and results["ResponseMetadata"]["HTTPStatusCode"] != 200
    ):
        logger.error(
            "api_call_failed",
            service=service_name,
            method=method,
            status_code=results["ResponseMetadata"]["HTTPStatusCode"],
        )
        raise RuntimeError(
            f"API call to {service_name}.{method} failed with status code {results['ResponseMetadata']['HTTPStatusCode']}"
        )
    return results


def paginator(client: BaseClient, operation, keys=None, **kwargs):
    """Generic paginator for AWS operations

    Args:
        client (BaseClient): The service client.
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
            for key, value in page.items():
                if key != "ResponseMetadata":
                    if isinstance(value, list):
                        results.extend(value)
                    else:
                        results.append(value)
                else:
                    if key == "ResponseMetadata" and value["HTTPStatusCode"] != 200:
                        logger.error(
                            "api_call_failed_during_pagination",
                            service=client.meta.service_model.service_name,
                            operation=operation,
                            status_code=value["HTTPStatusCode"],
                        )
                        raise RuntimeError(
                            f"API call to {client.meta.service_model.service_name}.{operation} failed with status code {value['HTTPStatusCode']}"
                        )
        else:
            for key in keys:
                if key in page:
                    results.extend(page[key])

    return results

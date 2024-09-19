import os
import logging
from functools import wraps
import boto3  # type: ignore
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
from botocore.client import BaseClient  # type: ignore
from dotenv import load_dotenv
from integrations.utils.api import convert_kwargs_to_pascal_case

load_dotenv()

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
                logger.warning(f"{func.__module__}.{func.__name__}: {e}")
            else:
                logger.error(f"{func.__module__}.{func.__name__}: {e}")
        except Exception as e:  # Catch-all for any other types of exceptions
            logger.error(f"{func.__module__}.{func.__name__}: {e}")
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
            f"API call to {service_name}.{method} failed with status code {results['ResponseMetadata']['HTTPStatusCode']}"
        )
        raise Exception(
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
                            f"API call to {client.meta.service_model.service_name}.{operation} failed with status code {value['HTTPStatusCode']}"
                        )
                        raise Exception(
                            f"API call to {client.meta.service_model.service_name}.{operation} failed with status code {value['HTTPStatusCode']}"
                        )
        else:
            for key in keys:
                if key in page:
                    results.extend(page[key])

    return results

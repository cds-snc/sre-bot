"""AWS vendor client.

Provides the typed boto3 client factory and the shared error classification
per decisions/outbound-clients.md: clients raise typed SDK exceptions; adapters
classify them. Every client carries SDK-native standard retries and explicit
per-attempt timeouts fixed once at construction, AssumeRole goes through the
public STS API, and the only endpoint override is the dynamodb-local one.
Clients are built per call and never cached, so assumed credentials never
need refreshing.
"""

from functools import wraps
from typing import TYPE_CHECKING, Any, Literal, overload

import boto3
import structlog
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.configuration.integrations.aws import get_aws_settings as _get_legacy_aws_settings
from infrastructure.operations.status import OperationStatus
from integrations.aws.settings import AWSSettings, get_aws_settings

if TYPE_CHECKING:
    from types_boto3_ce.client import CostExplorerClient
    from types_boto3_config.client import ConfigServiceClient
    from types_boto3_dynamodb.client import DynamoDBClient
    from types_boto3_guardduty.client import GuardDutyClient
    from types_boto3_identitystore.client import IdentityStoreClient
    from types_boto3_lambda.client import LambdaClient
    from types_boto3_organizations.client import OrganizationsClient
    from types_boto3_securityhub.client import SecurityHubClient
    from types_boto3_sso_admin.client import SSOAdminClient
    from types_boto3_sts.client import STSClient
    from types_boto3_sts.type_defs import CredentialsTypeDef

logger = structlog.get_logger()

type AwsServiceName = Literal[
    "dynamodb",
    "identitystore",
    "organizations",
    "sso-admin",
    "ce",
    "config",
    "guardduty",
    "securityhub",
    "lambda",
    "sts",
]

_DEFAULT_SESSION_NAME = "sre-bot"


@overload
def get_aws_client(
    service_name: Literal["dynamodb"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> DynamoDBClient: ...
@overload
def get_aws_client(
    service_name: Literal["identitystore"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> IdentityStoreClient: ...
@overload
def get_aws_client(
    service_name: Literal["organizations"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> OrganizationsClient: ...
@overload
def get_aws_client(
    service_name: Literal["sso-admin"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> SSOAdminClient: ...
@overload
def get_aws_client(
    service_name: Literal["ce"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> CostExplorerClient: ...
@overload
def get_aws_client(
    service_name: Literal["config"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> ConfigServiceClient: ...
@overload
def get_aws_client(
    service_name: Literal["guardduty"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> GuardDutyClient: ...
@overload
def get_aws_client(
    service_name: Literal["securityhub"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> SecurityHubClient: ...
@overload
def get_aws_client(
    service_name: Literal["lambda"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> LambdaClient: ...
@overload
def get_aws_client(
    service_name: Literal["sts"],
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> STSClient: ...


def get_aws_client(
    service_name: AwsServiceName,
    *,
    role_arn: str | None = None,
    session_name: str = _DEFAULT_SESSION_NAME,
    retries: bool = True,
) -> Any:
    """Build a boto3 client with the standard retry, timeout and endpoint policy.

    ``role_arn`` assumes that role eagerly through STS before the client is
    built. ``retries=False`` makes exactly one attempt, for writes that are not
    safe to replay. The dynamodb-local endpoint is applied to dynamodb only,
    and only when configured. Failures raise SDK exceptions; adapters classify
    them with ``classify_aws_error``.
    """
    settings = get_aws_settings()
    session = _session_for(settings, role_arn, session_name)
    endpoint_url = settings.DYNAMODB_ENDPOINT_URL if service_name == "dynamodb" else None
    return session.client(
        service_name,
        region_name=settings.AWS_REGION,
        config=_build_config(settings, retries=retries),
        endpoint_url=endpoint_url,
    )


def _build_config(settings: AWSSettings, *, retries: bool) -> Config:
    """Botocore config with explicit retry mode, attempt budget and timeouts."""
    max_attempts = settings.RETRY_MAX_ATTEMPTS if retries else 0
    return Config(
        retries={"mode": settings.RETRY_MODE, "max_attempts": max_attempts},
        connect_timeout=settings.CONNECT_TIMEOUT_SECONDS,
        read_timeout=settings.READ_TIMEOUT_SECONDS,
    )


def _session_for(settings: AWSSettings, role_arn: str | None, session_name: str) -> boto3.Session:
    """Ambient-credential session, or one holding credentials assumed for ``role_arn``."""
    ambient = boto3.Session(region_name=settings.AWS_REGION)
    if not role_arn:
        return ambient

    sts: STSClient = ambient.client("sts", config=_build_config(settings, retries=True))
    credentials = _assume_role_credentials(sts, role_arn, session_name)
    return boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=settings.AWS_REGION,
    )


def _assume_role_credentials(sts: STSClient, role_arn: str, session_name: str) -> CredentialsTypeDef:
    """Exchange ``role_arn`` for temporary credentials through the public STS API."""
    response = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
    return response["Credentials"]


def classify_aws_error(exc: Exception) -> tuple[OperationStatus, str | None, int | None]:
    """Classify expected botocore errors; propagate unknown exceptions unchanged."""
    if isinstance(exc, BotoCoreError):
        return OperationStatus.TRANSIENT_ERROR, type(exc).__name__, None

    if not isinstance(exc, ClientError):
        raise exc

    response = getattr(exc, "response", None) or {}
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    code = error.get("Code")
    if not isinstance(code, str) or not code:
        raise exc

    settings = get_aws_settings()
    if code in settings.NOT_FOUND_CODES:
        return OperationStatus.NOT_FOUND, code, None
    if code in settings.UNAUTHORIZED_CODES:
        return OperationStatus.UNAUTHORIZED, code, None
    if code in settings.TRANSIENT_CODES:
        return OperationStatus.TRANSIENT_ERROR, code, settings.TRANSIENT_RETRY_AFTER_SECONDS
    if code == "ConditionalCheckFailedException":
        return OperationStatus.PERMANENT_ERROR, code, None

    raise exc


# --- Legacy dispatcher helpers -------------------------------------------------
# Kept only for the per-service mirror modules and deleted together with the
# last of them. They keep reading the infrastructure settings module the mirrors
# still import; nothing above this line does.
_legacy_settings = _get_legacy_aws_settings()
SYSTEM_ADMIN_PERMISSIONS = _legacy_settings.SYSTEM_ADMIN_PERMISSIONS
VIEW_ONLY_PERMISSIONS = _legacy_settings.VIEW_ONLY_PERMISSIONS
AWS_REGION = _legacy_settings.AWS_REGION
THROTTLING_ERRS = _legacy_settings.THROTTLING_ERRS
RESOURCE_NOT_FOUND_ERRS = _legacy_settings.RESOURCE_NOT_FOUND_ERRS


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
            log = logger.bind(module=func.__module__, function=func.__name__)
            log.error(
                "boto_core_error",
                error=str(e),
            )
        except ClientError as e:
            log = logger.bind(
                module=func.__module__,
                function=func.__name__,
                error_code=e.response["Error"]["Code"],
            )
            if e.response["Error"]["Code"] in THROTTLING_ERRS:
                log.info(
                    "aws_throttling_error",
                    error=str(e),
                )
            elif e.response["Error"]["Code"] in RESOURCE_NOT_FOUND_ERRS:
                log.warning(
                    "aws_resource_not_found",
                    error=str(e),
                )
            else:
                log.error(
                    "aws_client_error",
                    error=str(e),
                )
        except Exception as e:  # Catch-all for any other types of exceptions
            log = logger.bind(module=func.__module__, function=func.__name__)
            log.error(
                "unexpected_error",
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
    assumed_role = sts_client.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
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

    session = assume_role_session(role_arn, session_name) if role_arn else boto3.Session(**session_config)
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

    log = logger.bind(service=service_name, method=method, paginated=paginated)
    log.debug("aws_api_call_started")

    client = get_aws_service_client(
        service_name,
        role_arn,
        session_config=session_config,
        client_config=client_config,
    )
    api_method = getattr(client, method)
    results = paginator(client, method, keys, **kwargs) if paginated else api_method(**kwargs)

    if "ResponseMetadata" in results and results["ResponseMetadata"]["HTTPStatusCode"] != 200:
        log.error(
            "aws_api_call_failed",
            status_code=results["ResponseMetadata"]["HTTPStatusCode"],
        )
        raise RuntimeError(
            f"API call to {service_name}.{method} failed with status code {results['ResponseMetadata']['HTTPStatusCode']}"
        )

    log.debug("aws_api_call_completed")

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
    log = logger.bind(service=client.meta.service_model.service_name, operation=operation)

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
                        log.error(
                            "api_call_failed_during_pagination",
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

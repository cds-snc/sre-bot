"""AWS vendor client.

Provides the typed boto3 client factory and the shared error classification
per decisions/outbound-clients.md: clients raise typed SDK exceptions; adapters
classify them. Every client carries SDK-native standard retries and explicit
per-attempt timeouts fixed once at construction, AssumeRole goes through the
public STS API, and the only endpoint override is the dynamodb-local one.
Clients are built per call and never cached, so assumed credentials never
need refreshing.
"""

from typing import TYPE_CHECKING, Any, Literal, overload

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

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
    if code in ("ConditionalCheckFailedException", "ConflictException"):
        # DynamoDB conditional writes and Identity Store "already exists" conflicts are final outcomes.
        return OperationStatus.PERMANENT_ERROR, code, None

    raise exc

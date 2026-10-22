"""AWS vendor settings: the single home of every AWS setting.

Exposes `AWSSettings` and the cached `get_aws_settings()` provider, read by
the client factory and the error classifier in `integrations.aws.client`.
Transport fields (region, retry policy, per-attempt timeouts, the
dynamodb-local endpoint, boto3 error-code catalogues) live next to the
feature-level fields (SSO permission sets, per-account role ARNs, SSO instance
identifiers, the service-to-role map) until the business features that own
them define their own settings modules; the env aliases match what the
deployment already sets.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RetryMode = Literal["legacy", "standard", "adaptive"]


class AWSSettings(BaseSettings):
    """Transport, error-classification and feature-level settings for AWS."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    aws_region: str = Field(default="ca-central-1")
    dynamodb_endpoint_url: str | None = Field(
        default=None,
        alias="AWS_ENDPOINT_URL_DYNAMODB",
        description=(
            "Endpoint override applied to DynamoDB clients only; botocore's own "
            "service-specific variable name. Set to http://dynamodb-local:8000 for "
            "local development, leave unset elsewhere."
        ),
    )

    retry_max_attempts: int = Field(
        default=3,
        alias="AWS_RETRY_MAX_ATTEMPTS",
        description="Retries after the initial attempt (botocore max_attempts): 3 means four attempts in total.",
    )
    retry_mode: RetryMode = Field(default="standard", alias="AWS_RETRY_MODE")
    connect_timeout_seconds: int = Field(default=10, alias="AWS_CONNECT_TIMEOUT_SECONDS")
    read_timeout_seconds: int = Field(default=10, alias="AWS_READ_TIMEOUT_SECONDS")
    transient_retry_after_seconds: int = Field(
        default=60,
        alias="AWS_TRANSIENT_RETRY_AFTER_SECONDS",
        description="Retry hint attached to transient classifications, in seconds.",
    )

    not_found_codes: list[str] = Field(
        default=[
            "ResourceNotFoundException",
            "NoSuchEntity",
            "NoSuchBucket",
            "NoSuchKey",
            "NotFoundException",
            "AccountNotFoundException",
            "TargetNotFoundException",
            "NoSuchConfigurationAggregatorException",
        ],
        alias="AWS_NOT_FOUND_CODES",
    )
    unauthorized_codes: list[str] = Field(
        default=[
            "AccessDenied",
            "AccessDeniedException",
            "UnauthorizedOperation",
            "InvalidClientTokenId",
            "SignatureDoesNotMatch",
            "ExpiredToken",
            "ExpiredTokenException",
            "TokenRefreshRequired",
            "InvalidAccessException",
        ],
        alias="AWS_UNAUTHORIZED_CODES",
    )
    transient_codes: list[str] = Field(
        default=[
            "Throttling",
            "ThrottlingException",
            "RequestLimitExceeded",
            "ProvisionedThroughputExceededException",
            "TooManyRequestsException",
            "RequestTimeout",
            "RequestTimeoutException",
            "ServiceUnavailable",
            "ServiceUnavailableException",
            "InternalFailure",
            "InternalServerError",
            "InternalServerErrorException",
            "InternalException",
            "ServiceException",
            "LimitExceededException",
        ],
        alias="AWS_TRANSIENT_CODES",
    )

    system_admin_permissions: str = Field(default="", alias="AWS_SSO_SYSTEM_ADMIN_PERMISSIONS")
    view_only_permissions: str = Field(default="", alias="AWS_SSO_VIEW_ONLY_PERMISSIONS")
    audit_role_arn: str = Field(default="", alias="AWS_AUDIT_ACCOUNT_ROLE_ARN")
    org_role_arn: str = Field(default="", alias="AWS_ORG_ACCOUNT_ROLE_ARN")
    logging_role_arn: str = Field(default="", alias="AWS_LOGGING_ACCOUNT_ROLE_ARN")
    instance_id: str = Field(default="", alias="AWS_SSO_INSTANCE_ID")
    instance_arn: str = Field(default="", alias="AWS_SSO_INSTANCE_ARN")

    @property
    def service_role_map(self) -> dict[str, str]:
        """Role ARN assumed for each service or account role name."""
        return {
            "audit": self.audit_role_arn,
            "organizations": self.org_role_arn,
            "identitystore": self.org_role_arn,
            "sso-admin": self.org_role_arn,
            "logging": self.logging_role_arn,
            "ce": self.org_role_arn,
            "config": self.audit_role_arn,
            "guardduty": self.logging_role_arn,
            "securityhub": self.logging_role_arn,
        }


@lru_cache(maxsize=1)
def get_aws_settings() -> AWSSettings:
    """Return the process-wide `AWSSettings` singleton."""
    return AWSSettings()

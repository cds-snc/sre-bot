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
        case_sensitive=True,
        extra="ignore",
    )

    AWS_REGION: str = Field(default="ca-central-1")
    DYNAMODB_ENDPOINT_URL: str | None = Field(
        default=None,
        alias="AWS_ENDPOINT_URL_DYNAMODB",
        description=(
            "Endpoint override applied to DynamoDB clients only; botocore's own "
            "service-specific variable name. Set to http://dynamodb-local:8000 for "
            "local development, leave unset elsewhere."
        ),
    )

    RETRY_MAX_ATTEMPTS: int = Field(
        default=3,
        alias="AWS_RETRY_MAX_ATTEMPTS",
        description="Retries after the initial attempt (botocore max_attempts): 3 means four attempts in total.",
    )
    RETRY_MODE: RetryMode = Field(default="standard", alias="AWS_RETRY_MODE")
    CONNECT_TIMEOUT_SECONDS: int = Field(default=10, alias="AWS_CONNECT_TIMEOUT_SECONDS")
    READ_TIMEOUT_SECONDS: int = Field(default=10, alias="AWS_READ_TIMEOUT_SECONDS")
    TRANSIENT_RETRY_AFTER_SECONDS: int = Field(
        default=60,
        alias="AWS_TRANSIENT_RETRY_AFTER_SECONDS",
        description="Retry hint attached to transient classifications, in seconds.",
    )

    NOT_FOUND_CODES: list[str] = Field(
        default=[
            "ResourceNotFoundException",
            "NoSuchEntity",
            "NoSuchBucket",
            "NoSuchKey",
            "NotFoundException",
        ],
        alias="AWS_NOT_FOUND_CODES",
    )
    UNAUTHORIZED_CODES: list[str] = Field(
        default=[
            "AccessDenied",
            "AccessDeniedException",
            "UnauthorizedOperation",
            "InvalidClientTokenId",
            "SignatureDoesNotMatch",
            "ExpiredToken",
            "ExpiredTokenException",
            "TokenRefreshRequired",
        ],
        alias="AWS_UNAUTHORIZED_CODES",
    )
    TRANSIENT_CODES: list[str] = Field(
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
        ],
        alias="AWS_TRANSIENT_CODES",
    )

    SYSTEM_ADMIN_PERMISSIONS: str = Field(default="", alias="AWS_SSO_SYSTEM_ADMIN_PERMISSIONS")
    VIEW_ONLY_PERMISSIONS: str = Field(default="", alias="AWS_SSO_VIEW_ONLY_PERMISSIONS")
    AUDIT_ROLE_ARN: str = Field(default="", alias="AWS_AUDIT_ACCOUNT_ROLE_ARN")
    ORG_ROLE_ARN: str = Field(default="", alias="AWS_ORG_ACCOUNT_ROLE_ARN")
    LOGGING_ROLE_ARN: str = Field(default="", alias="AWS_LOGGING_ACCOUNT_ROLE_ARN")
    INSTANCE_ID: str = Field(default="", alias="AWS_SSO_INSTANCE_ID")
    INSTANCE_ARN: str = Field(default="", alias="AWS_SSO_INSTANCE_ARN")

    @property
    def SERVICE_ROLE_MAP(self) -> dict[str, str]:
        """Role ARN assumed for each service or account role name."""
        return {
            "audit": self.AUDIT_ROLE_ARN,
            "organizations": self.ORG_ROLE_ARN,
            "identitystore": self.ORG_ROLE_ARN,
            "sso-admin": self.ORG_ROLE_ARN,
            "logging": self.LOGGING_ROLE_ARN,
            "ce": self.ORG_ROLE_ARN,
            "config": self.AUDIT_ROLE_ARN,
            "guardduty": self.LOGGING_ROLE_ARN,
        }


@lru_cache(maxsize=1)
def get_aws_settings() -> AWSSettings:
    """Return the process-wide `AWSSettings` singleton."""
    return AWSSettings()

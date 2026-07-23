"""Vendor settings for the AWS shield.

Exposes `AWSSettings` — the vendor-credential, transport, and
error-classification surface consumed by `AWSShield` — and the cached
`get_aws_settings()` provider.

Only AWS-transport concerns belong here (region, endpoint, retry policy,
timeouts, boto3 error-code catalogues). Feature-domain configuration
(SSO permission sets, instance ARNs, role mappings) lives with the
consuming feature per `docs/adr/configuration-ownership.md`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

RetryMode = Literal["legacy", "standard", "adaptive"]


class AWSSettings(BaseSettings):
    """Vendor-credential, transport, and error-classification settings for AWS."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    AWS_REGION: str = Field(default="ca-central-1")
    AWS_ENDPOINT_URL: str | None = Field(default=None)

    RETRY_MAX_ATTEMPTS: int = Field(default=3, alias="AWS_RETRY_MAX_ATTEMPTS")
    RETRY_MODE: RetryMode = Field(default="standard", alias="AWS_RETRY_MODE")
    CONNECT_TIMEOUT_SECONDS: int = Field(default=10, alias="AWS_CONNECT_TIMEOUT_SECONDS")
    READ_TIMEOUT_SECONDS: int = Field(default=10, alias="AWS_READ_TIMEOUT_SECONDS")

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


@lru_cache(maxsize=1)
def get_aws_settings() -> AWSSettings:
    """Return the process-wide `AWSSettings` singleton."""
    return AWSSettings()

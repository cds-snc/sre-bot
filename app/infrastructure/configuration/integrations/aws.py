"""AWS integration settings."""

from pydantic import Field

from infrastructure.configuration.base import IntegrationSettings


class AwsSettings(IntegrationSettings):
    """AWS configuration settings.

    Environment Variables:
        AWS_REGION: AWS region for services (default: ca-central-1)
        AWS_SSO_SYSTEM_ADMIN_PERMISSIONS: System admin permission set ARN
        AWS_SSO_VIEW_ONLY_PERMISSIONS: View-only permission set ARN
        AWS_AUDIT_ACCOUNT_ROLE_ARN: Audit account role ARN
        AWS_ORG_ACCOUNT_ROLE_ARN: Organization account role ARN
        AWS_LOGGING_ACCOUNT_ROLE_ARN: Logging account role ARN
        AWS_SSO_INSTANCE_ID: AWS SSO instance ID
        AWS_SSO_INSTANCE_ARN: AWS SSO instance ARN

    Example:
        ```python
        from infrastructure.services import get_settings

        settings = get_settings()

        region = settings.aws.AWS_REGION
        instance_arn = settings.aws.INSTANCE_ARN
        ```
    """

    AWS_REGION: str = Field(default="ca-central-1", alias="AWS_REGION")
    SYSTEM_ADMIN_PERMISSIONS: str = Field(
        default="", alias="AWS_SSO_SYSTEM_ADMIN_PERMISSIONS"
    )
    VIEW_ONLY_PERMISSIONS: str = Field(
        default="", alias="AWS_SSO_VIEW_ONLY_PERMISSIONS"
    )
    AUDIT_ROLE_ARN: str = Field(default="", alias="AWS_AUDIT_ACCOUNT_ROLE_ARN")
    ORG_ROLE_ARN: str = Field(default="", alias="AWS_ORG_ACCOUNT_ROLE_ARN")
    LOGGING_ROLE_ARN: str = Field(default="", alias="AWS_LOGGING_ACCOUNT_ROLE_ARN")
    INSTANCE_ID: str = Field(default="", alias="AWS_SSO_INSTANCE_ID")
    INSTANCE_ARN: str = Field(default="", alias="AWS_SSO_INSTANCE_ARN")

    THROTTLING_ERRS: list[str] = [
        "Throttling",
        "ThrottlingException",
        "RequestLimitExceeded",
    ]
    RESOURCE_NOT_FOUND_ERRS: list[str] = ["ResourceNotFoundException", "NoSuchEntity"]

    @property
    def SERVICE_ROLE_MAP(self) -> dict[str, str]:
        """Mapping of service names to their associated role ARNs.

        Returns:
            Dict mapping service identifiers to role ARNs
        """
        return {
            "audit": self.AUDIT_ROLE_ARN,
            "organizations": self.ORG_ROLE_ARN,
            "sso-admin": self.ORG_ROLE_ARN,
            "logging": self.LOGGING_ROLE_ARN,
            "ce": self.ORG_ROLE_ARN,
            "config": self.AUDIT_ROLE_ARN,
            "guardduty": self.LOGGING_ROLE_ARN,
        }

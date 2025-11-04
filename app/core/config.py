"""SRE Bot configuration settings."""

from typing import Any, Dict, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import structlog

logger = structlog.stdlib.get_logger().bind(component="config")


class SlackSettings(BaseSettings):
    """Slack configuration settings."""

    INCIDENT_CHANNEL: str = ""
    SLACK_SECURITY_USER_GROUP_ID: str = ""
    APP_TOKEN: str = ""
    SLACK_TOKEN: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class AwsSettings(BaseSettings):
    """AWS configuration settings."""

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
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class GoogleWorkspaceSettings(BaseSettings):
    """Google Workspace configuration settings."""

    GOOGLE_DELEGATED_ADMIN_EMAIL: str = Field(
        default="", alias="GOOGLE_DELEGATED_ADMIN_EMAIL"
    )
    SRE_BOT_EMAIL: str = Field(default="", alias="SRE_BOT_EMAIL")
    GOOGLE_WORKSPACE_CUSTOMER_ID: str = Field(
        default="", alias="GOOGLE_WORKSPACE_CUSTOMER_ID"
    )
    GOOGLE_SRE_CALENDAR_ID: str = Field(default="", alias="GOOGLE_SRE_CALENDAR_ID")

    GCP_SRE_SERVICE_ACCOUNT_KEY_FILE: str = Field(
        default="", alias="GCP_SRE_SERVICE_ACCOUNT_KEY_FILE"
    )

    SRE_DRIVE_ID: str = Field(default="", alias="SRE_DRIVE_ID")
    SRE_INCIDENT_FOLDER: str = Field(default="", alias="SRE_INCIDENT_FOLDER")
    INCIDENT_TEMPLATE: str = Field(default="", alias="INCIDENT_TEMPLATE")
    INCIDENT_LIST: str = Field(default="", alias="INCIDENT_LIST")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class MaxMindSettings(BaseSettings):
    """MaxMind configuration settings."""

    MAXMIND_DB_PATH: str = Field(
        default="./geodb/GeoLite2-City.mmdb", alias="MAXMIND_DB_PATH"
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class NotifySettings(BaseSettings):
    """GC Notify configuration settings."""

    NOTIFY_SRE_USER_NAME: str | None = Field(default=None, alias="NOTIFY_SRE_USER_NAME")
    NOTIFY_SRE_CLIENT_SECRET: str | None = Field(
        default=None, alias="NOTIFY_SRE_CLIENT_SECRET"
    )
    NOTIFY_API_URL: str = Field(default="", alias="NOTIFY_API_URL")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class OpsGenieSettings(BaseSettings):
    """OpsGenie configuration settings."""

    OPSGENIE_INTEGRATIONS_KEY: str | None = Field(
        default=None, alias="OPSGENIE_INTEGRATIONS_KEY"
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class SentinelSettings(BaseSettings):
    """Sentinel configuration settings."""

    SENTINEL_CUSTOMER_ID: str | None = Field(default=None, alias="SENTINEL_CUSTOMER_ID")
    SENTINEL_LOG_TYPE: str = Field(default="DevSREBot", alias="SENTINEL_LOG_TYPE")
    SENTINEL_SHARED_KEY: str | None = Field(default=None, alias="SENTINEL_SHARED_KEY")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class TrelloSettings(BaseSettings):
    """Trello configuration settings."""

    TRELLO_APP_KEY: str | None = Field(default=None, alias="TRELLO_APP_KEY")
    TRELLO_TOKEN: str | None = Field(default=None, alias="TRELLO_TOKEN")
    TRELLO_ATIP_BOARD: str | None = Field(default=None, alias="TRELLO_ATIP_BOARD")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class AtipSettings(BaseSettings):
    """ATIP configuration settings."""

    ATIP_ANNOUNCE_CHANNEL: str | None = Field(
        default=None, alias="ATIP_ANNOUNCE_CHANNEL"
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class TalentRoleSettings(BaseSettings):
    """Talent Role configuration settings."""

    INTERNAL_TALENT_FOLDER: str = Field(default="", alias="INTERNAL_TALENT_FOLDER")
    SCORING_GUIDE_TEMPLATE: str = Field(default="", alias="SCORING_GUIDE_TEMPLATE")
    TEMPLATES_FOLDER: str = Field(default="", alias="TEMPLATES_FOLDER")
    CORE_VALUES_INTERVIEW_NOTES_TEMPLATE: str = Field(
        default="", alias="CORE_VALUES_INTERVIEW_NOTES_TEMPLATE"
    )
    TECHNICAL_INTERVIEW_NOTES_TEMPLATE: str = Field(
        default="", alias="TECHNICAL_INTERVIEW_NOTES_TEMPLATE"
    )
    INTAKE_FORM_TEMPLATE: str = Field(default="", alias="INTAKE_FORM_TEMPLATE")
    PHONE_SCREEN_TEMPLATE: str = Field(default="", alias="PHONE_SCREEN_TEMPLATE")
    RECRUITMENT_FEEDBACK_TEMPLATE: str = Field(
        default="", alias="RECRUITMENT_FEEDBACK_TEMPLATE"
    )
    PANELIST_GUIDEBOOK_TEMPLATE: str = Field(
        default="", alias="PANELIST_GUIDEBOOK_TEMPLATE"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class ReportsSettings(BaseSettings):
    """Reports configuration settings."""

    FOLDER_REPORTS_GOOGLE_GROUPS: str = Field(
        default="", alias="FOLDER_REPORTS_GOOGLE_GROUPS"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class AWSFeatureSettings(BaseSettings):
    """AWS Feature configuration settings."""

    AWS_ADMIN_GROUPS: list[str] = Field(
        default=["sre-ifs@cds-snc.ca"], alias="AWS_ADMIN_GROUPS"
    )
    AWS_OPS_GROUP_NAME: str = Field(default="", alias="AWS_OPS_GROUP_NAME")
    SPENDING_SHEET_ID: str = Field(default="", alias="SPENDING_SHEET_ID")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class IncidentFeatureSettings(BaseSettings):
    """Incident Feature configuration settings."""

    INCIDENT_CHANNEL: str | None = Field(default=None, alias="INCIDENT_CHANNEL")
    SLACK_SECURITY_USER_GROUP_ID: str | None = Field(
        default=None, alias="SLACK_SECURITY_USER_GROUP_ID"
    )
    INCIDENT_HANDBOOK_URL: str = Field(default="", alias="INCIDENT_HANDBOOK_URL")
    INCIDENT_TEMPLATE: str = Field(default="", alias="INCIDENT_TEMPLATE")
    INCIDENT_LIST: str = Field(default="", alias="INCIDENT_LIST")
    SRE_DRIVE_ID: str = Field(default="", alias="SRE_DRIVE_ID")
    SRE_INCIDENT_FOLDER: str = Field(default="", alias="SRE_INCIDENT_FOLDER")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class SreOpsSettings(BaseSettings):
    """SRE Ops configuration settings."""

    SRE_OPS_CHANNEL_ID: str = Field(default="", alias="SRE_OPS_CHANNEL_ID")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class GroupsFeatureSettings(BaseSettings):
    """Configuration for the groups feature and provider management.

    Providers Configuration (GROUP_PROVIDERS):
    -----------------------------------------
    Configure per-provider behavior including enable/disable, primary provider
    selection, prefix overrides, and capability overrides.

    Schema:
        providers: Dict[str, Dict[str, Any]]
            Key: Provider name (e.g., "google", "aws")
            Value: Provider configuration dict with the following fields:

            - enabled (bool, optional): Whether to activate this provider.
              Default: True. Set to False to disable a provider without
              removing configuration.

            - primary (bool, optional): Whether this provider is the primary.
              Exactly one provider must have primary=True. The primary provider
              is used for group creation and as the canonical source of truth.
              Default: False

            - prefix (str, optional): Override the provider's default prefix
              used for group key mapping. Non-primary providers should have
              a prefix to enable proper group name mapping.
              Example: "aws" for AWS Identity Center groups

            - capabilities (dict, optional): Override provider capabilities.
              Merged with provider defaults (config takes precedence).
              Available capability fields:
                * supports_user_creation (bool): Can create users
                * supports_user_deletion (bool): Can delete users
                * supports_group_creation (bool): Can create groups (always False)
                * supports_group_deletion (bool): Can delete groups (always False)
                * supports_member_management (bool): Can add/remove members
                * is_primary (bool): Mark as primary via capability
                * provides_role_info (bool): Provides role/membership type info
                * supports_batch_operations (bool): Supports batch operations
                * max_batch_size (int): Maximum batch operation size

    Example Configuration:
        GROUP_PROVIDERS = {
            "google": {
                "enabled": True,
                "primary": True,
                "capabilities": {
                    "provides_role_info": True,
                    "supports_member_management": True
                }
            },
            "aws": {
                "enabled": True,
                "prefix": "aws",
                "capabilities": {
                    "supports_member_management": True,
                    "supports_batch_operations": True,
                    "max_batch_size": 100
                }
            }
        }

    Validation:
        - Exactly one provider must have primary=True
        - Disabled providers (enabled=False) are excluded from activation
        - Non-primary providers should have a prefix for proper mapping
    """

    # Per-provider configuration. Each key is a provider name with a dict value
    providers: dict[str, dict] = Field(
        default_factory=dict,
        alias="GROUP_PROVIDERS",
        description="Per-provider configuration for enable/disable, primary selection, prefix, and capabilities",
    )

    @field_validator("providers", mode="after")
    @classmethod
    def _validate_providers_config(cls, v: Optional[Dict[str, dict]]):
        """Validation for GROUP_PROVIDERS configuration.

        Rules:
        - Filter to only enabled providers (enabled != False)
        - Ensure exactly one enabled provider has primary=True
        - Warn if non-primary enabled providers are missing prefix

        Disabled providers (enabled=False) are excluded from all validation
        checks since they won't be activated.
        """
        try:
            if not v or not isinstance(v, dict):
                return {}

            # Filter to only enabled providers
            enabled_providers = {
                pname: cfg
                for pname, cfg in v.items()
                if isinstance(cfg, dict) and cfg.get("enabled", True)
            }

            if not enabled_providers:
                logger.warning("no_enabled_providers_configured")
                return v

            # Count primary providers among enabled providers only
            primary_count = sum(
                1
                for cfg in enabled_providers.values()
                if isinstance(cfg, dict) and cfg.get("primary")
            )

            if primary_count != 1:
                # Fail-fast: require exactly one enabled primary provider
                raise ValueError(
                    f"GROUP_PROVIDERS configuration must contain exactly one enabled provider "
                    f"with 'primary': True. Found {primary_count} enabled primary provider(s)."
                )

            # Warn about enabled non-primary providers missing prefix
            for pname, cfg in enabled_providers.items():
                if not cfg.get("primary") and not cfg.get("prefix"):
                    logger.warning(
                        "provider_missing_prefix",
                        provider=pname,
                        msg=(
                            "Enabled non-primary provider has no 'prefix' configured; "
                            "mapping to primary provider may fail"
                        ),
                    )
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.warning(f"Could not validate providers configuration: {e}")
        return v

    # Reconciliation configuration
    reconciliation_enabled: bool = Field(
        default=True,
        alias="RECONCILIATION_ENABLED",
        description="Enable reconciliation for failed propagations",
    )

    reconciliation_backend: str = Field(
        default="memory",
        alias="RECONCILIATION_BACKEND",
        description="Reconciliation backend: 'memory', 'dynamodb', or 'sqs'",
    )

    reconciliation_max_attempts: int = Field(
        default=5,
        alias="RECONCILIATION_MAX_ATTEMPTS",
        description="Maximum retry attempts before moving to DLQ",
    )

    reconciliation_base_delay_seconds: int = Field(
        default=60,
        alias="RECONCILIATION_BASE_DELAY_SECONDS",
        description="Base delay for exponential backoff (seconds)",
    )

    reconciliation_max_delay_seconds: int = Field(
        default=3600,
        alias="RECONCILIATION_MAX_DELAY_SECONDS",
        description="Maximum delay for exponential backoff (seconds)",
    )

    # Circuit breaker configuration
    circuit_breaker_enabled: bool = Field(
        default=True,
        alias="CIRCUIT_BREAKER_ENABLED",
        description="Enable circuit breaker for providers to prevent cascading failures",
    )

    circuit_breaker_failure_threshold: int = Field(
        default=5,
        alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        description="Number of consecutive failures before opening circuit",
    )

    circuit_breaker_timeout_seconds: int = Field(
        default=60,
        alias="CIRCUIT_BREAKER_TIMEOUT_SECONDS",
        description="Seconds to wait before attempting recovery (HALF_OPEN state)",
    )

    circuit_breaker_half_open_max_calls: int = Field(
        default=3,
        alias="CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS",
        description="Maximum concurrent requests allowed in HALF_OPEN state",
    )

    # Justification enforcement configuration
    require_justification: bool = Field(
        default=True,
        alias="REQUIRE_JUSTIFICATION",
        description="Require justification for group operations",
    )

    min_justification_length: int = Field(
        default=10,
        alias="MIN_JUSTIFICATION_LENGTH",
        description="Minimum length for justification text",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        """Allow programmatic construction using the `providers` keyword.

        The field uses the alias `GROUP_PROVIDERS` for environment loading.
        When callers pass `providers=` directly (common in unit tests), map
        that to the alias so the normal BaseSettings initialization and
        validators (including the primary-provider check) run as expected.
        """
        if "providers" in kwargs and "GROUP_PROVIDERS" not in kwargs:
            # Move the programmatic `providers` into the alias key so
            # Pydantic/Settings machinery and field validators run.
            kwargs["GROUP_PROVIDERS"] = kwargs.pop("providers")
        super().__init__(**kwargs)


class ServerSettings(BaseSettings):
    """Server configuration settings."""

    BACKEND_URL: str = Field(default="http://127.0.0.1:8000", alias="BACKEND_URL")
    NOTIFY_OPS_CHANNEL_ID: str = Field(default="", alias="NOTIFY_OPS_CHANNEL_ID")
    GOOGLE_CLIENT_ID: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    SECRET_KEY: str | None = Field(default=None, alias="SESSION_SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ACCESS_TOKEN_MAX_AGE_MINUTES: int = 1440  # Defaults to 24 hours
    ISSUER_CONFIG: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        alias="ISSUER_CONFIG",
    )

    @field_validator("ISSUER_CONFIG", mode="before")
    @classmethod
    def validate_issuer_config(cls, v: Optional[Dict[str, Dict[str, Any]]]) -> Any:
        """Validate the ISSUER_CONFIG field.

        Args:
            cls: The class itself.
            v: The value of the ISSUER_CONFIG field.

        Returns:
            The validated value of the ISSUER_CONFIG field.
        """
        if v is None or not isinstance(v, dict):
            return {}
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class DevSettings(BaseSettings):
    """Development environment configuration settings."""

    SLACK_DEV_MSG_CHANNEL: str = Field(default="", alias="SLACK_DEV_MSG_CHANNEL")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class FrontEndSettings(BaseSettings):
    FRONTEND_URL: str = Field(default="http://127.0.0.1:3000", alias="FRONTEND_URL")
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


class Settings(BaseSettings):
    """SRE Bot configuration settings."""

    PREFIX: str = ""
    LOG_LEVEL: str = "INFO"
    GIT_SHA: str = "Unknown"

    # Server settings
    server: ServerSettings
    frontend: FrontEndSettings

    # Integration settings
    slack: SlackSettings
    aws: AwsSettings
    google_workspace: GoogleWorkspaceSettings
    maxmind: MaxMindSettings
    notify: NotifySettings
    opsgenie: OpsGenieSettings
    sentinel: SentinelSettings
    trello: TrelloSettings

    # Functionality settings
    atip: AtipSettings
    talent_role: TalentRoleSettings
    reports: ReportsSettings
    aws_feature: AWSFeatureSettings
    feat_incident: IncidentFeatureSettings
    sre_ops: SreOpsSettings
    groups: GroupsFeatureSettings

    # Development settings
    dev: DevSettings

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production."""
        return not bool(self.PREFIX)

    def __init__(self, **kwargs):
        settings_map = {
            "server": ServerSettings,
            "frontend": FrontEndSettings,
            "slack": SlackSettings,
            "aws": AwsSettings,
            "google_workspace": GoogleWorkspaceSettings,
            "maxmind": MaxMindSettings,
            "notify": NotifySettings,
            "opsgenie": OpsGenieSettings,
            "sentinel": SentinelSettings,
            "trello": TrelloSettings,
            "atip": AtipSettings,
            "talent_role": TalentRoleSettings,
            "reports": ReportsSettings,
            "aws_feature": AWSFeatureSettings,
            "feat_incident": IncidentFeatureSettings,
            "sre_ops": SreOpsSettings,
            "dev": DevSettings,
            "groups": GroupsFeatureSettings,
        }

        for setting_name, setting_class in settings_map.items():
            if setting_name not in kwargs:
                kwargs[setting_name] = setting_class()

        super().__init__(**kwargs)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


# Create the settings instance
settings = Settings()

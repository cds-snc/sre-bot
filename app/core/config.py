"""SRE Bot configuration settings."""

from typing import Any, Dict, Optional
import json
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

    GCP_SRE_SERVICE_ACCOUNT_KEY_FILE: str = Field(
        default="", alias="GCP_SRE_SERVICE_ACCOUNT_KEY_FILE"
    )

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


class GoogleResourcesConfig(BaseSettings):
    """Consolidated Google Drive/Document resources configuration.

    Stores all Google resource IDs (folders, documents, sheets) in a
    single compact JSON structure to reduce AWS Parameter Store footprint.

    Structure:
        {
            "inc": {  # Incident resources
                "d": <drive_id>,
                "f": <folder_id>,
                "t": <template_id>,
                "l": <list_id>,
                "h": <handbook_id>
            },
            "tal": {  # Talent role resources
                "i": <internal_folder_id>,
                "s": <scoring_guide_id>,
                "t": <templates_folder_id>,
                "c": <core_values_notes_id>,
                "tech": <technical_notes_id>,
                "int": <intake_form_id>,
                "ph": <phone_screen_id>,
                "rec": <recruitment_feedback_id>,
                "pan": <panelist_guidebook_id>
            },
            "rep": {  # Reports resources
                "g": <google_groups_folder_id>
            },
            "aws": {  # AWS resources
                "s": <spending_sheet_id>
            },
            "cal": {  # Calendar resources
                "sre": <sre_calendar_id>
            },
        }
    """

    resources: Any = Field(
        default_factory=dict,
        alias="GOOGLE_RESOURCES",
        description="Consolidated Google resources in nested dict format",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("resources", mode="before")
    @classmethod
    def _parse_resources(cls, v: Optional[Any]) -> Any:
        """Allow `GOOGLE_RESOURCES` to be provided as a JSON string (possibly
        wrapped in single or double quotes) or as a native dict.

        This makes the settings more robust when the environment or parameter
        store contains an extra layer of quoting.
        """
        if v is None:
            return {}

        # If already a dict, return as-is
        if isinstance(v, dict):
            return v

        # If a string, try to strip surrounding quotes and parse JSON
        if isinstance(v, str):
            s = v.strip()
            if (s.startswith("'") and s.endswith("'")) or (
                s.startswith('"') and s.endswith('"')
            ):
                s = s[1:-1]
            try:
                parsed = json.loads(s) if s else {}
                return parsed
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(
                    f"Invalid GOOGLE_RESOURCES JSON: {e} (value: {s[:80]}...)"
                ) from e

        # Fallback: invalid type
        raise ValueError("GOOGLE_RESOURCES must be a JSON string or a mapping")

    def _get_resource(self, scope: str, key: str) -> str:
        """Helper to safely retrieve a resource ID."""
        raw = getattr(self, "resources", {}) or {}
        if not isinstance(raw, dict):
            return ""
        scope_dict = raw.get(scope, {})
        return scope_dict.get(key, "") if isinstance(scope_dict, dict) else ""

    # --- Incident Resources ---
    @property
    def incident_drive_id(self) -> str:
        """SRE Drive ID for incident management."""
        return self._get_resource("inc", "d")

    @property
    def incident_folder_id(self) -> str:
        """Incident folder ID in Google Drive."""
        return self._get_resource("inc", "f")

    @property
    def incident_template_id(self) -> str:
        """Incident document template ID."""
        return self._get_resource("inc", "t")

    @property
    def incident_list_id(self) -> str:
        """Incident tracking spreadsheet ID."""
        return self._get_resource("inc", "l")

    @property
    def incident_handbook_id(self) -> str:
        """Incident handbook document ID."""
        return self._get_resource("inc", "h")

    # --- Talent Role Resources ---
    @property
    def internal_talent_folder_id(self) -> str:
        """Internal talent management folder."""
        return self._get_resource("tal", "i")

    @property
    def scoring_guide_template_id(self) -> str:
        """Scoring guide template document ID."""
        return self._get_resource("tal", "s")

    @property
    def templates_folder_id(self) -> str:
        """Talent templates folder ID."""
        return self._get_resource("tal", "t")

    @property
    def core_values_interview_notes_id(self) -> str:
        """Core values interview notes template ID."""
        return self._get_resource("tal", "c")

    @property
    def technical_interview_notes_id(self) -> str:
        """Technical interview notes template ID."""
        return self._get_resource("tal", "tech")

    @property
    def intake_form_template_id(self) -> str:
        """Intake form template ID."""
        return self._get_resource("tal", "int")

    @property
    def phone_screen_template_id(self) -> str:
        """Phone screen template ID."""
        return self._get_resource("tal", "ph")

    @property
    def recruitment_feedback_template_id(self) -> str:
        """Recruitment feedback template ID."""
        return self._get_resource("tal", "rec")

    @property
    def panelist_guidebook_template_id(self) -> str:
        """Panelist guidebook template ID."""
        return self._get_resource("tal", "pan")

    # --- Reports Resources ---
    @property
    def google_groups_reports_folder_id(self) -> str:
        """Google Groups reports folder ID."""
        return self._get_resource("rep", "g")

    # --- AWS Resources ---
    @property
    def spending_sheet_id(self) -> str:
        """AWS Spending Google Sheet ID."""
        return self._get_resource("aws", "s")

    # --- Calendar Resources ---
    @property
    def sre_calendar_id(self) -> str:
        """SRE Calendar ID."""
        return self._get_resource("cal", "sre")


class AWSFeatureSettings(BaseSettings):
    """AWS Feature configuration settings."""

    AWS_ADMIN_GROUPS: list[str] = Field(
        default=["sre-ifs@cds-snc.ca"], alias="AWS_ADMIN_GROUPS"
    )
    AWS_OPS_GROUP_NAME: str = Field(default="", alias="AWS_OPS_GROUP_NAME")
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

    @field_validator("providers", mode="before")
    @classmethod
    def _parse_providers(cls, v: Optional[Any]) -> Any:
        """Parse GROUP_PROVIDERS from JSON string (environment variable) or dict.

        Handles JSON string input from environment variables, with or without
        surrounding quotes.
        """
        if v is None:
            return {}

        # If already a dict, return as-is
        if isinstance(v, dict):
            return v

        # If a string, try to strip surrounding quotes and parse JSON
        if isinstance(v, str):
            s = v.strip()
            if (s.startswith("'") and s.endswith("'")) or (
                s.startswith('"') and s.endswith('"')
            ):
                s = s[1:-1]
            try:
                parsed = json.loads(s) if s else {}
                return parsed
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(
                    f"Invalid GROUP_PROVIDERS JSON: {e} (value: {s[:80]}...)"
                ) from e

        # Fallback: invalid type
        raise ValueError("GROUP_PROVIDERS must be a JSON string or a mapping")

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

    # Group domain configuration for email-based providers
    group_domain: str = Field(
        default="",
        alias="GROUP_DOMAIN",
        description="Domain suffix for group email addresses (e.g., 'cds-snc.ca'). "
        "Used by primary provider when full email format is required.",
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


class CommandsSettings(BaseSettings):
    """Configuration for command adapters and platform integrations.

    Command Providers Configuration (COMMAND_PROVIDERS):
    ---------------------------------------------------
    Configure per-provider behavior including enable/disable and platform-specific
    settings for command adapters (Slack, Teams, Discord, etc.).

    Schema:
        providers: Dict[str, Dict[str, Any]]
            Key: Provider name (e.g., "slack", "teams", "discord")
            Value: Provider configuration dict with the following fields:

            - enabled (bool, optional): Whether to activate this command provider.
              Default: True. Set to False to disable without removing config.

            - Additional provider-specific fields as needed

    Example Configuration:
        COMMAND_PROVIDERS = {
            "slack": {
                "enabled": True
            },
            "teams": {
                "enabled": False
            }
        }

    Scenarios:
        1. No providers enabled -> API-only mode (commands disabled)
        2. One provider enabled -> Single platform mode
        3. Multiple providers enabled -> Multi-platform mode

    Validation:
        - At least zero providers enabled (API-only is valid)
        - Enabled providers must have required configuration
    """

    # Per-provider configuration. Each key is a provider name with a dict value
    providers: dict[str, dict] = Field(
        default_factory=dict,
        alias="COMMAND_PROVIDERS",
        description="Per-provider configuration for command adapters",
    )

    @field_validator("providers", mode="before")
    @classmethod
    def _parse_providers(cls, v: Optional[Any]) -> Any:
        """Parse COMMAND_PROVIDERS from JSON string (environment variable) or dict.

        Handles JSON string input from environment variables, with or without
        surrounding quotes.
        """
        if v is None:
            return {}

        # If already a dict, return as-is
        if isinstance(v, dict):
            return v

        # If a string, try to strip surrounding quotes and parse JSON
        if isinstance(v, str):
            s = v.strip()
            if (s.startswith("'") and s.endswith("'")) or (
                s.startswith('"') and s.endswith('"')
            ):
                s = s[1:-1]
            try:
                parsed = json.loads(s) if s else {}
                return parsed
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(
                    f"Invalid COMMAND_PROVIDERS JSON: {e} (value: {s[:80]}...)"
                ) from e

        # Fallback: invalid type
        raise ValueError("COMMAND_PROVIDERS must be a JSON string or a mapping")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


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


class Settings(BaseSettings):
    """SRE Bot configuration settings."""

    PREFIX: str = ""
    LOG_LEVEL: str = "INFO"
    GIT_SHA: str = "Unknown"

    # Server settings
    server: ServerSettings

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
    aws_feature: AWSFeatureSettings
    feat_incident: IncidentFeatureSettings
    sre_ops: SreOpsSettings
    groups: GroupsFeatureSettings
    google_resources: GoogleResourcesConfig
    commands: CommandsSettings

    # Development settings
    dev: DevSettings

    @property
    def is_production(self) -> bool:
        """Check if the application is running in production."""
        return not bool(self.PREFIX)

    def __init__(self, **kwargs):
        settings_map = {
            "server": ServerSettings,
            "slack": SlackSettings,
            "aws": AwsSettings,
            "google_workspace": GoogleWorkspaceSettings,
            "maxmind": MaxMindSettings,
            "notify": NotifySettings,
            "opsgenie": OpsGenieSettings,
            "sentinel": SentinelSettings,
            "trello": TrelloSettings,
            "atip": AtipSettings,
            "aws_feature": AWSFeatureSettings,
            "feat_incident": IncidentFeatureSettings,
            "sre_ops": SreOpsSettings,
            "dev": DevSettings,
            "groups": GroupsFeatureSettings,
            "google_resources": GoogleResourcesConfig,
            "commands": CommandsSettings,
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

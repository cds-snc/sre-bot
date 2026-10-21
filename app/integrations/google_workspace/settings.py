"""Vendor settings for the Google Workspace API client.

Exposes ``GoogleWorkspaceSettings``, its tenant entry ``GoogleWorkspaceTenant``, and the
cached ``get_google_workspace_settings()`` provider. Each field reads the environment variable of the same name.

Also holds ``GoogleResourcesConfig`` (GOOGLE_RESOURCES) and ``get_google_resources_config()``:
the Google document and folder ids of several features, tolerated here until TASK-111
splits them into the owning feature slices.
"""

import json
from functools import lru_cache
from typing import Any, cast

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger().bind(component="config.google")


class GoogleWorkspaceTenant(BaseModel):
    """The Google Workspace tenant this instance works with, and the credential that reaches it."""

    model_config = ConfigDict(frozen=True)

    customer_id: str = Field(description="Real Google Workspace customer id, never the my_customer alias.")
    service_account_key: str = Field(repr=False, description="Service-account key JSON for this tenant.")


class GoogleWorkspaceSettings(BaseSettings):
    """Google Workspace configuration settings.

    Environment Variables:
        GOOGLE_DELEGATED_ADMIN_EMAIL: Admin email for domain-wide delegation
        SRE_BOT_EMAIL: SRE Bot service account email
        GOOGLE_WORKSPACE_CUSTOMER_ID: Real Google Workspace customer id (no default)
        GCP_SRE_SERVICE_ACCOUNT_KEY_FILE: Service-account key JSON
        GOOGLE_API_NUM_RETRIES: Number of automatic retries for transient Google API failures
        GOOGLE_API_TIMEOUT_SECONDS: Per-attempt HTTP timeout in seconds for Google API calls (defaults to 10.0)

    The two keys are the source of the interim Google tenant entry
    (``GoogleWorkspaceTenant``, read through ``tenant``) until TASK-111 makes the
    entry a nested field (decisions/configuration.md); readers use the entry,
    never the flat fields. The entry is present when either key is set, and a
    present entry needs both: the key, and the real customer id, non-blank and
    not the my_customer API alias. Each failure names its variable. The id is
    opaque (Google documents no format), so no pattern is checked and no network
    call is made. With neither key set, Google is not configured.

    Example:
        ```python
        from integrations.google_workspace.settings import get_google_workspace_settings

        settings = get_google_workspace_settings()

        admin_email = settings.google_delegated_admin_email
        tenant = settings.tenant
        ```
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    google_delegated_admin_email: str = Field(default="")
    sre_bot_email: str = Field(default="")
    google_workspace_customer_id: str | None = Field(default=None)
    gcp_sre_service_account_key_file: str = Field(default="")
    google_api_num_retries: int = Field(
        default=3,
        description="Number of automatic retries googleapiclient applies to transient (429/5xx) API call failures, configured once at service construction.",
    )
    google_api_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        description="Per-attempt HTTP timeout in seconds for every Google Workspace API client, configured once at service construction. Defaults to 10.0; must be positive.",
    )

    @property
    def tenant(self) -> GoogleWorkspaceTenant | None:
        """Return the Google tenant entry, or None when Google is not configured."""
        if self.google_workspace_customer_id is None or not self.gcp_sre_service_account_key_file:
            return None
        return GoogleWorkspaceTenant(
            customer_id=self.google_workspace_customer_id.strip(),
            service_account_key=self.gcp_sre_service_account_key_file,
        )

    @field_validator("google_workspace_customer_id", mode="before")
    @classmethod
    def _empty_customer_id_is_absent(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _validate_tenant_entry(self) -> GoogleWorkspaceSettings:
        if self.google_workspace_customer_id is None and not self.gcp_sre_service_account_key_file:
            return self
        if not self.gcp_sre_service_account_key_file:
            raise ValueError("GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is required when GOOGLE_WORKSPACE_CUSTOMER_ID is set")
        customer_id = (self.google_workspace_customer_id or "").strip()
        if not customer_id or customer_id == "my_customer":
            raise ValueError(
                "GOOGLE_WORKSPACE_CUSTOMER_ID must be the real Google Workspace customer id, not blank or the "
                "my_customer alias, when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is set"
            )
        return self


class GoogleResourcesConfig(BaseSettings):
    """Consolidated Google Drive/Document resources configuration.

    Feature data, not vendor settings: it waits here until TASK-111 splits it into
    the owning feature slices (decisions/configuration.md).

    Stores all Google resource IDs (folders, documents, sheets) in a
    single compact JSON structure to reduce AWS Parameter Store footprint.

    Environment Variables:
        GOOGLE_RESOURCES: JSON dict of resource IDs organized by domain

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
            "aws": {  # AWS resources
                "s": <spending_sheet_id>
            },
            "cal": {  # Calendar resources
                "sre": <sre_calendar_id>
            },
        }

    Example:
        ```python
        from integrations.google_workspace.settings import get_google_resources_config

        settings = get_google_resources_config()

        incident_drive = settings.incident_drive_id
        incident_folder = settings.incident_folder_id
        ```
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    resources: dict[str, Any] = Field(
        default_factory=dict,
        alias="GOOGLE_RESOURCES",
        description="Consolidated Google resources in nested dict format",
    )

    @field_validator("resources", mode="before")
    @classmethod
    def _parse_resources(cls, v: Any | None) -> dict[str, Any]:
        """Parse GOOGLE_RESOURCES from JSON string or dict."""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            s = v.strip()
            if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
                s = s[1:-1]
            try:
                return dict(cast(dict[str, Any], json.loads(s)))
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("failed_to_parse_google_resources", error=str(e))
                raise ValueError(f"GOOGLE_RESOURCES must be valid JSON: {e}") from e
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


@lru_cache(maxsize=1)
def get_google_workspace_settings() -> GoogleWorkspaceSettings:
    """Singleton provider for Google Workspace integration settings."""
    return GoogleWorkspaceSettings()


@lru_cache(maxsize=1)
def get_google_resources_config() -> GoogleResourcesConfig:
    """Singleton provider for Google Resources configuration."""
    return GoogleResourcesConfig()

"""Google Workspace vendor settings slice: the [google_workspace] table of the configuration files.

Exposes ``GoogleWorkspaceSettings``, its tenant entry ``GoogleWorkspaceTenant``, and the
cached ``get_google_workspace_settings()`` provider.

Non-secret values (retries, per-attempt timeout) come from [google_workspace]. The
tenant entry is read only from the environment as GOOGLE_WORKSPACE__TENANT__<FIELD>:
the customer id and the delegated user are non-public values and the service-account
key a secret (decisions/configuration.md), so no configuration file names the tenant.
A customer id needs the key, and the key or the delegated user set without a customer
id fails, so Google is never half configured. Which principal and scopes each caller
uses is TASK-169's.

Also holds ``GoogleResourcesConfig`` (GOOGLE_RESOURCES) and ``get_google_resources_config()``:
the Google document and folder ids of several features, tolerated here until TASK-111.10.3
gives each id its own key.
"""

import json
from functools import lru_cache
from typing import Any, cast

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from contracts.configuration import ConfigurationSlice

logger = structlog.get_logger().bind(component="config.google")

# The tenant entry's fields, read from the environment as GOOGLE_WORKSPACE__TENANT__<FIELD>; empty counts as unset.
_TENANT_FIELDS = ("customer_id", "service_account_key", "delegated_user_email")
_TENANT_VARIABLE = "GOOGLE_WORKSPACE__TENANT__{}"


class GoogleWorkspaceTenant(BaseModel):
    """The Google Workspace tenant this instance works with, and the credential that reaches it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    customer_id: str = Field(
        repr=False, description="Real Google Workspace customer id, never the my_customer alias; a non-public value."
    )
    service_account_key: str = Field(repr=False, description="Service-account key JSON for this tenant.")
    delegated_user_email: str | None = Field(
        default=None,
        repr=False,
        description="Workspace user the service account impersonates when a caller names none; a non-public value.",
    )

    @field_validator("customer_id")
    @classmethod
    def _real_customer_id(cls, value: str) -> str:
        # The id is opaque (Google documents no format), so only blankness and the alias are checked.
        value = value.strip()
        if not value or value == "my_customer":
            raise ValueError("customer_id must be the real Google Workspace customer id, not blank or my_customer")
        return value


class GoogleWorkspaceSettings(ConfigurationSlice):
    """Vendor credential, tenant and tuning settings for Google Workspace.

    Keys of [google_workspace]:
        api_num_retries, api_timeout_seconds.

    Environment only (the tenant entry; no tenant without a customer id):
        GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID, GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY,
        GOOGLE_WORKSPACE__TENANT__DELEGATED_USER_EMAIL. An empty value counts as unset.
    """

    model_config = SettingsConfigDict(toml_table_header=("google_workspace",), env_prefix="GOOGLE_WORKSPACE__")

    tenant: GoogleWorkspaceTenant | None = Field(
        default=None, description="The Google Workspace tenant this instance works with."
    )
    api_num_retries: int = Field(
        default=3,
        description="Number of automatic retries googleapiclient applies to transient (429/5xx) API call failures, configured once at service construction.",
    )
    api_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        description="Per-attempt HTTP timeout in seconds for every Google Workspace API client, configured once at service construction; must be positive.",
    )

    @model_validator(mode="before")
    @classmethod
    def _tenant_and_its_values_go_together(cls, data: Any) -> Any:
        # Before validation: pydantic's own errors would not name the variable, and an empty key
        # would build a half tenant.
        if not isinstance(data, dict) or not isinstance(data.get("tenant"), dict):
            return data
        tenant = {key: value for key, value in data["tenant"].items() if not (key in _TENANT_FIELDS and value == "")}
        customer_id = _TENANT_VARIABLE.format("CUSTOMER_ID")
        if "customer_id" not in tenant:
            for field in _TENANT_FIELDS[1:]:
                if field in tenant:
                    raise ValueError(f"{_TENANT_VARIABLE.format(field.upper())} is set but {customer_id} is not")
            # Anything else in the entry is left for validation to reject as an unknown key.
            return {**data, "tenant": tenant or None}
        if "service_account_key" not in tenant:
            raise ValueError(f"{_TENANT_VARIABLE.format('SERVICE_ACCOUNT_KEY')} is required when {customer_id} is set")
        return {**data, "tenant": tenant}


class GoogleResourcesConfig(BaseSettings):
    """Consolidated Google Drive/Document resources configuration.

    Feature data, not vendor settings: it waits here until TASK-111.10.3 gives each
    id its own key (decisions/configuration.md).

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

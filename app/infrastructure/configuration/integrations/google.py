"""Google Workspace integration settings."""

import json
from typing import Any, Optional

from pydantic import Field, field_validator
import structlog

from infrastructure.configuration.base import IntegrationSettings

logger = structlog.stdlib.get_logger().bind(component="config.google")


class GoogleWorkspaceSettings(IntegrationSettings):
    """Google Workspace configuration settings.

    Environment Variables:
        GOOGLE_DELEGATED_ADMIN_EMAIL: Admin email for domain-wide delegation
        SRE_BOT_EMAIL: SRE Bot service account email
        GOOGLE_WORKSPACE_CUSTOMER_ID: Google Workspace customer ID
        GCP_SRE_SERVICE_ACCOUNT_KEY_FILE: Path to service account key file

    Example:
        ```python
        from infrastructure.configuration import settings

        admin_email = settings.google_workspace.GOOGLE_DELEGATED_ADMIN_EMAIL
        customer_id = settings.google_workspace.GOOGLE_WORKSPACE_CUSTOMER_ID
        ```
    """

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


class GoogleResourcesConfig(IntegrationSettings):
    """Consolidated Google Drive/Document resources configuration.

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

    Example:
        ```python
        from infrastructure.configuration import settings

        incident_drive = settings.google_resources.incident_drive_id
        incident_folder = settings.google_resources.incident_folder_id
        ```
    """

    resources: Any = Field(
        default_factory=dict,
        alias="GOOGLE_RESOURCES",
        description="Consolidated Google resources in nested dict format",
    )

    @field_validator("resources", mode="before")
    @classmethod
    def _parse_resources(cls, v: Optional[Any]) -> Any:
        """Parse GOOGLE_RESOURCES from JSON string or dict."""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            s = v.strip()
            if (s.startswith("'") and s.endswith("'")) or (
                s.startswith('"') and s.endswith('"')
            ):
                s = s[1:-1]
            try:
                return json.loads(s)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error("failed_to_parse_google_resources", error=str(e))
                raise ValueError(f"GOOGLE_RESOURCES must be valid JSON: {e}")
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

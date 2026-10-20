"""Vendor settings for the Google Workspace API client.

Exposes ``GoogleWorkspaceSettings`` and the cached ``get_google_workspace_settings()``
provider. Each field reads the environment variable of the same name.
"""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GoogleWorkspaceSettings(BaseSettings):
    """Google Workspace configuration settings.

    Environment Variables:
        GOOGLE_DELEGATED_ADMIN_EMAIL: Admin email for domain-wide delegation
        SRE_BOT_EMAIL: SRE Bot service account email
        GOOGLE_WORKSPACE_CUSTOMER_ID: Google Workspace customer ID (defaults to "my_customer"
            while Google is not in use; the real id is required once it is)
        GCP_SRE_SERVICE_ACCOUNT_KEY_FILE: Path to service account key file
        GOOGLE_API_NUM_RETRIES: Number of automatic retries for transient Google API failures
        GOOGLE_API_TIMEOUT_SECONDS: Per-attempt HTTP timeout in seconds for Google API calls (defaults to 10.0)

    Google is in use when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is set (the interim
    signal until the Google tenant entry exists, decisions/configuration.md).
    Then GOOGLE_WORKSPACE_CUSTOMER_ID must be the real customer id: non-blank
    and not the my_customer API alias. The id is opaque (Google documents no
    format), so no pattern is checked and no network call is made.

    Example:
        ```python
        from integrations.google_workspace.settings import get_google_workspace_settings

        settings = get_google_workspace_settings()

        admin_email = settings.GOOGLE_DELEGATED_ADMIN_EMAIL
        customer_id = settings.GOOGLE_WORKSPACE_CUSTOMER_ID
        ```
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    GOOGLE_DELEGATED_ADMIN_EMAIL: str = Field(default="", alias="GOOGLE_DELEGATED_ADMIN_EMAIL")
    SRE_BOT_EMAIL: str = Field(default="", alias="SRE_BOT_EMAIL")
    GOOGLE_WORKSPACE_CUSTOMER_ID: str = Field(default="my_customer", alias="GOOGLE_WORKSPACE_CUSTOMER_ID")
    GCP_SRE_SERVICE_ACCOUNT_KEY_FILE: str = Field(default="", alias="GCP_SRE_SERVICE_ACCOUNT_KEY_FILE")
    GOOGLE_API_NUM_RETRIES: int = Field(
        default=3,
        alias="GOOGLE_API_NUM_RETRIES",
        description="Number of automatic retries googleapiclient applies to transient (429/5xx) API call failures, configured once at service construction.",
    )
    GOOGLE_API_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        alias="GOOGLE_API_TIMEOUT_SECONDS",
        gt=0,
        description="Per-attempt HTTP timeout in seconds for every Google Workspace API client, configured once at service construction. Defaults to 10.0; must be positive.",
    )

    @model_validator(mode="after")
    def _require_real_customer_id_when_in_use(self) -> GoogleWorkspaceSettings:
        if not self.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE:
            return self
        customer_id = self.GOOGLE_WORKSPACE_CUSTOMER_ID.strip()
        if not customer_id or customer_id == "my_customer":
            raise ValueError(
                "GOOGLE_WORKSPACE_CUSTOMER_ID must be the real Google Workspace customer id, not blank or the "
                "my_customer alias, when GCP_SRE_SERVICE_ACCOUNT_KEY_FILE is set"
            )
        return self


@lru_cache(maxsize=1)
def get_google_workspace_settings() -> GoogleWorkspaceSettings:
    """Singleton provider for Google Workspace integration settings."""
    return GoogleWorkspaceSettings()

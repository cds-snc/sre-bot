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
"""

import json
from functools import lru_cache
from typing import Any, cast

from google.oauth2 import service_account
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only

# The tenant entry's fields, read from the environment as GOOGLE_WORKSPACE__TENANT__<FIELD>; empty counts as unset.
_TENANT_FIELDS = ("customer_id", "service_account_key", "delegated_user_email")
_TENANT_VARIABLE = "GOOGLE_WORKSPACE__TENANT__{}"
# The fields google-auth needs to build service-account credentials locally.
_KEY_FIELDS = ("client_email", "private_key", "token_uri")


def build_service_account_credentials(raw_key: str) -> service_account.Credentials:
    """Shape-check a service-account key and build its credentials, with no network call.

    Strict JSON (a private_key with literal newlines fails), type service_account, the
    fields google-auth needs, and a private key it can load into a signer. Every message
    describes the problem, never the key. A revoked key or a missing delegation only shows
    when the first token is fetched (client.py).
    """
    try:
        info = json.loads(raw_key)
    except json.JSONDecodeError as error:
        raise ValueError(f"is not valid JSON ({error.msg} at line {error.lineno} column {error.colno})") from None
    if not isinstance(info, dict):
        raise ValueError("is not a JSON object")
    if info.get("type") != "service_account":
        raise ValueError("is not a service-account key (type must be service_account)")
    missing = [field for field in _KEY_FIELDS if not info.get(field)]
    if missing:
        raise ValueError(f"is missing {', '.join(missing)}")
    try:
        return cast(service_account.Credentials, service_account.Credentials.from_service_account_info(info))
    except Exception:
        # The library's message may quote the key material, so only the problem is named.
        raise ValueError("has a private_key that cannot be loaded") from None


class GoogleWorkspaceTenant(BaseModel):
    """The Google Workspace tenant this instance works with, and the credential that reaches it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    _credentials: service_account.Credentials = PrivateAttr()

    customer_id: str = env_only(
        "Real Google Workspace customer id, never the my_customer alias; a non-public value.", "codespaces"
    )
    service_account_key: str = env_only("Service-account key JSON for this tenant.", "codespaces")
    delegated_user_email: str | None = env_only(
        "Workspace user the service account impersonates when a caller names none; a non-public value.",
        "codespaces",
        default=None,
    )

    @field_validator("customer_id")
    @classmethod
    def _real_customer_id(cls, value: str) -> str:
        # The id is opaque (Google documents no format), so only blankness and the alias are checked.
        value = value.strip()
        if not value or value == "my_customer":
            raise ValueError("customer_id must be the real Google Workspace customer id, not blank or my_customer")
        return value

    @model_validator(mode="after")
    def _key_builds_credentials(self) -> GoogleWorkspaceTenant:
        # Raised as a field error so the configuration error names the key's variable.
        try:
            self._credentials = build_service_account_credentials(self.service_account_key)
        except ValueError as error:
            raise ValueError(f"{_TENANT_VARIABLE.format('SERVICE_ACCOUNT_KEY')} {error}") from None
        return self

    @property
    def credentials(self) -> service_account.Credentials:
        """The tenant's base credentials, built once at boot; callers derive subject and scopes per call."""
        return self._credentials


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


@lru_cache(maxsize=1)
def get_google_workspace_settings() -> GoogleWorkspaceSettings:
    """Singleton provider for Google Workspace integration settings."""
    return GoogleWorkspaceSettings()

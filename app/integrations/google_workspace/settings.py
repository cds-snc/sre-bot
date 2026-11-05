"""Google Workspace vendor settings slice: the [google_workspace] table of the configuration files.

Exposes ``GoogleWorkspaceSettings``, its tenant entry ``GoogleWorkspaceTenant``, and the
cached ``get_google_workspace_settings()`` provider.

Non-secret values (retries, per-attempt timeout) come from [google_workspace]. The
tenant entry is read only from the environment as GOOGLE_WORKSPACE__TENANT__<FIELD>:
the customer id, the service-account email and the delegated user are non-public values
and the key a secret (decisions/configuration.md), so no configuration file names the
tenant. A customer id needs a credential source, chosen in this order: the federation
audience with the service-account email (AWS federation, the ECS adapter), the key
(tolerated until TASK-182; a set email must be its account), then the email alone
(application default credentials). Any tenant value without a customer id fails, so Google
is never half configured, and no tenant entry leaves Google unconfigured.
"""

import json
import re
from functools import lru_cache
from typing import Any, Literal, cast

import botocore.session
from google.oauth2 import service_account
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only

# The tenant entry's fields, read from the environment as GOOGLE_WORKSPACE__TENANT__<FIELD>; empty counts as unset.
_TENANT_FIELDS = (
    "customer_id",
    "service_account_key",
    "delegated_user_email",
    "service_account_email",
    "federation_audience",
)
_TENANT_VARIABLE = "GOOGLE_WORKSPACE__TENANT__{}"
# A workload identity provider's audience: project number, pool and provider ids of 4 to 32 [a-z0-9-].
_AUDIENCE = re.compile(
    r"^//iam\.googleapis\.com/projects/\d+/locations/global/workloadIdentityPools/[a-z0-9-]{4,32}/providers/[a-z0-9-]{4,32}$"
)

type Authentication = Literal["aws_federation", "key", "application_default"]
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


def _variable(field: str) -> str:
    return _TENANT_VARIABLE.format(field.upper())


class GoogleWorkspaceTenant(BaseModel):
    """The Google Workspace tenant this instance works with, and how the bot proves its identity to it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    _authentication: Authentication = PrivateAttr()
    _credentials: service_account.Credentials | None = PrivateAttr(default=None)
    _aws_region: str | None = PrivateAttr(default=None)

    customer_id: str = env_only(
        "Real Google Workspace customer id, never the my_customer alias; a non-public value.", "codespaces"
    )
    service_account_key: SecretStr | None = env_only(
        "Service-account key JSON for this tenant; tolerated until TASK-182, ignored when the federation audience is set.",
        "codespaces",
        default=None,
    )
    delegated_user_email: str | None = env_only(
        "Workspace user the service account impersonates when a caller names none; a non-public value.",
        "codespaces",
        default=None,
    )
    service_account_email: str | None = env_only(
        "The bot's GCP service account, impersonated keylessly; must be the key's account while a key is set; "
        "a non-public value (it holds domain privileges).",
        "codespaces",
        default=None,
    )
    federation_audience: str | None = env_only(
        "Workload identity provider audience the ECS task role federates through "
        "(//iam.googleapis.com/projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>); "
        "unset outside ECS.",
        "local",
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

    @field_validator("service_account_email")
    @classmethod
    def _an_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if "@" not in value.strip("@"):
            raise ValueError(f"{_variable('service_account_email')} is not a service-account email address")
        return value

    @model_validator(mode="after")
    def _choose_the_credential_source(self) -> GoogleWorkspaceTenant:
        # Raised as field errors so the configuration error names the variable; no network call.
        # The client builds the chosen source on the first call (client.py, credential_source).
        if self.federation_audience is not None:
            self._aws_region = self._aws_federation_region()
            self._authentication = "aws_federation"
        elif self.service_account_key is not None:
            self._credentials = self._key_credentials(self.service_account_key)
            self._authentication = "key"
        else:
            # The settings slice guarantees the email when neither the audience nor the key is set.
            self._authentication = "application_default"
        return self

    def _aws_federation_region(self) -> str:
        audience_name = _variable("federation_audience")
        if not _AUDIENCE.match(str(self.federation_audience)):
            raise ValueError(
                f"{audience_name} is not a workload identity provider audience "
                "(//iam.googleapis.com/projects/<project number>/locations/global/workloadIdentityPools/<pool id>/providers/<provider id>)"
            )
        # botocore reads the region from the environment and its config files, without network.
        session = botocore.session.get_session()
        region = session.get_config_variable("region")
        if not region:
            raise ValueError(f"{audience_name} is set but no AWS region is configured (AWS_REGION)")
        return str(region)

    def _key_credentials(self, key: SecretStr) -> service_account.Credentials:
        try:
            credentials = build_service_account_credentials(key.get_secret_value())
        except ValueError as error:
            raise ValueError(f"{_variable('service_account_key')} {error}") from None
        if self.service_account_email is not None and credentials.service_account_email != self.service_account_email:
            raise ValueError(
                f"{_variable('service_account_email')} does not name the account of {_variable('service_account_key')}"
            )
        return credentials

    @property
    def authentication(self) -> Authentication:
        """How the bot proves its identity: AWS federation, the key, or application default credentials."""
        return self._authentication

    @property
    def credentials(self) -> service_account.Credentials:
        """The key's base credentials, built once at boot; only on the key path."""
        if self._credentials is None:
            raise ValueError(f"{_variable('service_account_key')} is not the credential source ({self._authentication})")
        return self._credentials

    @property
    def aws_region(self) -> str:
        """The AWS region resolved at boot for the federation's signed request; only on the AWS federation path."""
        if self._aws_region is None:
            raise ValueError(f"{_variable('federation_audience')} is not set")
        return self._aws_region


class GoogleWorkspaceSettings(ConfigurationSlice):
    """Vendor credential, tenant and tuning settings for Google Workspace.

    Keys of [google_workspace]:
        api_num_retries, api_timeout_seconds.

    Environment only (the tenant entry; no tenant without a customer id):
        GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID, GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_EMAIL,
        GOOGLE_WORKSPACE__TENANT__FEDERATION_AUDIENCE, GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY,
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
        audience, email, key = (
            _variable(field) for field in ("federation_audience", "service_account_email", "service_account_key")
        )
        if "federation_audience" in tenant and "service_account_email" not in tenant:
            raise ValueError(f"{audience} is set but {email} is not")
        if not {"federation_audience", "service_account_key", "service_account_email"} & tenant.keys():
            raise ValueError(
                f"{customer_id} is set without a credential: set {audience} with {email} (AWS federation), "
                f"{key}, or {email} alone (application default credentials)"
            )
        return {**data, "tenant": tenant}


@lru_cache(maxsize=1)
def get_google_workspace_settings() -> GoogleWorkspaceSettings:
    """Singleton provider for Google Workspace integration settings."""
    return GoogleWorkspaceSettings()

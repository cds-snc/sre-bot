"""Trello vendor settings slice: the [trello] table of the configuration files.

Exposes ``TrelloSettings``, its tenant entry ``TrelloTenant``, and the cached
``get_trello_settings()`` provider, read at use by ``integrations.trello.client``.

The SDK fixes Trello's host and nothing else identifies the tenant, so the entry is the
credentials, read only from the environment as TRELLO__TENANT__<FIELD>; no configuration file
names it (decisions/configuration.md). The slice is validated at boot; whether a consumer
requires Trello is the consumer's, not this slice's.
"""

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice

# The tenant entry's fields, read from the environment as TRELLO__TENANT__<FIELD>; empty counts as unset.
_TENANT_FIELDS = ("app_key", "token")
_TENANT_VARIABLE = "TRELLO__TENANT__{}"


class TrelloTenant(BaseModel):
    """The Trello credentials this instance works with."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    app_key: SecretStr = Field(description="Trello Power-Up API key.")
    token: SecretStr = Field(description="Trello user token the API key acts with.")


class TrelloSettings(ConfigurationSlice):
    """Vendor credential settings for the Trello API.

    Keys of [trello]: none.

    Environment only:
        TRELLO__TENANT__APP_KEY, TRELLO__TENANT__TOKEN: the tenant entry; each needs the other.
        TRELLO__ATIP_BOARD: needs the tenant entry. An empty value counts as unset.
    """

    model_config = SettingsConfigDict(toml_table_header=("trello",), env_prefix="TRELLO__")

    tenant: TrelloTenant | None = Field(default=None, description="The Trello credentials this instance works with.")
    # A non-public board id the legacy ATIP command posts to; tolerated on the vendor slice until
    # TASK-39 moves it to the ATIP feature (decisions/configuration.md).
    atip_board: str = Field(default="", repr=False, description="Id of the ATIP Trello board.")

    @model_validator(mode="before")
    @classmethod
    def _tenant_and_its_values_go_together(cls, data: Any) -> Any:
        # Before validation: an empty value must count as unset, and the message must name the variable.
        if not isinstance(data, dict):
            return data
        if data.get("atip_board") == "":
            data = {key: value for key, value in data.items() if key != "atip_board"}
        tenant = data.get("tenant")
        if isinstance(tenant, dict):
            tenant = {key: value for key, value in tenant.items() if not (key in _TENANT_FIELDS and value == "")}
            present = [field for field in _TENANT_FIELDS if field in tenant]
            if len(present) == 1:
                missing = next(field for field in _TENANT_FIELDS if field not in tenant)
                raise ValueError(
                    f"{_TENANT_VARIABLE.format(present[0].upper())} is set but {_TENANT_VARIABLE.format(missing.upper())} is not"
                )
            # Anything else in the entry is left for validation to reject as an unknown key.
            data = {**data, "tenant": tenant or None}
        if data.get("tenant") is None and "atip_board" in data:
            raise ValueError(f"TRELLO__ATIP_BOARD is set but {_TENANT_VARIABLE.format('APP_KEY')} is not")
        return data


@lru_cache(maxsize=1)
def get_trello_settings() -> TrelloSettings:
    """Return the process-wide ``TrelloSettings`` singleton."""
    return TrelloSettings()

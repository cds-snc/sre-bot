"""Incident response settings: the [incident_response] table of the configuration files.

The declare path's Slack ids are deployment configuration, committed in the environment
file. The handbook id is a non-public value (decisions/configuration.md): declared empty in
base.toml, set only from the environment as INCIDENT_RESPONSE__HANDBOOK_ID; so is the Notify
placement folder id (INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID). A declared incident's
initial status is organisation policy, so it is a key here, never a code constant. The legacy
declare path in modules/incident reads this slice until it is deleted. The upgrade_* keys
drive the incident legacy upgrade job the plugin registers; TASK-145.13 deletes them with it.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only
from features.incident.common.vocabulary import IncidentStatus


class UpgradeMode(StrEnum):
    """What the incident legacy upgrade job does: nothing (not registered), report only, or write."""

    OFF = "off"
    DRY_RUN = "dry_run"
    APPLY = "apply"


class IncidentResponseSettings(ConfigurationSlice):
    """Where a new incident is announced, which groups it invites, and the documents it links to.

    Keys of [incident_response]:
        announcement_channel_id: channel new incidents are announced in; empty for none.
        security_group_id: user group invited to a security incident; empty for none.
        policy_group_id: user group (@incident-policy) invited when policy help is requested; empty for none.
        notify_management_group_id: user group invited to a Notify product incident; empty for none.
        initial_status: the status a declared incident starts in, Open or In Progress; default Open.
        upgrade_mode: the incident legacy upgrade job's mode; off registers nothing.
        upgrade_interval_minutes: minutes between two runs of the upgrade job.
        upgrade_lease_ttl_seconds: lease one run holds, sized to the job's longest run.

    Environment only (non-public values):
        INCIDENT_RESPONSE__HANDBOOK_ID.
        INCIDENT_RESPONSE__NOTIFY_MANAGEMENT_PLACEMENT_ID: the report placement (Drive folder) whose
            incidents invite the Notify management group; empty for none. TODO(TASK-165.1): the
            product catalogue replaces this placement trigger.
    """

    model_config = SettingsConfigDict(toml_table_header=("incident_response",), env_prefix="INCIDENT_RESPONSE__")

    announcement_channel_id: str = Field(default="", description="Slack channel id new incidents are announced in.")
    security_group_id: str = Field(default="", description="Slack user group id invited to a security incident.")
    policy_group_id: str = Field(
        default="", description="Slack user group id (@incident-policy) invited when policy help is requested."
    )
    notify_management_group_id: str = Field(default="", description="Slack user group id invited to a Notify product incident.")
    initial_status: IncidentStatus = Field(
        default=IncidentStatus.OPEN, description="Status a declared incident starts in: Open or In Progress."
    )
    upgrade_mode: UpgradeMode = Field(
        default=UpgradeMode.OFF, description="Incident legacy upgrade job mode: off (not registered), dry_run or apply."
    )
    upgrade_interval_minutes: int = Field(default=30, ge=1, description="Minutes between two runs of the upgrade job.")
    upgrade_lease_ttl_seconds: int = Field(
        default=900, ge=1, description="Seconds one upgrade run holds its lease; longer than the job's longest run."
    )
    handbook_id: str = env_only("Google Docs id of the incident management handbook.", "codespaces", default="")
    notify_management_placement_id: str = env_only(
        "Drive folder id of the report placement whose incidents invite the Notify management group.",
        "codespaces",
        default="",
    )

    @field_validator("initial_status")
    @classmethod
    def _declarable(cls, value: IncidentStatus) -> IncidentStatus:
        if not value.is_declarable:
            raise ValueError(f"a declared incident starts Open or In Progress, not {value.value}")
        return value


@lru_cache(maxsize=1)
def get_incident_response_settings() -> IncidentResponseSettings:
    """Return the process-wide [incident_response] slice."""
    return IncidentResponseSettings()

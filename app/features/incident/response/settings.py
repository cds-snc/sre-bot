"""Incident response settings: the [incident_response] table of the configuration files.

The declare path's Slack ids are deployment configuration, committed in the environment
file. The handbook id is a non-public value (decisions/configuration.md): declared empty in
base.toml, set only from the environment as INCIDENT_RESPONSE__HANDBOOK_ID. The legacy
declare path in modules/incident reads this slice until it is deleted. The upgrade_* keys
drive the incident legacy upgrade job the plugin registers; TASK-145.13 deletes them with it.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice, env_only


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
        notify_management_group_id: user group invited to a Notify product incident; empty for none.
        upgrade_mode: the incident legacy upgrade job's mode; off registers nothing.
        upgrade_interval_minutes: minutes between two runs of the upgrade job.
        upgrade_lease_ttl_seconds: lease one run holds, sized to the job's longest run.
        timeline_update_attempts: bounded legacy timeline write attempts.
        timeline_retry_base_seconds: initial full-jitter retry window.
        timeline_retry_cap_seconds: maximum full-jitter retry window.
        timeline_retry_wait_seconds: total inline retry sleep budget (not an I/O deadline).

    Environment only (non-public values):
        INCIDENT_RESPONSE__HANDBOOK_ID.
    """

    model_config = SettingsConfigDict(toml_table_header=("incident_response",), env_prefix="INCIDENT_RESPONSE__")

    announcement_channel_id: str = Field(default="", description="Slack channel id new incidents are announced in.")
    security_group_id: str = Field(default="", description="Slack user group id invited to a security incident.")
    notify_management_group_id: str = Field(default="", description="Slack user group id invited to a Notify product incident.")
    upgrade_mode: UpgradeMode = Field(
        default=UpgradeMode.OFF, description="Incident legacy upgrade job mode: off (not registered), dry_run or apply."
    )
    upgrade_interval_minutes: int = Field(default=30, ge=1, description="Minutes between two runs of the upgrade job.")
    upgrade_lease_ttl_seconds: int = Field(
        default=900, ge=1, description="Seconds one upgrade run holds its lease; longer than the job's longest run."
    )
    timeline_update_attempts: int = Field(default=6, ge=1, le=10, description="Maximum revision-guarded timeline write attempts.")
    timeline_retry_base_seconds: float = Field(default=0.1, gt=0, le=1, description="Initial timeline retry jitter window.")
    timeline_retry_cap_seconds: float = Field(default=1, gt=0, le=2, description="Maximum timeline retry jitter window.")
    timeline_retry_wait_seconds: float = Field(default=3, ge=0, le=5, description="Total inline timeline retry sleep budget.")
    handbook_id: str = env_only("Google Docs id of the incident management handbook.", "codespaces", default="")


@lru_cache(maxsize=1)
def get_incident_response_settings() -> IncidentResponseSettings:
    """Return the process-wide [incident_response] slice."""
    return IncidentResponseSettings()

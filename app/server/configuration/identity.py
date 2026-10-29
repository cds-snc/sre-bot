"""Deployment identity: ENVIRONMENT and GIT_SHA from the process environment only.

Identity selects the configuration files, so it cannot read them. It reads no
.env file either (decisions/configuration.md, Loading order).
"""

from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import metadata
from typing import Literal
from uuid import uuid4

from pydantic_settings import BaseSettings, SettingsConfigDict


class IdentitySettings(BaseSettings):
    """Which environment this process runs as and which image it was built from."""

    model_config = SettingsConfigDict(env_file=None, case_sensitive=False, extra="ignore")

    environment: Literal["local", "ci", "production"]
    git_sha: str = "Unknown"


@lru_cache(maxsize=1)
def get_identity_settings() -> IdentitySettings:
    """Return the process-wide identity read from the process environment."""
    return IdentitySettings()


@dataclass(frozen=True)
class ServiceIdentity:
    """Who this process is on every log record: OpenTelemetry service and deployment resource attributes."""

    service_name: str
    version: str
    environment: str
    instance_id: str

    def log_fields(self) -> dict[str, str]:
        """Return the fields in the OpenTelemetry resource names (decisions/observability.md)."""
        return {
            "service.name": self.service_name,
            "service.version": self.version,
            "service.instance.id": self.instance_id,
            "deployment.environment.name": self.environment,
        }


def build_service_identity(identity: IdentitySettings) -> ServiceIdentity:
    """Build this process's identity: the distribution name, the image's git_sha and a fresh instance id."""
    return ServiceIdentity(
        service_name=metadata("sre-bot")["Name"],
        version=identity.git_sha,
        environment=identity.environment,
        instance_id=str(uuid4()),
    )

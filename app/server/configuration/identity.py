"""Deployment identity: ENVIRONMENT and GIT_SHA from the process environment only.

Identity selects the configuration files, so it cannot read them. It reads no
.env file either (decisions/configuration.md, Loading order).
"""

from functools import lru_cache
from typing import Literal

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

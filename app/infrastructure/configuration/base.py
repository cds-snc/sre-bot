"""Shared base classes and utilities for settings modules."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class FeatureSettings(BaseSettings):
    """Base class for feature module settings.

    All feature settings should inherit from this class to ensure
    consistent configuration behavior.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

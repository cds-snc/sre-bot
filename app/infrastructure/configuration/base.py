"""Shared base classes and utilities for settings modules."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class IntegrationSettings(BaseSettings):
    """Base class for external integration settings.

    All integration settings should inherit from this class to ensure
    consistent configuration behavior (env file loading, case sensitivity).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


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


class InfrastructureSettings(BaseSettings):
    """Base class for infrastructure-level settings.

    Infrastructure settings control core system behavior like retry logic,
    idempotency, and server configuration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

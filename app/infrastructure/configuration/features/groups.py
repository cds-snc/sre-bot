"""Groups module feature settings."""

import json
from typing import Any, Dict, Optional

from pydantic import Field, field_validator
import structlog

from infrastructure.configuration.base import FeatureSettings

logger = structlog.stdlib.get_logger().bind(component="config.groups")


class GroupsFeatureSettings(FeatureSettings):
    """Configuration for the groups feature and provider management.

    Environment Variables:
        GROUP_PROVIDERS: JSON dict of provider configurations
        RECONCILIATION_ENABLED: Enable reconciliation for failed propagations
        RECONCILIATION_BACKEND: Backend type (memory, dynamodb, sqs)
        RECONCILIATION_MAX_ATTEMPTS: Maximum retry attempts
        RECONCILIATION_BASE_DELAY_SECONDS: Base exponential backoff delay
        RECONCILIATION_MAX_DELAY_SECONDS: Maximum backoff delay
        CIRCUIT_BREAKER_ENABLED: Enable circuit breaker protection
        CIRCUIT_BREAKER_FAILURE_THRESHOLD: Failures before opening circuit
        CIRCUIT_BREAKER_TIMEOUT_SECONDS: Recovery attempt timeout
        CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS: Max calls in half-open state
        REQUIRE_JUSTIFICATION: Require justification for operations
        MIN_JUSTIFICATION_LENGTH: Minimum justification text length
        GROUP_DOMAIN: Domain suffix for group emails (e.g., 'cds-snc.ca')

    Providers Configuration (GROUP_PROVIDERS):
        Configure per-provider behavior including enable/disable, primary
        provider selection, prefix overrides, and capability overrides.

        Schema:
            {
                "google": {
                    "enabled": true,
                    "primary": true,
                    "capabilities": {
                        "provides_role_info": true,
                        "supports_member_management": true
                    }
                },
                "aws": {
                    "enabled": true,
                    "prefix": "aws",
                    "capabilities": {
                        "supports_member_management": true,
                        "supports_batch_operations": true,
                        "max_batch_size": 100
                    }
                }
            }

        Validation:
            - Exactly one provider must have primary=True
            - Disabled providers (enabled=False) excluded from activation
            - Non-primary providers should have prefix for mapping

    Example:
        ```python
        from infrastructure.services import get_settings

        settings = get_settings()

        if settings.groups.circuit_breaker_enabled:
            threshold = settings.groups.circuit_breaker_failure_threshold
            # Configure circuit breaker...

        primary_provider = next(
            (name for name, cfg in settings.groups.providers.items()
             if cfg.get("primary")),
            None
        )
        ```
    """

    # Provider configuration
    providers: dict[str, dict] = Field(
        default_factory=dict,
        alias="GROUP_PROVIDERS",
        description="Per-provider configuration for enable/disable, primary selection, prefix, and capabilities",
    )

    @field_validator("providers", mode="before")
    @classmethod
    def _parse_providers(cls, v: Optional[Any]) -> Any:
        """Parse GROUP_PROVIDERS from JSON string or dict."""
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            s = v.strip()
            if (s.startswith("'") and s.endswith("'")) or (
                s.startswith('"') and s.endswith('"')
            ):
                s = s[1:-1]
            try:
                parsed = json.loads(s) if s else {}
                return parsed
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(
                    f"Invalid GROUP_PROVIDERS JSON: {e} (value: {s[:80]}...)"
                ) from e
        raise ValueError("GROUP_PROVIDERS must be a JSON string or a mapping")

    @field_validator("providers", mode="after")
    @classmethod
    def _validate_providers_config(cls, v: Optional[Dict[str, dict]]):
        """Validate GROUP_PROVIDERS configuration."""
        if not v or not isinstance(v, dict):
            return {}

        enabled_providers = {
            pname: cfg
            for pname, cfg in v.items()
            if isinstance(cfg, dict) and cfg.get("enabled", True)
        }

        if not enabled_providers:
            logger.warning("no_enabled_providers_configured")
            return v

        primary_count = sum(
            1
            for cfg in enabled_providers.values()
            if isinstance(cfg, dict) and cfg.get("primary")
        )

        if primary_count != 1:
            raise ValueError(
                f"GROUP_PROVIDERS configuration must contain exactly one enabled provider "
                f"with 'primary': True. Found {primary_count} enabled primary provider(s)."
            )

        for pname, cfg in enabled_providers.items():
            if not cfg.get("primary") and not cfg.get("prefix"):
                logger.warning(
                    "provider_missing_prefix",
                    provider=pname,
                    msg=(
                        "Enabled non-primary provider has no 'prefix' configured; "
                        "mapping to primary provider may fail"
                    ),
                )

        return v

    # Reconciliation configuration
    reconciliation_enabled: bool = Field(
        default=True,
        alias="RECONCILIATION_ENABLED",
        description="Enable reconciliation for failed propagations",
    )
    reconciliation_backend: str = Field(
        default="memory",
        alias="RECONCILIATION_BACKEND",
        description="Reconciliation backend: 'memory', 'dynamodb', or 'sqs'",
    )
    reconciliation_max_attempts: int = Field(
        default=5,
        alias="RECONCILIATION_MAX_ATTEMPTS",
        description="Maximum retry attempts before moving to DLQ",
    )
    reconciliation_base_delay_seconds: int = Field(
        default=60,
        alias="RECONCILIATION_BASE_DELAY_SECONDS",
        description="Base delay for exponential backoff (seconds)",
    )
    reconciliation_max_delay_seconds: int = Field(
        default=3600,
        alias="RECONCILIATION_MAX_DELAY_SECONDS",
        description="Maximum delay for exponential backoff (seconds)",
    )

    # Circuit breaker configuration
    circuit_breaker_enabled: bool = Field(
        default=True,
        alias="CIRCUIT_BREAKER_ENABLED",
        description="Enable circuit breaker for providers",
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        description="Consecutive failures before opening circuit",
    )
    circuit_breaker_timeout_seconds: int = Field(
        default=60,
        alias="CIRCUIT_BREAKER_TIMEOUT_SECONDS",
        description="Seconds before attempting recovery (HALF_OPEN state)",
    )
    circuit_breaker_half_open_max_calls: int = Field(
        default=3,
        alias="CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS",
        description="Max concurrent requests in HALF_OPEN state",
    )

    # Justification enforcement
    require_justification: bool = Field(
        default=True,
        alias="REQUIRE_JUSTIFICATION",
        description="Require justification for group operations",
    )
    min_justification_length: int = Field(
        default=10,
        alias="MIN_JUSTIFICATION_LENGTH",
        description="Minimum justification text length",
    )

    # Group domain configuration
    group_domain: str = Field(
        default="",
        alias="GROUP_DOMAIN",
        description="Domain suffix for group emails (e.g., 'cds-snc.ca')",
    )

    def __init__(self, **kwargs):
        """Allow programmatic construction using 'providers' keyword."""
        if "providers" in kwargs and "GROUP_PROVIDERS" not in kwargs:
            kwargs["GROUP_PROVIDERS"] = kwargs.pop("providers")
        super().__init__(**kwargs)

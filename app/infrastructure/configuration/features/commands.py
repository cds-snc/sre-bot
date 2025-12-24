"""Commands feature settings."""

import json
from typing import Any, Optional

from pydantic import Field, field_validator

from infrastructure.configuration.base import FeatureSettings


class CommandsSettings(FeatureSettings):
    """Configuration for command adapters and platform integrations.

    Environment Variables:
        COMMAND_PROVIDERS: JSON dict of command provider configurations

    Command Providers Configuration (COMMAND_PROVIDERS):
        Configure per-provider behavior including enable/disable and
        platform-specific settings for command adapters (Slack, Teams, etc.).        Schema:
            {
                "slack": {
                    "enabled": true
                },
                "teams": {
                    "enabled": false
                }
            }

        Scenarios:
            1. No providers enabled -> API-only mode (commands disabled)
            2. One provider enabled -> Single platform mode
            3. Multiple providers enabled -> Multi-platform mode

        Validation:
            - At least zero providers enabled (API-only is valid)
            - Enabled providers must have required configuration

    Example:
        ```python
        from infrastructure.services import get_settings

        settings = get_settings()

        enabled_providers = [
            name for name, cfg in settings.commands.providers.items()
            if cfg.get("enabled", True)
        ]
        ```
    """

    providers: dict[str, dict] = Field(
        default_factory=dict,
        alias="COMMAND_PROVIDERS",
        description="Per-provider configuration for command adapters",
    )

    @field_validator("providers", mode="before")
    @classmethod
    def _parse_providers(cls, v: Optional[Any]) -> Any:
        """Parse COMMAND_PROVIDERS from JSON string or dict."""
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
                    f"Invalid COMMAND_PROVIDERS JSON: {e} (value: {s[:80]}...)"
                ) from e
        raise ValueError("COMMAND_PROVIDERS must be a JSON string or a mapping")

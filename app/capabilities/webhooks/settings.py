"""Webhooks settings: the [webhooks] table of the configuration files.

Every limit the sender-kind content and its engines enforce is a setting with a
default (decisions/webhooks.md Content rules), so an organisation tunes them in a
configuration file instead of in code.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from capabilities.webhooks.domain.limits import WebhookLimits
from contracts.configuration import ConfigurationError, ConfigurationSlice, installed_configuration_files


class WebhooksSettings(ConfigurationSlice):
    """Keys of [webhooks]: the limits on sender-kind content and on what its engines produce."""

    model_config = SettingsConfigDict(toml_table_header=("webhooks",), env_prefix="WEBHOOKS__")

    max_kind_file_bytes: int = Field(default=16384, ge=1, description="Largest sender-kind file, in bytes.")
    max_kinds: int = Field(default=200, ge=1, description="Most sender kinds a deployment provides.")
    max_kinds_per_instance: int = Field(default=20, ge=1, description="Most sender kinds one instance lists.")
    max_conditions: int = Field(default=50, ge=1, description="Most conditions in one kind's match, across groups.")
    max_condition_depth: int = Field(default=2, ge=1, description="Deepest nesting of all and any groups.")
    max_extracted_fields: int = Field(default=30, ge=1, description="Most fields one kind extracts.")
    max_field_value_chars: int = Field(default=4096, ge=1, description="Longest extracted text value; longer is cut.")
    max_list_items: int = Field(default=50, ge=1, description="Most elements in an extracted list; more are dropped.")
    max_url_chars: int = Field(default=2048, ge=1, description="Longest link URL accepted from a payload.")
    max_template_chars: int = Field(default=2048, ge=1, description="Longest template text in a sender kind.")
    max_title_chars: int = Field(default=150, ge=1, description="Longest rendered title; longer is cut with an ellipsis.")
    max_loop_iterations: int = Field(default=100, ge=1, description="Most loop iterations in one render.")
    max_render_chars: int = Field(default=3000, ge=1, description="Longest output of one template render.")
    max_context_depth: int = Field(default=10, ge=1, description="Deepest template context nesting.")
    email_lookups_per_message: int = Field(
        default=10, ge=1, description="Most distinct email addresses resolved to mentions in one message."
    )

    def limits(self) -> WebhookLimits:
        """Return the limits as the frozen value the engines take."""
        return WebhookLimits(
            max_kinds_per_instance=self.max_kinds_per_instance,
            max_conditions=self.max_conditions,
            max_condition_depth=self.max_condition_depth,
            max_extracted_fields=self.max_extracted_fields,
            max_field_value_chars=self.max_field_value_chars,
            max_list_items=self.max_list_items,
            max_url_chars=self.max_url_chars,
            max_template_chars=self.max_template_chars,
            max_title_chars=self.max_title_chars,
            max_loop_iterations=self.max_loop_iterations,
            max_render_chars=self.max_render_chars,
            max_context_depth=self.max_context_depth,
            email_lookups_per_message=self.email_lookups_per_message,
        )


@lru_cache(maxsize=1)
def get_webhooks_settings() -> WebhooksSettings:
    """Return the process-wide [webhooks] slice."""
    return WebhooksSettings()


def content_settings() -> WebhooksSettings:
    """Return the slice that checks sender-kind files: the loaded one, or its defaults outside the app.

    The app installs its configuration files before content loads, so boot checks files
    against the configured limits. The content validator (``bin.check_content_schemas``) runs
    over any root without an environment's configuration and checks against the defaults,
    as it does for the [content] ceilings (decisions/provisioned-content.md).
    """
    try:
        installed_configuration_files()
    except ConfigurationError:
        return WebhooksSettings.model_construct()
    return get_webhooks_settings()

"""Webhooks settings: the [webhooks] table of the configuration files.

Every limit the sender-kind content and its engines enforce is a setting with a
default (decisions/webhooks.md Content rules), and so is every ingest bound: body caps,
deadlines, leases, the inbox's retention and retry policy, and the SNS fetch bounds
(decisions/webhooks.md 3 Pipeline), so an organisation tunes them in a configuration file
instead of in code.
"""

from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
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
    post_attempt_timeout_seconds: int = Field(
        default=2,
        ge=1,
        description="Timeout of one platform call while posting (a post or a mention lookup); posts are retried by the inbox, never in process.",
    )

    instances_table_name: str = Field(
        default="webhooks", min_length=1, description="Records table holding the webhook instances."
    )
    inbox_table_name: str = Field(
        default="sre_bot_webhook_inbox", min_length=1, description="Records table holding one inbox item per delivery."
    )
    inbox_ttl_seconds: int = Field(
        default=604800, ge=3600, description="How long an inbox item is kept, and so how long a delivery id is deduplicated."
    )
    inline_processing_deadline_seconds: float = Field(
        default=5.0, gt=0, le=30, description="Time the request spends processing an item before it answers."
    )
    processing_lease_margin_seconds: int = Field(
        default=30, ge=1, description="Time past the processing deadline before another worker may take an item over."
    )
    unavailable_retry_after_seconds: int = Field(
        default=30, ge=1, description="Retry-After sent with a 503 when nothing could be persisted."
    )
    retry_base_seconds: int = Field(default=30, ge=1, description="First retry delay; it doubles per attempt, with full jitter.")
    retry_max_seconds: int = Field(default=3600, ge=1, description="Longest delay between two attempts.")
    retry_max_attempts: int = Field(default=8, ge=1, description="Attempts before an item is dead-lettered.")
    sweeper_interval_seconds: int = Field(default=60, ge=10, description="How often the sweeper looks for due items.")
    sweeper_lease_ttl_seconds: int = Field(default=300, ge=1, description="Longest sweeper run; the run's lease length.")
    sweeper_batch_size: int = Field(default=25, ge=1, description="Most due items one sweeper run takes.")
    aws_sns_max_body_bytes: int = Field(
        default=524288, ge=1, description="Largest aws_sns body: about twice SNS's 256 KiB message, for the escaped envelope."
    )
    legacy_slack_json_max_body_bytes: int = Field(default=262144, ge=1, description="Largest legacy_slack_json body.")
    aws_sns_content_types: tuple[str, ...] = Field(
        default=("text/plain", "application/json"),
        min_length=1,
        description="Media types an aws_sns delivery may declare; SNS sends text/plain.",
    )
    legacy_slack_json_content_types: tuple[str, ...] = Field(
        default=("application/json",), min_length=1, description="Media types a legacy_slack_json delivery may declare."
    )
    max_json_depth: int = Field(default=64, ge=1, description="Deepest nesting of objects and arrays a body may have.")
    max_envelope_bytes: int = Field(
        default=358400, ge=1, description="Largest decoded envelope an inbox item holds, under the store's item limit."
    )
    idempotency_key_max_chars: int = Field(
        default=255, ge=1, description="Longest Idempotency-Key header a legacy_slack_json delivery may send."
    )
    sns_max_message_age_seconds: int = Field(
        default=86400,
        ge=3600,
        description="Oldest SNS Timestamp accepted; at most the inbox TTL, so a replay never outlives its dedupe key.",
    )
    sns_fetch_timeout_seconds: float = Field(
        default=3.0, gt=0, description="Timeout of one SNS certificate fetch or subscription confirmation."
    )
    sns_connect_retries: int = Field(default=2, ge=0, description="Retries of an SNS connection that never opened.")
    sns_certificate_cache_ttl_seconds: int = Field(
        default=86400, ge=60, description="How long a fetched SNS certificate is kept."
    )
    sns_certificate_cache_size: int = Field(default=32, ge=1, description="Most SNS certificates kept at once.")

    @model_validator(mode="after")
    def _bounds_fit(self) -> Self:
        if self.sns_max_message_age_seconds > self.inbox_ttl_seconds:
            raise ValueError("sns_max_message_age_seconds must not exceed inbox_ttl_seconds")
        if self.retry_base_seconds > self.retry_max_seconds:
            raise ValueError("retry_base_seconds must not exceed retry_max_seconds")
        return self

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

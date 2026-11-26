"""The limits the sender-kind content and its engines enforce, as one frozen value."""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class WebhookLimits:
    """Limits built from the [webhooks] settings, which hold the defaults; the engines take this value."""

    max_kinds_per_instance: int
    max_conditions: int
    max_condition_depth: int
    max_extracted_fields: int
    max_field_value_chars: int
    max_list_items: int
    max_url_chars: int
    max_template_chars: int
    max_title_chars: int
    max_loop_iterations: int
    max_render_chars: int
    max_context_depth: int
    email_lookups_per_message: int

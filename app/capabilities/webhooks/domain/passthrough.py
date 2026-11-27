"""The passthrough-hardening fingerprint of a sender-built Slack message.

The legacy protocol forwards a Slack-shaped message the sender built. Before hardening is
enforced, each delivery records which of the fields the passthrough rule drops it carries
(decisions/webhooks.md 9, security.md Passthrough rule), by name only and never by value,
so the shadow run can measure who relies on them. The walk is iterative and linear in the
message.
"""

from collections.abc import Mapping
from typing import Any

# Interaction ids a registered feature may own: a payload must never supply them.
INTERACTION_ID_FIELDS = ("action_id", "block_id", "callback_id")
# Top-level fields the rule drops (or keeps only where the instance allows them).
TOP_LEVEL_FIELDS = ("icon_emoji", "icon_url", "link_names", "parse", "reply_broadcast", "thread_ts", "username")
# Block Kit elements that act on a click; one without a url would reach a registered handler.
INTERACTIVE_TYPES = frozenset(
    {
        "button",
        "checkboxes",
        "datepicker",
        "datetimepicker",
        "multi_conversations_select",
        "multi_external_select",
        "multi_static_select",
        "multi_users_select",
        "overflow",
        "radio_buttons",
        "conversations_select",
        "external_select",
        "static_select",
        "timepicker",
        "users_select",
    }
)
INTERACTIVE_WITHOUT_URL = "interactive_without_url"


def hardening_fingerprint(message: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the sorted names of the hardening fields ``message`` carries."""
    found = {name for name in TOP_LEVEL_FIELDS if name in message}
    stack: list[Any] = list(message.values())
    while stack:
        node = stack.pop()
        if isinstance(node, Mapping):
            found.update(name for name in INTERACTION_ID_FIELDS if name in node)
            if node.get("type") in INTERACTIVE_TYPES and "url" not in node:
                found.add(INTERACTIVE_WITHOUT_URL)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return tuple(sorted(found))

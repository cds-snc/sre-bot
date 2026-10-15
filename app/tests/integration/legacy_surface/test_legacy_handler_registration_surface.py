"""Pinning tests for the set of listeners the hard-coded legacy modules register.

The harness applies the lifespan's own ``_register_legacy_handlers`` to a Bolt
app that records every ``command``, ``action``, ``view`` and ``event``
registration. Each test compares one kind against literal names, so renaming,
dropping or adding a legacy slash command, interaction id or event listener
fails here. What each listener does is pinned by the per-surface test files.
"""

from collections import Counter

import pytest

from .conftest import LegacyHandlerHarness

pytestmark = pytest.mark.integration

LEGACY_COMMANDS = ("aws", "talent-role", "secret", "atip", "aiprp", "incident")

LEGACY_ACTIONS = (
    "role_change_locale",
    "ati_search_width",
    "atip_change_locale",
    "secret_change_locale",
    "toggle_webhook",
    "reveal_webhook",
    "next_page",
    "channel",
    "hook_type",
    "incident_change_locale",
    "handle_incident_action_buttons",
    "add_folder_metadata",
    "view_folder_metadata",
    "delete_folder_metadata",
    "confirm_click",
    "user_select_action",
    "archive_channel",
    "update_incident_field",
)

LEGACY_VIEWS = (
    "role_view",
    "atip_view",
    "aws_health_view",
    "secret_view",
    "create_webhooks_view",
    "incident_view",
    "view_folder_metadata_modal",
    "add_metadata_view",
    "view_save_incident_roles",
    "view_save_event",
    "update_field_modal",
)

# Each reaction event has a floppy-disk listener (with a matcher) and an ack-only fallback.
LEGACY_EVENTS = (
    ("reaction_added", True),
    ("reaction_removed", True),
    ("reaction_added", False),
    ("reaction_removed", False),
)


def test_legacy_handlers_register_exactly_the_six_slash_commands(legacy_handler_harness: LegacyHandlerHarness) -> None:
    """The legacy modules register these six commands, each once, under the transport prefix."""
    prefix = legacy_handler_harness.command_prefix
    expected = Counter(f"/{prefix}{name}" for name in LEGACY_COMMANDS)

    assert Counter(legacy_handler_harness.app.registered_commands) == expected


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("action", LEGACY_ACTIONS), ("view", LEGACY_VIEWS)],
)
def test_legacy_handlers_register_exactly_the_interaction_ids(
    legacy_handler_harness: LegacyHandlerHarness, kind: str, expected: tuple[str, ...]
) -> None:
    """Every action and view id is registered once, with no matcher, and nothing else of that kind is."""
    registered = [
        (name, has_matchers)
        for listener_kind, name, has_matchers in legacy_handler_harness.app.registered_listeners
        if listener_kind == kind
    ]

    assert Counter(registered) == Counter((name, False) for name in expected)


def test_legacy_handlers_register_the_reaction_listeners_and_their_fallbacks(
    legacy_handler_harness: LegacyHandlerHarness,
) -> None:
    """Both reaction events register a matcher-filtered listener first, then an ack-only fallback."""
    registered = [
        (name, has_matchers) for kind, name, has_matchers in legacy_handler_harness.app.registered_listeners if kind == "event"
    ]

    assert registered == list(LEGACY_EVENTS)

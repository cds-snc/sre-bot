"""Unit tests for the public name of the Slack reply Protocol in contracts.slack.

The module is inspected directly, with no stub: the Protocol is exported under
its role name with the three reply methods handlers call, and the former
pattern-suffixed name is gone, so no alias can keep importers on it.
"""

import pytest

import contracts.slack.reply as reply_module

pytestmark = pytest.mark.unit


def test_reply_module_exposes_the_reply_sender_protocol() -> None:
    sender = reply_module.SlackReplySender

    assert getattr(sender, "_is_protocol", False)
    assert all(callable(getattr(sender, method)) for method in ("post_message", "post_ephemeral", "open_view"))


def test_reply_module_keeps_no_alias_at_the_former_name() -> None:
    assert not hasattr(reply_module, "SlackReplyPort")

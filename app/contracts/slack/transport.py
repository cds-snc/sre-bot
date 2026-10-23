"""Slack transport facts the host establishes at boot, for code that cannot import the host.

The host owns the [slack_transport] slice (server/slack/settings.py) and hands the
Slack runtime its values directly. The legacy modules name their own slash commands
and sit below server/ in the layers, so they read the command prefix from here
(decisions/transport-slack.md); they leave this contract when they are rebuilt.
"""

from dataclasses import dataclass

from contracts.configuration import ConfigurationError


@dataclass(frozen=True)
class SlackTransportInfo:
    """Facts about the running Slack transport that code below the host reads."""

    command_prefix: str


# Process-wide state the app factory sets once, written only by the install functions below,
# in the same form and for the same reason as HostInfo in contracts/configuration.py.
_transport: SlackTransportInfo | None = None


def install_slack_transport_info(info: SlackTransportInfo) -> None:
    """Install the transport facts built by the app factory; a later install replaces them."""
    global _transport
    _transport = info


def uninstall_slack_transport_info() -> None:
    """Remove the installed transport facts, so reading them fails until the next install."""
    global _transport
    _transport = None


def slack_transport_info() -> SlackTransportInfo:
    """Return the installed transport facts, or fail when the app factory has not run."""
    if _transport is None:
        raise ConfigurationError("Slack transport info not installed: the app factory (create_app) installs it")
    return _transport

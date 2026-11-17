"""The oncall plugin: its hookimpls.

The entry point names this module, not the package, so features and packages may import
``capabilities.oncall.api`` while the plugin itself stays protected (decisions/plugins.md).
Registration is startup-driven and side effect free at import time.
"""

from capabilities.oncall.entrypoints.slack import register_commands
from contracts.plugins.namespace import hookimpl
from contracts.plugins.requirements import Requirement
from contracts.slack.registrar import SlackCommandRegistrar


@hookimpl
def register_requirements() -> tuple[Requirement, ...]:
    """Declare no requirement: the self-managed source needs no vendor, Opsgenie is optional.

    The rotation commands need no Slack requirement either: the host calls ``register_slack_commands``
    only when the Slack transport runs, which itself requires ``[slack.tenant]``.
    """
    return ()


@hookimpl
def register_slack_commands(registrar: SlackCommandRegistrar) -> None:
    """Register the ``/sre rotations`` commands."""
    register_commands(registrar)

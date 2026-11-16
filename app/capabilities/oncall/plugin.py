"""The oncall plugin: its hookimpls.

The entry point names this module, not the package, so features and packages may import
``capabilities.oncall.api`` while the plugin itself stays protected (decisions/plugins.md).
Registration is startup-driven and side effect free at import time.
"""

from contracts.plugins.namespace import hookimpl
from contracts.plugins.requirements import Requirement


@hookimpl
def register_requirements() -> tuple[Requirement, ...]:
    """Declare no requirement: the self-managed source needs no vendor, Opsgenie is optional."""
    return ()

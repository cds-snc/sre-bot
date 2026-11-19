"""Text generation capability: text from a source and instructions, for features that offer drafting or summarising.

Holds the package's hookimpls, register_requirements first. Registration is
startup-driven and side effect free at import time: only decorated hookimpls
are defined here (decisions/plugins.md).
"""

from contracts.plugins.namespace import hookimpl
from contracts.plugins.requirements import Requirement


@hookimpl
def register_requirements() -> list[Requirement]:
    """Declare each vendor or capability capabilities.text_generation cannot run without; none yet."""
    return []

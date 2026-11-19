"""AI writing capability: AI-written text from a source and the caller's instructions, for features that offer drafts and summaries.

Holds the package's hookimpls, register_requirements first. Registration is
startup-driven and side effect free at import time: only decorated hookimpls
are defined here (decisions/plugins.md).
"""

from contracts.plugins.namespace import hookimpl
from contracts.plugins.requirements import Requirement


@hookimpl
def register_requirements() -> list[Requirement]:
    """Declare each vendor or capability capabilities.ai_writing cannot run without; none yet."""
    return []

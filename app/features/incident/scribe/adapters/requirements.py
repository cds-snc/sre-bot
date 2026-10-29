"""Resolves the vendors incident scribe requires; the plugin's ``register_requirements`` calls it.

Per ``decisions/feature-packages.md`` the adapters are the only modules in the
package allowed to import ``integrations``.
"""

from contracts.plugins.requirements import RequiredDependencyError
from integrations.openai import get_openai_settings


def require_openai_tenant() -> None:
    """Raise unless the OpenAI tenant is configured: drafting and summarizing have no fallback without it.

    Raises:
        RequiredDependencyError: No [openai.tenant] entry is configured.
    """
    if get_openai_settings().tenant is None:
        raise RequiredDependencyError("openai.tenant")

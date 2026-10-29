"""The requirements a plugin declares: configuration settings that must be set for it to run.

A plugin states its requirements in its ``register_requirements`` hookimpl by
returning a ``Requirement`` for each, naming the setting by its dotted path. The
host resolves them, so a plugin carries no vendor code (decisions/plugins.md).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    """One configuration setting an enabled plugin requires, such as ``openai.tenant``.

    The path is ``<settings table>.<field>``. It names a setting, never a configured value.
    """

    setting: str

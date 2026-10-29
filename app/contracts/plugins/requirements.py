"""The error a plugin raises when a vendor or capability it requires is not configured.

A plugin states its requirements in its ``register_requirements`` hookimpl by
resolving each one and raising this error, naming the configuration setting to
set, when one is absent (decisions/plugins.md). The host aborts boot on it.
"""


class RequiredDependencyError(Exception):
    """A vendor or capability an enabled plugin requires is not configured.

    Carries only the configuration setting to fix, such as ``openai.tenant``,
    never a configured value.
    """

    def __init__(self, setting: str) -> None:
        super().__init__(f"required dependency not configured: set {setting} or switch the plugin off")
        self.setting = setting

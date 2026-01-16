"""Auto-discovery and decorator-based command registration system.

Provides a FastAPI-inspired decorator pattern for registering commands with platform
providers (Slack, Teams, Discord). Commands are auto-discovered from module/package
files and registered with their respective providers.

Key Components:
    - ProviderCommandRegistry: Per-provider decorator registry
    - AutoDiscovery: Orchestrator that discovers and registers commands for all providers
    - Global instances: slack_commands, teams_commands, discord_commands for use in
      decorators throughout the codebase

Example:
    # In packages/geolocate/platforms/slack.py
    from infrastructure.platforms.registry.auto_discovery import slack_commands

    @slack_commands.register(
        name="geolocate",
        parent="sre",
        description="Geolocate an IP address",
        usage_hint="<ip_address>",
        examples=["8.8.8.8", "1.1.1.1"],
    )
    def handle_geolocate_slack(payload: CommandPayload) -> CommandResponse:
        # Handler implementation
        pass

    # In main.py
    auto_discovery = get_auto_discovery()
    auto_discovery.discover_all()
    auto_discovery.register_all(
        slack_provider=slack_provider,
        teams_provider=teams_provider,
        discord_provider=discord_provider,
    )
"""

import importlib
import importlib.util
import pkgutil
import structlog
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = structlog.get_logger()


class ProviderCommandRegistry:
    """Provider-specific command registry using decorators.

    Each platform provider (Slack, Teams, Discord) gets its own registry instance.
    Commands are registered via decorators and automatically bound to the provider
    when register_with_provider() is called.

    Attributes:
        provider_name: Name of the platform (e.g., "slack", "teams", "discord")
        _commands: List of command metadata dicts containing handler info
    """

    def __init__(self, provider_name: str):
        """Initialize registry for a specific provider.

        Args:
            provider_name: Name of the platform provider (e.g., "slack", "teams")
        """
        self.provider_name = provider_name
        self._commands: List[Dict[str, Any]] = []
        self._logger = logger.bind(provider=provider_name)

    def register(
        self,
        name: str,
        parent: str,
        description: str = "",
        description_key: Optional[str] = None,
        usage_hint: str = "",
        examples: Optional[List[str]] = None,
        example_keys: Optional[List[str]] = None,
        legacy_mode: bool = False,
    ) -> Callable:
        """Decorator to register a command with this provider.

        Args:
            name: Command name (e.g., "version", "geolocate")
            parent: Parent command path (e.g., "sre", "sre.dev")
            description: Human-readable command description
            description_key: i18n key for description (e.g., "commands.sre.version.description")
            usage_hint: Usage syntax (e.g., "<ip_address>")
            examples: List of example usages (e.g., ["8.8.8.8", "1.1.1.1"])
            example_keys: i18n keys for examples
            legacy_mode: Bypass automatic help interception

        Returns:
            Decorator function that registers the handler

        Example:
            @slack_commands.register(
                name="version",
                parent="sre",
                description="Show version",
            )
            def handle_version(payload: CommandPayload) -> CommandResponse:
                pass
        """

        def decorator(func: Callable) -> Callable:
            """Inner decorator that registers the function."""
            command_meta = {
                "command": name,
                "handler": func,
                "parent": parent,
                "description": description,
                "description_key": description_key,
                "usage_hint": usage_hint,
                "examples": examples or [],
                "example_keys": example_keys or [],
                "legacy_mode": legacy_mode,
            }
            self._commands.append(command_meta)
            self._logger.debug(
                "command_registered",
                command=name,
                parent=parent,
                handler=func.__name__,
            )
            return func

        return decorator

    def get_commands(self) -> List[Dict[str, Any]]:
        """Get all registered commands for this provider.

        Returns:
            Copy of the commands list to prevent external modification
        """
        return self._commands.copy()

    def register_with_provider(self, provider: Any) -> None:
        """Register all decorated commands with the actual provider instance.

        Calls provider.register_command() for each command that was decorated
        with @provider_commands.register().

        Args:
            provider: Provider instance (SlackPlatformProvider, TeamsPlatformProvider, etc.)
        """
        if not provider:
            self._logger.warning(
                "provider_is_none",
                provider_name=self.provider_name,
            )
            return

        for cmd_meta in self._commands:
            try:
                provider.register_command(**cmd_meta)
                self._logger.debug(
                    "command_registered_with_provider",
                    command=cmd_meta["command"],
                    parent=cmd_meta["parent"],
                )
            except Exception as e:
                self._logger.error(
                    "failed_to_register_command_with_provider",
                    command=cmd_meta["command"],
                    parent=cmd_meta["parent"],
                    error=str(e),
                    exc_info=True,
                )
                raise

        self._logger.info(
            "all_commands_registered_with_provider",
            provider=self.provider_name,
            command_count=len(self._commands),
        )


class AutoDiscovery:
    """Auto-discovery orchestrator for all platform providers.

    Scans module and package directories for platform-specific command files
    (e.g., modules/*/platforms/slack.py) and imports them to trigger command
    registration decorators. Then registers all discovered commands with their
    respective provider instances.

    Attributes:
        slack: ProviderCommandRegistry for Slack
        teams: ProviderCommandRegistry for Teams
        discord: ProviderCommandRegistry for Discord
    """

    def __init__(self):
        """Initialize registries for all providers."""
        self.slack = ProviderCommandRegistry("slack")
        self.teams = ProviderCommandRegistry("teams")
        self.discord = ProviderCommandRegistry("discord")
        self._logger = logger
        self._discovered_modules: List[str] = []

    def discover_all(
        self,
        base_paths: Optional[List[str]] = None,
        platform_pattern: str = "platforms",
    ) -> None:
        """Auto-discover and import all platform-specific command modules.

        Scans for files matching these patterns:
        - modules/*/platforms/slack.py
        - modules/*/platforms/teams.py
        - modules/*/platforms/discord.py
        - packages/*/platforms/slack.py
        - packages/*/slack.py (for backward compatibility)
        - packages/*/teams.py (for backward compatibility)
        - packages/*/discord.py (for backward compatibility)

        When a module is imported, any @slack_commands.register() decorators
        in that module will execute and register their handlers.

        Args:
            base_paths: Directories to scan (default: ["modules", "packages"])
            platform_pattern: Directory name for platform files (default: "platforms")

        Raises:
            ImportError: If a discovered module cannot be imported
        """
        if base_paths is None:
            base_paths = ["modules", "packages"]

        providers = ["slack", "teams", "discord"]
        self._discovered_modules = []

        for base_path in base_paths:
            base_path_obj = Path(base_path)
            if not base_path_obj.exists():
                self._logger.debug(f"base_path_does_not_exist", path=base_path)
                continue

            # Pattern 1: Scan for modules/*/platforms/{slack,teams,discord}.py
            for module_dir in base_path_obj.iterdir():
                if not module_dir.is_dir() or module_dir.name.startswith("_"):
                    continue

                platforms_dir = module_dir / platform_pattern
                if platforms_dir.exists():
                    for provider in providers:
                        provider_file = platforms_dir / f"{provider}.py"
                        if provider_file.exists():
                            module_path = f"{base_path}.{module_dir.name}.{platform_pattern}.{provider}"
                            self._import_module(module_path)

            # Pattern 2: Scan for packages/*/{slack,teams,discord}.py (backward compatibility)
            if base_path == "packages":
                for module_dir in base_path_obj.iterdir():
                    if not module_dir.is_dir() or module_dir.name.startswith("_"):
                        continue

                    for provider in providers:
                        provider_file = module_dir / f"{provider}.py"
                        if provider_file.exists():
                            module_path = f"{base_path}.{module_dir.name}.{provider}"
                            self._import_module(module_path)

        self._logger.info(
            "auto_discovery_complete",
            modules_discovered=len(self._discovered_modules),
            modules=self._discovered_modules,
        )

    def _import_module(self, module_path: str) -> None:
        """Import a single module, triggering decorator registration.

        Args:
            module_path: Full module path (e.g., "modules.sre.platforms.slack")
        """
        try:
            importlib.import_module(module_path)
            self._discovered_modules.append(module_path)
            self._logger.debug(
                "module_imported",
                module=module_path,
            )
        except ImportError as e:
            self._logger.error(
                "failed_to_import_module",
                module=module_path,
                error=str(e),
                exc_info=True,
            )
            raise
        except Exception as e:
            self._logger.error(
                "unexpected_error_importing_module",
                module=module_path,
                error=str(e),
                exc_info=True,
            )
            raise

    def register_all(
        self,
        slack_provider: Optional[Any] = None,
        teams_provider: Optional[Any] = None,
        discord_provider: Optional[Any] = None,
    ) -> None:
        """Register all discovered commands with their respective providers.

        For each enabled provider, calls register_with_provider() to bind all
        decorated commands to the actual provider instance.

        Args:
            slack_provider: SlackPlatformProvider instance (optional)
            teams_provider: TeamsPlatformProvider instance (optional)
            discord_provider: DiscordPlatformProvider instance (optional)
        """
        self._logger.info("starting_provider_registration")

        if slack_provider:
            self.slack.register_with_provider(slack_provider)
        else:
            self._logger.debug("slack_provider_not_enabled")

        if teams_provider:
            self.teams.register_with_provider(teams_provider)
        else:
            self._logger.debug("teams_provider_not_enabled")

        if discord_provider:
            self.discord.register_with_provider(discord_provider)
        else:
            self._logger.debug("discord_provider_not_enabled")

        self._logger.info("all_providers_registered")


# Global singleton instance
_auto_discovery = AutoDiscovery()

# Export provider-specific registries for use in command decorator files
slack_commands = _auto_discovery.slack
teams_commands = _auto_discovery.teams
discord_commands = _auto_discovery.discord


def get_auto_discovery() -> AutoDiscovery:
    """Get the global auto-discovery orchestrator instance.

    Returns:
        The singleton AutoDiscovery instance
    """
    return _auto_discovery

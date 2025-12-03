"""Multi-platform command router with explicit platform registry."""

import shlex
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from core.logging import get_module_logger
from infrastructure.commands.registry import CommandRegistry
from infrastructure.commands.providers.base import CommandProvider
from infrastructure.i18n.models import TranslationKey, Locale

logger = get_module_logger()


@dataclass
class ProviderRoute:
    """Platform-specific provider route."""

    platform: str  # "slack", "teams", "discord", "api"
    provider: CommandProvider
    registry: Optional[CommandRegistry]  # Optional for legacy handlers without registry
    description: Optional[str] = None  # Fallback description (English)
    description_key: Optional[str] = (
        None  # i18n translation key (e.g., "sre.subcommands.groups.description")
    )


class CommandRouter:
    """Multi-platform command router.

    Routes commands to platform-specific providers based on explicit registration.
    Supports multiple platforms per subcommand (e.g., groups works on Slack AND Teams).

    Example:
        router = CommandRouter(namespace="sre")

        # Register Slack provider
        router.register_subcommand("groups", slack_groups_provider, platform="slack")

        # Register Teams provider (same command, different platform)
        router.register_subcommand("groups", teams_groups_provider, platform="teams")

        # Route based on payload
        router.handle(slack_payload)  # → slack_groups_provider
        router.handle(teams_payload)  # → teams_groups_provider
    """

    def __init__(self, namespace: str):
        """Initialize router with namespace.

        Args:
            namespace: Command namespace (e.g., "sre", "incident", "aws")
        """
        self.namespace = namespace
        # Two-level dict: routes[subcommand][platform] = ProviderRoute
        self.routes: Dict[str, Dict[str, ProviderRoute]] = {}

    def _requote_tokens(self, tokens: List[str]) -> str:
        """Re-quote tokens that contain spaces or special characters.

        When joining tokens back into a string for re-tokenization (as happens when
        the router extracts the subcommand and passes the rest to the provider),
        we need to add quotes back for tokens that were originally quoted.
        This preserves the semantic meaning through double tokenization.

        The router tokenizes to extract the subcommand name (necessary), which causes
        shlex.split() to consume quotes. When we reconstruct the text for the provider,
        a simple join loses quote information. This method re-escapes tokens to preserve
        their structure through the second tokenization in the provider.

        Args:
            tokens: List of tokens to join (typically tokens[1:] after subcommand extraction)

        Returns:
            String with tokens properly quoted and joined for re-tokenization

        Example:
            tokens = ['add', 'user@example.com', 'my group', 'provider', 'test new command']
            result = _requote_tokens(tokens)
            # Returns: 'add user@example.com "my group" provider "test new command"'
            # When this is tokenized again, 'my group' stays as one token
        """
        quoted_tokens = []
        for token in tokens:
            # Token needs quoting if it contains spaces or special shell chars
            # These are chars that have special meaning in POSIX shell
            if " " in token or any(c in token for c in "|&;<>()$`\\\"'"):
                quoted_tokens.append(shlex.quote(token))
            else:
                quoted_tokens.append(token)
        return " ".join(quoted_tokens)

    def register_subcommand(
        self,
        name: str,
        provider: CommandProvider,
        platform: str,
        description: Optional[str] = None,
        description_key: Optional[str] = None,
    ) -> None:
        """Register a subcommand with platform-specific provider.

        Args:
            name: Subcommand name (e.g., "groups", "incident", "webhooks")
            provider: Platform-specific provider instance
            platform: Platform identifier ("slack", "teams", "discord", "api")
            description: Fallback description (English) if translation key not available
            description_key: i18n translation key (e.g., "sre.subcommands.groups.description")

        Raises:
            ValueError: If provider invalid configuration
        """
        # Allow optional registry for legacy handlers that don't use commands
        # (e.g., LegacyIncidentProvider delegates directly to helper functions)

        # Set parent command for help generation
        provider.parent_command = self.namespace

        # Create route entry
        route = ProviderRoute(
            platform=platform,
            provider=provider,
            registry=provider.registry,  # Can be None for legacy handlers
            description=description,
            description_key=description_key,
        )

        # Register in two-level dictionary
        if name not in self.routes:
            self.routes[name] = {}

        self.routes[name][platform] = route

        logger.info(
            "subcommand_registered",
            namespace=self.namespace,
            subcommand=name,
            platform=platform,
            provider=provider.__class__.__name__,
        )

    def _detect_platform(self, platform_payload: Any) -> Optional[str]:
        """Detect platform from payload structure.

        Uses structural inspection to identify platform:
        - Slack: has "command" dict + "client" + team_id
        - Teams: has "activity" dict + channelId
        - Discord: has "interaction" dict + guild_id
        - API: explicit "platform" key or fallback to "api"

        Args:
            platform_payload: Platform-specific payload

        Returns:
            Platform identifier or None if detection failed
        """
        if not isinstance(platform_payload, dict):
            return None

        # Explicit platform key (for testing or ambiguous cases)
        if "platform" in platform_payload:
            return platform_payload["platform"]

        # Slack detection: has command + client + team_id/channel_id
        if "command" in platform_payload and "client" in platform_payload:
            command = platform_payload["command"]
            if isinstance(command, dict) and (
                "team_id" in command or "channel_id" in command
            ):
                return "slack"

        # Teams detection: has activity + channelId
        if "activity" in platform_payload:
            activity = platform_payload["activity"]
            if isinstance(activity, dict) and "channelId" in platform_payload:
                return "teams"

        # Discord detection: has interaction + guild_id
        if "interaction" in platform_payload:
            interaction = platform_payload["interaction"]
            if isinstance(interaction, dict) and "guild_id" in interaction:
                return "discord"

        # Default to API for HTTP requests without platform markers
        return "api"

    def handle(self, platform_payload: Any) -> None:
        """Handle command routing based on platform detection.

        Flow:
        1. Detect platform from payload structure
        2. Extract subcommand name from payload
        3. Look up provider for (subcommand, platform) pair
        4. Delegate to provider.handle()

        Args:
            platform_payload: Platform-specific command payload
        """
        # Step 1: Detect platform
        platform = self._detect_platform(platform_payload)
        if platform is None:
            logger.error(
                "platform_detection_failed",
                namespace=self.namespace,
                payload_keys=(
                    list(platform_payload.keys())
                    if isinstance(platform_payload, dict)
                    else None
                ),
            )
            # Can't send error - don't know how to respond
            return

        # Step 2: Extract subcommand name
        # Platform provider will do full extraction, we just need first token
        try:
            # Get provider for this platform (any subcommand) to extract text
            sample_route = next(iter(self.routes.values())).get(platform)
            if sample_route is None:
                logger.error(
                    "no_provider_for_platform",
                    namespace=self.namespace,
                    platform=platform,
                )
                return

            text = sample_route.provider.extract_command_text(platform_payload)
            preprocessed = sample_route.provider.preprocess_command_text(
                platform_payload, text
            )
            tokens = (
                sample_route.provider._tokenize(preprocessed) if preprocessed else []
            )

            if not tokens:
                # Show router help
                self._send_router_help(platform_payload, platform)
                return

            subcommand_name = tokens[0]

        except Exception as e:
            logger.exception(
                "command_extraction_failed",
                namespace=self.namespace,
                platform=platform,
                error=str(e),
            )
            return

        # Step 2.5: Handle help/aide as special commands at router level
        if subcommand_name in ("help", "aide", "--help", "-h"):
            self._send_router_help(platform_payload, platform)
            return

        # Step 3: Look up provider for (subcommand, platform)
        if subcommand_name not in self.routes:
            # Unknown subcommand
            sample_route.provider.send_error(
                platform_payload,
                f"Unknown subcommand: `{subcommand_name}`. Type `help` for usage.",
            )
            return

        if platform not in self.routes[subcommand_name]:
            # Subcommand not available on this platform
            available_platforms = list(self.routes[subcommand_name].keys())
            sample_route.provider.send_error(
                platform_payload,
                f"❌ `{subcommand_name}` not available on {platform.upper()}.\n"
                f"Available on: {', '.join(p.upper() for p in available_platforms)}",
            )
            return

        # Step 4: Route to provider
        route = self.routes[subcommand_name][platform]

        # Modify payload to include remaining tokens (after subcommand)
        modified_payload = dict(platform_payload)
        if "command" in modified_payload:
            # Slack-style payload
            modified_payload["command"] = dict(modified_payload["command"])
            modified_payload["command"]["text"] = self._requote_tokens(tokens[1:])
        elif "activity" in modified_payload:
            # Teams-style payload
            modified_payload["activity"] = dict(modified_payload["activity"])
            modified_payload["activity"]["text"] = self._requote_tokens(tokens[1:])

        logger.info(
            "routing_to_provider",
            namespace=self.namespace,
            subcommand=subcommand_name,
            platform=platform,
            provider=route.provider.__class__.__name__,
        )

        route.provider.handle(modified_payload)

    def _send_router_help(self, platform_payload: Any, platform: str) -> None:
        """Send router-level help showing available subcommands.

        Args:
            platform_payload: Platform payload for sending response
            platform: Detected platform identifier
        """
        # Get sample provider to send help
        sample_route = next(iter(self.routes.values())).get(platform)
        if sample_route is None:
            return

        # Resolve locale for translation
        locale = "en-US"  # Default
        try:
            locale = sample_route.provider._resolve_framework_locale(platform_payload)
        except Exception:  # pylint: disable=broad-except
            pass

        # Helper function to translate template strings
        def translate_key(key_name: str, fallback: str) -> str:
            """Translate a help template key, fall back to English if unavailable."""
            if not sample_route.provider.translator:
                return fallback
            try:
                key = TranslationKey.from_string(f"{self.namespace}.help.{key_name}")
                locale_enum = (
                    Locale.from_string(locale) if isinstance(locale, str) else locale
                )
                translated = sample_route.provider.translator.translate_message(
                    key, locale_enum
                )
                return translated if translated else fallback
            except Exception:  # pylint: disable=broad-except
                return fallback

        # Translate help template strings
        title = translate_key("title", f"{self.namespace.upper()} Commands")
        section_header = translate_key("section_header", "Available subcommands:")
        # Footer is namespace-specific, so construct dynamically
        footer_fallback = (
            f"Type /{self.namespace} <subcommand> help for subcommand details."
        )
        # Translate footer template (no {namespace} placeholder in YAML)
        footer = translate_key("footer", footer_fallback)

        lines = [f"*{title}*\n"]
        lines.append(f"{section_header}\n")

        for subcommand_name in sorted(self.routes.keys()):
            if platform in self.routes[subcommand_name]:
                route = self.routes[subcommand_name][platform]

                # Try to translate description using the provider's translator
                desc = route.description or f"{subcommand_name} commands"
                if route.description_key and sample_route.provider.translator:
                    try:
                        key = TranslationKey.from_string(route.description_key)
                        locale_enum = (
                            Locale.from_string(locale)
                            if isinstance(locale, str)
                            else locale
                        )
                        translated = sample_route.provider.translator.translate_message(
                            key, locale_enum
                        )
                        if translated:
                            desc = translated
                    except Exception:  # pylint: disable=broad-except
                        # Fallback to English description if translation fails
                        pass

                lines.append(f"  `/{self.namespace} {subcommand_name}` - {desc}")

        lines.append(f"\n{footer}")

        help_text = "\n".join(lines)
        sample_route.provider.send_help(platform_payload, help_text)

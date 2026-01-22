"""SRE Module - Main command handler for /sre commands

This module provides the entry point for /sre commands via the legacy Slack Bolt interface.
It bridges the Slack Bolt interface with the new platform provider system.
"""

import structlog
from slack_bolt import Ack, App, Respond
from slack_sdk import WebClient

from infrastructure.platforms.models import CommandPayload
from infrastructure.services import get_slack_provider, get_settings


logger = structlog.get_logger()


# ============================================================
# SLACK BOT INTEGRATION - Legacy Bolt interface
# ============================================================


def register(bot: App):
    """Register the /sre Slack command with Bolt.

    Called by main.py to register the command handler with Slack Bolt.
    This provides the legacy Bolt entry point that dispatches to platform providers.
    """
    settings = get_settings()
    bot.command(f"/{settings.PREFIX}sre")(sre_command)


def sre_command(ack: Ack, command, respond: Respond, client: WebClient):
    """Handle /sre command from Slack Bolt.

    This is the legacy Bolt entry point that bridges to the platform provider system.
    It acknowledges the command, extracts the subcommand, and dispatches to the
    appropriate handler via the platform provider.

    Args:
        ack: Slack Bolt acknowledgment function
        command: Command payload from Slack
        respond: Function to send response back to Slack
        client: Slack WebClient instance
    """
    ack()

    text = command.get("text", "").strip()
    user_id = command.get("user_id", "")
    channel_id = command.get("channel_id", "")

    logger.info("sre_command_received", text=text, user=user_id, channel=channel_id)

    # Get platform service
    slack_provider = get_slack_provider()

    if not slack_provider:
        respond("Slack provider not available")
        return

    # Extract user's locale from Slack profile (defaults to en-US)
    user_locale = "en-US"
    try:
        user_info = client.users_info(user=user_id)
        if user_info.get("ok") and user_info.get("user"):
            profile = user_info["user"].get("profile", {})
            if profile.get("locale"):
                user_locale = profile["locale"]
                logger.info(
                    "user_locale_extracted", user_id=user_id, locale=user_locale
                )
            else:
                logger.debug(
                    "user_profile_no_locale",
                    user_id=user_id,
                    profile_keys=list(profile.keys()),
                )
    except Exception as e:
        logger.warning("failed_to_get_user_locale", user_id=user_id, error=str(e))

    # Handle help request
    if not text or text.lower() in ("help", "aide", "--help", "-h"):
        # Show all commands under /sre (root_command="sre")
        help_text = slack_provider.generate_help(locale=user_locale, root_command="sre")
        respond(help_text)
        return

    # Parse subcommand and args, finding the longest matching command path
    # For hierarchical commands like /sre groups list, we need to find the full path
    # Example: text="groups list" should resolve to "sre.groups.list" not "sre.groups"
    parts = text.split()
    subcommand_args = ""

    # Build full_path by trying progressively longer command paths
    full_command_path = None
    for i in range(len(parts), 0, -1):
        candidate_path = "sre." + ".".join(parts[:i])
        if candidate_path in slack_provider._commands:
            full_command_path = candidate_path
            # Remaining parts are arguments
            subcommand_args = " ".join(parts[i:]) if i < len(parts) else ""
            break

    # Fallback: if no command found, use first word as subcommand
    if not full_command_path:
        subcommand = parts[0] if parts else ""
        full_command_path = f"sre.{subcommand}"
        subcommand_args = " ".join(parts[1:]) if len(parts) > 1 else ""

    # Create CommandPayload with full Slack command as platform_metadata
    # This ensures legacy handlers have access to all Slack-specific fields
    # (trigger_id, channel_name, etc.) without us having to enumerate them
    payload = CommandPayload(
        text=subcommand_args,
        user_id=user_id,
        channel_id=channel_id,
        user_locale=user_locale,
        user_email="",
        response_url="",
        platform_metadata=command,  # Pass entire Slack command object
    )

    # Dispatch to handler
    try:
        response = slack_provider.dispatch_command(full_command_path, payload)

        if response.blocks:
            respond(blocks=response.blocks)
        elif response.message:
            respond(response.message)
        else:
            respond(f"Executed: {subcommand}")

    except Exception as e:
        logger.error("command_dispatch_failed", subcommand=subcommand, error=str(e))
        respond(f"Error executing command '{subcommand}': {str(e)}")

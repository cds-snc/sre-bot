"""The configuration phase result: validated slices and the HostInfo built from them."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import structlog
from pydantic import ValidationError

from contracts.configuration import (
    ConfigurationError,
    HostInfo,
    describe_validation_error,
    install_configuration_files,
    install_host_info,
)
from contracts.slack.transport import SlackTransportInfo, install_slack_transport_info
from infrastructure.configuration.features.sre_ops import SreOpsSettings, get_sre_ops_settings
from infrastructure.directory import DirectorySettings, get_directory_settings
from infrastructure.logging.settings import LoggingSettings, get_logging_settings
from infrastructure.logging.setup import configure_logging
from infrastructure.security.settings import SecuritySettings, get_security_settings
from integrations.google_workspace.settings import get_google_workspace_settings
from integrations.slack.settings import SlackSettings, get_slack_settings
from modules.webhooks.patterns.aws_sns_notification.settings import get_notify_api_key_leak_settings
from server.configuration.identity import IdentitySettings, get_identity_settings
from server.configuration.loader import TomlConfigurationFiles, load_configuration_files
from server.configuration.server_settings import ServerSettings, get_server_settings
from server.slack.settings import SlackTransportSettings, get_slack_transport_settings


class SlackKey(StrEnum):
    """The Slack slice keys the transport rules name; TASK-111.9 renames them when the slice moves onto [slack]."""

    TEAM_ID = "SLACK_TEAM_ID"
    BOT = "SLACK_BOT_TOKEN"
    APP = "SLACK_APP_TOKEN"
    SIGNING = "SLACK_SIGNING_SECRET"


@dataclass(frozen=True)
class HostConfiguration:
    """Everything the lifespan reads from the configuration phase."""

    files: TomlConfigurationFiles
    identity: IdentitySettings
    host_info: HostInfo
    server: ServerSettings
    security: SecuritySettings
    directory: DirectorySettings
    sre_ops: SreOpsSettings
    logging: LoggingSettings
    slack_transport: SlackTransportSettings


def build_host_info(identity: IdentitySettings, server: ServerSettings) -> HostInfo:
    """Combine the deployment identity and the [server] slice into the host facts."""
    return HostInfo(
        environment=identity.environment,
        git_sha=identity.git_sha,
        public_base_url=server.public_base_url,
    )


def refuse_dev_bypass_in_production(host: HostInfo, security: SecuritySettings) -> None:
    """Fail boot when production would carry the dev bypass flag or token (decisions/security.md).

    The per-request guards already refuse the bypass in production; a flag or token
    present there is a deploy-coupled defect, so it stops the deploy instead.
    """
    if host.environment != "production":
        return
    if security.dev_bypass_enabled:
        raise ConfigurationError("[security] dev_bypass_enabled is true in production; the dev bypass is local only")
    if security.dev_bypass_token is not None:
        raise ConfigurationError("SECURITY__DEV_BYPASS_TOKEN is set in production; the dev bypass is local only")


def validate_slack_transport(transport: SlackTransportSettings, slack: SlackSettings) -> None:
    """Fail boot when the transport switched on lacks what its delivery mode needs (decisions/transport-slack.md).

    The rules join the [slack_transport] slice with the Slack vendor slice, so they run here
    rather than in either slice. Messages name the key, never a value. Socket Mode without
    the signing secret is production's shape: it boots, with an info notice.
    """
    if not transport.enabled:
        return
    if slack.tenant is None:
        raise ConfigurationError(f"{SlackKey.TEAM_ID} is required when [slack_transport] enabled is true")
    if not slack.bot_token:
        raise ConfigurationError(f"{SlackKey.BOT} is required when [slack_transport] enabled is true")
    if transport.socket_mode and not slack.app_token:
        raise ConfigurationError(f"{SlackKey.APP} is required when [slack_transport] socket_mode is true")
    if not transport.socket_mode and not slack.signing_secret:
        raise ConfigurationError(f"{SlackKey.SIGNING} is required when [slack_transport] socket_mode is false")
    if transport.socket_mode and not slack.signing_secret:
        structlog.get_logger(__name__).info(
            "slack_signing_secret_not_set_in_socket_mode",
            detail=(
                f"{SlackKey.SIGNING} is not set. Socket Mode does not need it for request authenticity "
                "(the connection handshake carries that), but it must be configured before switching to "
                "HTTP Events mode ([slack_transport] socket_mode = false), which fails boot without it."
            ),
        )


def load_host_configuration(directory: Path | None = None) -> HostConfiguration:
    """Run the configuration phase once: select, check and install the files, validate every host slice.

    Logging is configured right after the identity and [logging] slices, so every later
    configuration event, a failure included, renders through the one pipeline
    (decisions/observability.md). Any invalid environment, file, table or key raises
    here, before the app is built.
    """
    identity = get_identity_settings()
    files = load_configuration_files(identity.environment, directory)
    install_configuration_files(files)
    logging_settings = get_logging_settings()
    configure_logging(identity.environment, logging_settings)
    try:
        return _validate_slices(identity, files, logging_settings)
    except ValidationError as error:
        # A slice not yet on the files raises pydantic's error, whose message renders every input value.
        failure = ConfigurationError(describe_validation_error(error))
        _log_invalid(failure)
        raise failure from None
    except ConfigurationError as error:
        _log_invalid(error)
        raise


def _log_invalid(error: ConfigurationError) -> None:
    structlog.get_logger(__name__).critical("configuration_invalid", phase="configuration", error=str(error))


def _validate_slices(
    identity: IdentitySettings, files: TomlConfigurationFiles, logging_settings: LoggingSettings
) -> HostConfiguration:
    server = get_server_settings()
    security = get_security_settings()
    directory_settings = get_directory_settings()
    sre_ops = get_sre_ops_settings()
    # Vendor and feature slices validate with the host slices: an invalid entry fails boot here.
    slack_transport = get_slack_transport_settings()
    validate_slack_transport(slack_transport, get_slack_settings())
    get_google_workspace_settings()
    get_notify_api_key_leak_settings()
    host = build_host_info(identity, server)
    refuse_dev_bypass_in_production(host, security)
    install_host_info(host)
    install_slack_transport_info(SlackTransportInfo(command_prefix=slack_transport.command_prefix))
    return HostConfiguration(
        files=files,
        identity=identity,
        host_info=host,
        server=server,
        security=security,
        directory=directory_settings,
        sre_ops=sre_ops,
        logging=logging_settings,
        slack_transport=slack_transport,
    )

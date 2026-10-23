"""The configuration phase result: validated slices and the HostInfo built from them."""

from dataclasses import dataclass
from pathlib import Path

from contracts.configuration import HostInfo, install_configuration_files, install_host_info
from infrastructure.configuration.features.sre_ops import SreOpsSettings, get_sre_ops_settings
from infrastructure.directory import DirectorySettings, get_directory_settings
from infrastructure.logging.settings import LoggingSettings, get_logging_settings
from infrastructure.security.settings import SecuritySettings, get_security_settings
from integrations.google_workspace.settings import get_google_workspace_settings
from integrations.slack.settings import get_slack_settings
from modules.webhooks.patterns.aws_sns_notification.settings import get_notify_api_key_leak_settings
from server.configuration.identity import IdentitySettings, get_identity_settings
from server.configuration.loader import TomlConfigurationFiles, load_configuration_files
from server.configuration.server_settings import ServerSettings, get_server_settings


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


def build_host_info(identity: IdentitySettings, server: ServerSettings) -> HostInfo:
    """Combine the deployment identity and the [server] slice into the host facts."""
    return HostInfo(
        environment=identity.environment,
        git_sha=identity.git_sha,
        public_base_url=server.public_base_url,
    )


def load_host_configuration(directory: Path | None = None) -> HostConfiguration:
    """Run the configuration phase once: select, check and install the files, validate every host slice.

    Any invalid environment, file, table or key raises here, before the app is built.
    """
    identity = get_identity_settings()
    files = load_configuration_files(identity.environment, directory)
    install_configuration_files(files)
    server = get_server_settings()
    security = get_security_settings()
    directory_settings = get_directory_settings()
    sre_ops = get_sre_ops_settings()
    logging_settings = get_logging_settings()
    # Vendor and feature slices validate with the host slices: an invalid entry fails boot here.
    get_slack_settings()
    get_google_workspace_settings()
    get_notify_api_key_leak_settings()
    host = build_host_info(identity, server)
    install_host_info(host)
    return HostConfiguration(
        files=files,
        identity=identity,
        host_info=host,
        server=server,
        security=security,
        directory=directory_settings,
        sre_ops=sre_ops,
        logging=logging_settings,
    )

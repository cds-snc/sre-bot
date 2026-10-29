"""The configuration phase result: validated slices and the HostInfo built from them."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import structlog
from pydantic import ValidationError

from contracts.configuration import (
    ConfigurationError,
    HostInfo,
    built_slices,
    describe_validation_error,
    install_configuration_files,
    install_host_info,
)
from contracts.slack.transport import SlackTransportInfo, install_slack_transport_info
from features.cloud_operations.spending.settings import get_cloud_operations_spending_settings
from features.incident.common.settings import get_incident_core_settings
from features.incident.postmortem.settings import get_incident_postmortem_settings
from features.incident.response.settings import get_incident_response_settings
from features.talent.settings import get_talent_settings
from infrastructure.audit.settings import get_audit_settings
from infrastructure.configuration.features.aws_ops import get_aws_feature_settings
from infrastructure.configuration.features.sre_ops import SreOpsSettings, get_sre_ops_settings
from infrastructure.coordination.settings import get_conditional_write_settings
from infrastructure.directory import DirectorySettings, get_directory_settings
from infrastructure.logging.settings import get_logging_settings
from infrastructure.logging.setup import configure_logging
from infrastructure.security.settings import SecuritySettings, get_security_settings
from integrations.aws.settings import get_aws_settings
from integrations.google_workspace.settings import GoogleWorkspaceSettings, get_google_workspace_settings
from integrations.maxmind.settings import get_maxmind_settings
from integrations.notify.settings import get_notify_settings
from integrations.openai.settings import get_openai_settings
from integrations.opsgenie.settings import get_opsgenie_settings
from integrations.sentinel.settings import get_sentinel_settings
from integrations.slack.settings import SlackSettings, get_slack_settings
from integrations.trello.settings import get_trello_settings
from jobs.settings import SchedulerSettings, get_scheduler_settings
from modules.atip.settings import get_atip_settings
from modules.webhooks.patterns.aws_sns_notification.settings import get_notify_api_key_leak_settings
from server.configuration.identity import IdentitySettings, build_service_identity, get_identity_settings
from server.configuration.loader import TomlConfigurationFiles, load_configuration_files
from server.configuration.server_settings import ServerSettings, get_server_settings
from server.configuration.summary import summarize
from server.plugins.manager import installed_plugin_names
from server.plugins.settings import check_plugin_enablement, get_plugins_settings
from server.slack.settings import SlackTransportSettings, get_slack_transport_settings


class SlackKey(StrEnum):
    """The Slack slice keys the transport rules name."""

    TEAM_ID = "[slack.tenant] team_id"
    BOT = "SLACK__BOT_TOKEN"
    APP = "SLACK__APP_TOKEN"
    SIGNING = "SLACK__SIGNING_SECRET"


@dataclass(frozen=True)
class HostConfiguration:
    """Everything the lifespan reads from the configuration phase."""

    host_info: HostInfo
    server: ServerSettings
    security: SecuritySettings
    directory: DirectorySettings
    sre_ops: SreOpsSettings
    slack_transport: SlackTransportSettings
    scheduler: SchedulerSettings
    disabled_plugins: frozenset[str]


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


def warn_on_weakened_security(host: HostInfo, security: SecuritySettings) -> None:
    """Log a WARNING for each security-weakening setting at boot, naming the setting and never a value.

    The dev bypass flag is warned about outside production only, since production refuses
    to boot with it (refuse_dev_bypass_in_production). An empty issuer list leaves every
    authenticated endpoint failing at runtime, so it warns in every environment.
    """
    log = structlog.get_logger(__name__)
    if host.environment != "production" and security.dev_bypass_enabled:
        log.warning("security_setting_weakened", phase="configuration", setting="security.dev_bypass_enabled")
    if not security.issuers:
        log.warning("security_setting_weakened", phase="configuration", setting="security.issuers")


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


# The legacy incident handlers in modules/ use Google Workspace (documents, Drive, calendar) and are
# not plugins, so they cannot state the requirement through register_requirements (decisions/plugins.md).
# The host states it while they are registered; TASK-145.13 deletes app/modules/incident and this rule.
# No ENVIRONMENT comparison: every environment that switches the transport on needs the tenant.
LEGACY_INCIDENT_GOOGLE_KEY = "GOOGLE_WORKSPACE__TENANT__CUSTOMER_ID"


def validate_legacy_incident_google_tenant(transport: SlackTransportSettings, google: GoogleWorkspaceSettings) -> None:
    """Fail boot when the transport is switched on without a Google Workspace tenant (decisions/configuration.md).

    A half tenant entry already fails inside the Google slice, so a tenant present here is complete.
    The message names the key, never a value.
    """
    if transport.enabled and google.tenant is None:
        raise ConfigurationError(f"{LEGACY_INCIDENT_GOOGLE_KEY} is required when [slack_transport] enabled is true")


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
    configure_logging(identity.environment, logging_settings, static_fields=build_service_identity(identity).log_fields())
    try:
        configuration = _validate_slices(identity)
    except ValidationError as error:
        # A slice not yet on the files raises pydantic's error, whose message renders every input value.
        failure = ConfigurationError(describe_validation_error(error))
        _log_invalid(failure)
        raise failure from None
    except ConfigurationError as error:
        _log_invalid(error)
        raise
    _log_configuration_summary(files)
    return configuration


def _log_invalid(error: ConfigurationError) -> None:
    structlog.get_logger(__name__).critical("configuration_invalid", phase="configuration", error=str(error))


def _log_configuration_summary(files: TomlConfigurationFiles) -> None:
    """Log every slice the phase built as one event: the shown values, the state of the withheld, a hash of the shown."""
    summary = summarize(built_slices())
    structlog.get_logger(__name__).info(
        "configuration_summary",
        phase="configuration",
        files=[path.name for path in files.paths],
        config_hash=summary.config_hash,
        slices=summary.sections(),
    )


def _validate_slices(identity: IdentitySettings) -> HostConfiguration:
    server = get_server_settings()
    security = get_security_settings()
    directory_settings = get_directory_settings()
    get_audit_settings()
    get_conditional_write_settings()
    sre_ops = get_sre_ops_settings()
    # Vendor and feature slices validate with the host slices: an invalid entry fails boot here.
    slack_transport = get_slack_transport_settings()
    validate_slack_transport(slack_transport, get_slack_settings())
    scheduler = get_scheduler_settings()
    get_aws_settings()
    validate_legacy_incident_google_tenant(slack_transport, get_google_workspace_settings())
    get_openai_settings()
    get_notify_settings()
    get_trello_settings()
    get_opsgenie_settings()
    get_maxmind_settings()
    get_sentinel_settings()
    get_notify_api_key_leak_settings()
    get_atip_settings()
    get_aws_feature_settings()
    # The feature slices the legacy modules read; a rebuilt subdomain states its required ids when it registers.
    get_incident_core_settings()
    get_incident_response_settings()
    get_incident_postmortem_settings()
    get_cloud_operations_spending_settings()
    get_talent_settings()
    plugins = get_plugins_settings()
    check_plugin_enablement(plugins, installed_plugin_names())
    host = build_host_info(identity, server)
    refuse_dev_bypass_in_production(host, security)
    warn_on_weakened_security(host, security)
    install_host_info(host)
    install_slack_transport_info(SlackTransportInfo(command_prefix=slack_transport.command_prefix))
    return HostConfiguration(
        host_info=host,
        server=server,
        security=security,
        directory=directory_settings,
        sre_ops=sre_ops,
        slack_transport=slack_transport,
        scheduler=scheduler,
        disabled_plugins=plugins.disabled(),
    )

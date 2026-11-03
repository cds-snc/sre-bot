"""Slack inbound tenant guard: every request must come from the configured Slack tenant.

The [slack.tenant] entry is the expected tenant, as an OpenID Connect client
configures its issuer and rejects tokens from any other (decisions/transport-slack.md,
Verification). The guard is a global Bolt middleware: Bolt runs it after its own
request verification and before any listener, for every request type.

The ids compared are the installation-scoped ones Bolt extracts into the request
context (Events API: authorizations[0]; views: app_installed_team_id; commands and
interactions: the payload team and enterprise), never the acting user's team, so a
Slack Connect user in a shared channel is not mistaken for another tenant.

A refused request is acked (Bolt does not ack a middleware that stops the chain, and
Slack shows the user a timeout), runs no listener, and logs slack_tenant_mismatch at
error. Where the request has a response URL, an ephemeral notice is posted from a
background worker, so it never delays the ack.
"""

from collections.abc import Callable
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import structlog
from slack_bolt import App, BoltRequest, BoltResponse
from slack_bolt.middleware import Middleware
from slack_sdk.webhook import WebhookClient

from infrastructure.i18n.factory import t
from integrations.slack.settings import SlackTenant

logger = structlog.get_logger(__name__)

NOTICE_KEY = "transport.slack.tenant_mismatch"
NOTICE_LOCALES = ("en-US", "fr-FR")
NOTICE_TIMEOUT_SECONDS = 2


@dataclass(frozen=True)
class TenantMismatch:
    """The configured ids and the ids a refused request carried."""

    expected_team_id: str | None
    expected_enterprise_id: str | None
    received_team_id: str | None
    received_enterprise_id: str | None


def check_slack_tenant(tenant: SlackTenant, *, team_id: str | None, enterprise_id: str | None) -> TenantMismatch | None:
    """Return the mismatch when the request's ids do not match the configured tenant, otherwise None.

    A configured enterprise id must equal the request's; with none configured, a request
    naming an Enterprise org is refused. A configured team id must equal the request's;
    an unconfigured one is not compared, since an org-wide install spans workspaces.
    """
    enterprise_matches = enterprise_id == tenant.enterprise_id
    team_matches = tenant.team_id is None or team_id == tenant.team_id
    if enterprise_matches and team_matches:
        return None
    return TenantMismatch(
        expected_team_id=tenant.team_id,
        expected_enterprise_id=tenant.enterprise_id,
        received_team_id=team_id,
        received_enterprise_id=enterprise_id,
    )


def _notice_text(locale: str | None) -> str:
    """Return the notice in the user's locale when the payload names a supported one, otherwise in both."""
    if locale in NOTICE_LOCALES:
        return t(NOTICE_KEY, locale)
    return "\n".join(t(NOTICE_KEY, each) for each in NOTICE_LOCALES)


def _send_notice(response_url: str, text: str) -> None:
    try:
        WebhookClient(response_url, timeout=NOTICE_TIMEOUT_SECONDS).send(text=text, response_type="ephemeral")
    except Exception as error:
        logger.warning("slack_tenant_notice_failed", error_type=type(error).__name__)


def _request_fields(body: dict[str, Any]) -> dict[str, Any]:
    """Name the request for the log line: its type and identifiers, never its text."""
    view = body.get("view")
    event = body.get("event")
    actions = body.get("actions")
    return {
        "payload_type": body.get("type"),
        "command": body.get("command"),
        "event_type": event.get("type") if isinstance(event, dict) else None,
        "callback_id": view.get("callback_id") if isinstance(view, dict) else body.get("callback_id"),
        "action_id": actions[0].get("action_id") if isinstance(actions, list) and actions else body.get("action_id"),
    }


class SlackTenantGuard(Middleware):
    """Global Bolt middleware refusing every request that does not come from the configured tenant."""

    def __init__(self, tenant: SlackTenant, executor: Executor) -> None:
        self._tenant = tenant
        self._executor = executor

    def process(self, *, req: BoltRequest, resp: BoltResponse, next: Callable[[], BoltResponse]) -> BoltResponse:
        context = req.context
        mismatch = check_slack_tenant(self._tenant, team_id=context.team_id, enterprise_id=context.enterprise_id)
        if mismatch is None:
            return next()
        logger.error(
            "slack_tenant_mismatch",
            expected_team_id=mismatch.expected_team_id,
            expected_enterprise_id=mismatch.expected_enterprise_id,
            received_team_id=mismatch.received_team_id,
            received_enterprise_id=mismatch.received_enterprise_id,
            is_enterprise_install=context.is_enterprise_install,
            **_request_fields(req.body),
        )
        response_url = context.response_url
        if response_url:
            user = req.body.get("user")
            locale = user.get("locale") if isinstance(user, dict) else None
            self._executor.submit(_send_notice, response_url, _notice_text(locale))
        if req.body.get("type") == "block_suggestion":
            return context.ack(options=[])
        return context.ack()


def install_slack_tenant_guard(app: App, tenant: SlackTenant | None, *, executor: Executor | None = None) -> None:
    """Install the tenant guard as a global middleware of the Bolt app.

    Fails closed: with no tenant entry there is nothing to verify against, so no app
    runs without the guard. The configuration phase already requires the entry when
    the transport is switched on.
    """
    if tenant is None:
        raise ValueError("[slack.tenant] is required to verify inbound Slack requests")
    notice_executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="slack-tenant-notice")
    app.use(SlackTenantGuard(tenant, notice_executor))

import json
from datetime import UTC, datetime
from urllib.request import Request, urlopen

import structlog

from integrations.opsgenie.settings import get_opsgenie_settings

logger = structlog.get_logger()


class OpsGenieAPIError(Exception):
    """Raised when an OpsGenie API call fails or returns an unparseable response."""


def get_on_call_users(schedule):
    log = logger.bind(schedule=schedule)
    content = api_get_request(f"/v2/schedules/{schedule}/on-calls")
    try:
        data = json.loads(content)
        return [x["name"] for x in data["data"]["onCallParticipants"]]
    except Exception as e:
        log.exception(
            "get_on_call_users_error",
            schedule=schedule,
            error=str(e),
        )
        return []


def get_on_call_user_for_rotation(schedule_id: str, rotation_name: str) -> str | None:
    """Return the email of the user currently on-call for ``rotation_name``.

    Returns ``None`` when the rotation does not exist on the schedule, has no
    current coverage (gap), or the active recipient is not a user
    (team/escalation). Raises :class:`OpsGenieAPIError` on transport or
    response-parsing failures, and when Opsgenie is not configured.
    """
    # With no `date` param, OpsGenie anchors `finalTimeline` at "now", so the
    # first period of the matching rotation is the active one — unless its
    # startDate is in the future, which indicates a coverage gap.
    path = f"/v2/schedules/{schedule_id}/timeline?identifierType=id&interval=1&intervalUnit=days"
    try:
        content = api_get_request(path)
        rotations = json.loads(content)["data"]["finalTimeline"]["rotations"]
    except Exception as exc:
        raise OpsGenieAPIError(f"OpsGenie timeline request failed for schedule {schedule_id!r}") from exc

    rotation = next((r for r in rotations if r.get("name") == rotation_name), None)
    if not rotation:
        return None
    periods = rotation.get("periods") or []
    if not periods:
        return None
    period = periods[0]
    if datetime.fromisoformat(period["startDate"]) > datetime.now(UTC):
        return None
    recipient = period.get("recipient") or {}
    return recipient.get("name") if recipient.get("type") == "user" else None


def healthcheck():
    """Check if the bot can interact with the Opsgenie API."""
    if get_opsgenie_settings().tenant is None:
        logger.warning("opsgenie_not_configured")
        return False
    healthy = False
    try:
        content = api_get_request("/v1/services")
        result = json.loads(content)
        healthy = "data" in result
        logger.info(
            "opsgenie_healthcheck_success",
            status="healthy" if healthy else "unhealthy",
            result=result,
        )
    except Exception as error:
        logger.exception(
            "opsgenie_healthcheck_error",
            error=str(error),
        )
    return healthy


def api_get_request(path: str) -> str:
    """GET ``path`` on the tenant's Opsgenie API with the integration key; raises when not configured."""
    settings = get_opsgenie_settings()
    if settings.tenant is None:
        raise OpsGenieAPIError("Opsgenie is not configured")
    req = Request(settings.tenant.api_url.rstrip("/") + path)  # noqa: S310 -- the tenant validator requires https
    req.add_header("Authorization", f"GenieKey {settings.integrations_key.get_secret_value()}")
    conn = urlopen(req, timeout=settings.timeout_seconds)  # noqa: S310 -- the tenant validator requires https
    body: bytes = conn.read()
    return body.decode("utf-8")

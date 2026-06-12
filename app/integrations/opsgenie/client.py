import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import structlog

from infrastructure.configuration.integrations.opsgenie import get_opsgenie_settings

# Use the integrations API Key as the Opsgenie API Key
OPSGENIE_KEY = get_opsgenie_settings().OPSGENIE_INTEGRATIONS_KEY
logger = structlog.get_logger()


class OpsGenieAPIError(Exception):
    """Raised when an OpsGenie API call fails or returns an unparseable response."""


def get_on_call_users(schedule):
    log = logger.bind(schedule=schedule)
    content = api_get_request(
        f"https://api.opsgenie.com/v2/schedules/{schedule}/on-calls",
        {"name": "GenieKey", "token": OPSGENIE_KEY},
    )
    try:
        data = json.loads(content)
        return list(map(lambda x: x["name"], data["data"]["onCallParticipants"]))
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
    response-parsing failures.
    """
    # With no `date` param, OpsGenie anchors `finalTimeline` at "now", so the
    # first period of the matching rotation is the active one — unless its
    # startDate is in the future, which indicates a coverage gap.
    url = (
        f"https://api.opsgenie.com/v2/schedules/{schedule_id}/timeline"
        "?identifierType=id&interval=1&intervalUnit=days"
    )
    try:
        content = api_get_request(url, {"name": "GenieKey", "token": OPSGENIE_KEY})
        rotations = json.loads(content)["data"]["finalTimeline"]["rotations"]
    except Exception as exc:
        raise OpsGenieAPIError(
            f"OpsGenie timeline request failed for schedule {schedule_id!r}"
        ) from exc

    rotation = next((r for r in rotations if r.get("name") == rotation_name), None)
    if not rotation:
        return None
    periods = rotation.get("periods") or []
    if not periods:
        return None
    period = periods[0]
    if datetime.fromisoformat(period["startDate"]) > datetime.now(timezone.utc):
        return None
    recipient = period.get("recipient") or {}
    return recipient.get("name") if recipient.get("type") == "user" else None


# Create an Opsgenie alert. This is used to notify the on-call users
def create_alert(description):
    log = logger.bind(description=description)
    content = api_post_request(
        "https://api.opsgenie.com/v2/alerts",
        {"name": "GenieKey", "token": OPSGENIE_KEY},
        {
            "message": "Notify API Key has been compromised!",
            "description": f"{description}",
        },
    )
    try:
        data = json.loads(content)
        log.info(
            "create_alert",
            description=description,
            result=data["result"],
        )
        return data["result"]
    except Exception as e:
        log.exception(
            "create_alert_error",
            description=description,
            error=str(e),
        )
        return "Could not issue alert to Opsgenie!"


def healthcheck():
    """Check if the bot can interact with the Opsgenie API."""
    healthy = False
    try:
        content = api_get_request(
            "https://api.opsgenie.com/v1/services",
            {"name": "GenieKey", "token": OPSGENIE_KEY},
        )
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


def api_get_request(url, auth):
    req = Request(url)
    req.add_header("Authorization", f"{auth['name']} {auth['token']}")
    conn = urlopen(req)  # nosec - Scheme is hardcoded to https
    return conn.read().decode("utf-8")


# Post the API request to the Opsgenie API
def api_post_request(url, auth, data):
    data = json.dumps(data).encode("utf-8")
    req = Request(url, data=data)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"{auth['name']} {auth['token']}")
    conn = urlopen(req)  # nosec - Scheme is hardcoded to https
    return conn.read().decode("utf-8")

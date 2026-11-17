"""Views of ``/sre incident show`` and its update modal: pure builders over the incident record.

The information view lists the incident's links, five roles, severity, status,
times and security flag, each changeable field with an Update button whose value
names the field. The field view is pushed over it for one field: a select for the
severity, status and security flag, one date-and-time picker for a time (Slack
renders and returns an absolute instant, so no time zone is looked up). Every
string comes from the ``incident_response`` catalogue in ``locale``; the private
metadata carries the channel and the locale, never the incident, which each
press and submission read fresh.
"""

import json
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any

from features.incident.common.vocabulary import IncidentRole, IncidentStatus, Severity
from features.incident.core.api import Incident
from features.incident.core.api import translate as t

SHOW_DOMAIN = "incident_response.show"
SHOW_CALLBACK_ID = "incident.response.show"
FIELD_CALLBACK_ID = "incident.response.update_field"
UPDATE_ACTION_ID = "incident.response.update_field.open"
VALUE_ACTION_ID = "incident.response.update_field.value"
SELECT_BLOCK_ID = "drop_down_input"
WHEN_BLOCK_ID = "date_time_input"


class Field(StrEnum):
    """The fields the update modal changes; each value is the Update button's value."""

    SEVERITY = "severity"
    STATUS = "status"
    DETECTION_TIME = "detection_time"
    START_IMPACT_TIME = "start_impact_time"
    END_IMPACT_TIME = "end_impact_time"
    SECURITY_INCIDENT = "security_incident"


# The record attribute each time field reads and writes.
TIME_ATTRIBUTES = {
    Field.DETECTION_TIME: "detected_at",
    Field.START_IMPACT_TIME: "impact_started_at",
    Field.END_IMPACT_TIME: "impact_ended_at",
}

# The severity picker's options until TASK-145.7.10 adds SEV0 with the declare picker.
SEVERITY_OPTIONS = ("none", "sev-1", "sev-2", "sev-3", "sev-4")
STATUS_OPTIONS = tuple(
    status.value
    for status in (
        IncidentStatus.OPEN,
        IncidentStatus.IN_PROGRESS,
        IncidentStatus.READY_TO_BE_REVIEWED,
        IncidentStatus.REVIEWED,
        IncidentStatus.CLOSED,
    )
)
SECURITY_OPTIONS = ("yes", "no")


def severity_value(severity: Severity | None) -> str:
    """The option value of ``severity``: ``sev-<n>``, or ``none`` while not rated."""
    return "none" if severity is None else f"sev-{severity.value}"


def security_value(flag: bool) -> str:
    """The option value of the security flag."""
    return "yes" if flag else "no"


def field_value(incident: Incident, field: Field) -> str | None:
    """The current option value of a select field; ``None`` for a time field."""
    match field:
        case Field.SEVERITY:
            return severity_value(incident.severity)
        case Field.STATUS:
            return incident.status.value
        case Field.SECURITY_INCIDENT:
            return security_value(incident.security_incident)
    return None


def build_show_view(
    incident: Incident,
    roles: Mapping[IncidentRole, str | None],
    *,
    report_link: str | None,
    call_link: str | None,
    locale: str,
    channel_id: str,
) -> dict[str, Any]:
    """Build the information modal of ``incident`` with ``roles`` and the report and call links."""
    links = [
        _link(report_link, _t("report", locale)),
        _link(call_link, _t("meet", locale)),
    ]
    blocks: list[dict[str, Any]] = [
        {"type": "header", "text": {"type": "plain_text", "text": incident.title, "emoji": True}},
        _section(f"*{_t('id', locale)}*: {incident.id}"),
        {"type": "section", "fields": [{"type": "mrkdwn", "text": link} for link in links]},
        {"type": "divider"},
        _field_section(Field.SEVERITY, severity_value(incident.severity), locale),
        _field_section(Field.STATUS, incident.status.value, locale),
        _field_section(Field.SECURITY_INCIDENT, _t(f"security.{security_value(incident.security_incident)}", locale), locale),
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*{_t(f'role.{role.value}', locale)}*:\n{_holder(roles.get(role), locale)}"}
                for role in IncidentRole
            ],
        },
        {"type": "divider"},
        _section(f"*{_t('label.created_at', locale)}*:\n{time_text(incident.declared_at, locale)}"),
    ]
    for field, attribute in TIME_ATTRIBUTES.items():
        blocks.append(_field_section(field, time_text(getattr(incident, attribute), locale), locale))
    return {
        "type": "modal",
        "callback_id": SHOW_CALLBACK_ID,
        "title": {"type": "plain_text", "text": _t("title", locale), "emoji": True},
        "close": {"type": "plain_text", "text": _t("close", locale), "emoji": True},
        "private_metadata": json.dumps({"channel_id": channel_id, "locale": locale}),
        "blocks": blocks,
    }


def build_field_view(incident: Incident, field: Field, *, locale: str, channel_id: str) -> dict[str, Any]:
    """Build the modal pushed over the information modal to change ``field`` of ``incident``."""
    input_block: dict[str, Any]
    if field in TIME_ATTRIBUTES:
        element: dict[str, Any] = {"type": "datetimepicker", "action_id": VALUE_ACTION_ID}
        current: datetime | None = getattr(incident, TIME_ATTRIBUTES[field])
        if current is not None:
            element["initial_date_time"] = int(current.timestamp())
        input_block = {
            "type": "input",
            "block_id": WHEN_BLOCK_ID,
            "element": element,
            "label": {"type": "plain_text", "text": _t("field.pick_time", locale)},
        }
    else:
        input_block = {
            "type": "input",
            "block_id": SELECT_BLOCK_ID,
            "element": _select(field, field_value(incident, field), locale),
            "label": {"type": "plain_text", "text": _t("field.pick_item", locale)},
        }
    return {
        "type": "modal",
        "callback_id": FIELD_CALLBACK_ID,
        "title": {"type": "plain_text", "text": _t("title", locale), "emoji": True},
        "submit": {"type": "plain_text", "text": _t("field.submit", locale), "emoji": True},
        "close": {"type": "plain_text", "text": _t("close", locale), "emoji": True},
        "private_metadata": json.dumps({"channel_id": channel_id, "locale": locale, "field": field.value}),
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": _t(f"label.{field.value}", locale), "emoji": True}},
            input_block,
        ],
    }


def time_text(when: datetime | None, locale: str) -> str:
    """A time as Slack's date token, which each reader sees in their own time zone; ``Unknown`` when unset."""
    unknown = _t("unknown", locale)
    if when is None:
        return unknown
    return f"<!date^{int(when.timestamp())}^{{date}} {_t('at', locale)} {{time}}|{unknown}>"


def instant_text(when: datetime) -> str:
    """A changed time for the channel notice: Slack's date token with the UTC time as its fallback."""
    return f"<!date^{int(when.timestamp())}^{{date_num}} {{time}}|{when.isoformat()}>"


def _select(field: Field, current: str | None, locale: str) -> dict[str, Any]:
    values = {Field.SEVERITY: SEVERITY_OPTIONS, Field.STATUS: STATUS_OPTIONS, Field.SECURITY_INCIDENT: SECURITY_OPTIONS}[field]
    options = [{"text": {"type": "plain_text", "text": option_text(field, value, locale)}, "value": value} for value in values]
    element: dict[str, Any] = {
        "type": "static_select",
        "placeholder": {"type": "plain_text", "text": _t("field.placeholder", locale)},
        "options": options,
        "action_id": VALUE_ACTION_ID,
    }
    # A stored value outside the options (a SEV0 before TASK-145.7.10) preselects nothing rather than an invalid option.
    initial = next((option for option in options if option["value"] == current), None)
    if initial is not None:
        element["initial_option"] = initial
    return element


def option_text(field: Field, value: str, locale: str) -> str:
    """What a select option or a notice shows for ``value``: the yes/no words of the security flag, else the value."""
    return _t(f"security.{value}", locale) if field is Field.SECURITY_INCIDENT else value


def _field_section(field: Field, shown: str, locale: str) -> dict[str, Any]:
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*{_t(f'label.{field.value}', locale)}*:\n{shown}"},
        "accessory": {
            "type": "button",
            "text": {"type": "plain_text", "text": _t("update", locale), "emoji": True},
            "value": field.value,
            "action_id": UPDATE_ACTION_ID,
        },
    }


def _section(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _link(url: str | None, label: str) -> str:
    return f"<{url}|{label}>" if url else label


def _holder(user_id: str | None, locale: str) -> str:
    return f"<@{user_id}>" if user_id else _t("unassigned", locale)


def _t(key: str, locale: str, **variables: str) -> str:
    """Translate ``key`` of the show catalogue; the key itself is the neutral fallback (decisions/i18n.md)."""
    full_key = f"{SHOW_DOMAIN}.{key}"
    return t(full_key, locale, full_key, **variables)

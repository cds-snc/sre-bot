"""Views of the postmortem schedule flow: pure builders over the prefill, the settings and the outcome.

The schedule view has two user pickers (Must attend, defaulting to the incident's
role holders; Invite, defaulting to the channel's other people; anyone in the
workspace may be added), the number of days before the search starts, the rules
the search applies (from the [incident_postmortem] settings) and, once a preview
ran, who cannot be counted on. The working, outcome and error views replace it
after submission. No handler opens them yet.

Every string comes from the ``incident_postmortem`` catalogue in ``languages``: the
opener's language from a command, the instance languages from a button whose payload
names none (decisions/languages.md). With several languages a body text has one line
per language and an input label joins them with " / "; the title, submit and close,
which Slack caps at 24 characters, show the first language. The private metadata
carries the channel and the languages, never the incident, which the submission
reads fresh.
"""

import json
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from features.incident.postmortem.domain import Attendee, AttendeeOverview, SlotPolicy, local_time
from features.incident.postmortem.entrypoints.texts import text, when_text
from features.incident.postmortem.service.schedule import ScheduleOutcome, ScheduleState
from features.incident.postmortem.settings import IncidentPostmortemSettings

SCHEDULE_CALLBACK_ID = "incident.postmortem.schedule"
REQUIRED_BLOCK_ID = "postmortem_required"
REQUIRED_ACTION_ID = "incident.postmortem.schedule.required"
OPTIONAL_BLOCK_ID = "postmortem_optional"
OPTIONAL_ACTION_ID = "incident.postmortem.schedule.optional"
START_AFTER_BLOCK_ID = "postmortem_start_after"
START_AFTER_ACTION_ID = "incident.postmortem.schedule.start_after"


def view_metadata(channel_id: str, languages: Sequence[str]) -> str:
    """The private metadata of every postmortem view: the channel and the view's languages."""
    return json.dumps({"channel_id": channel_id, "languages": list(languages)})


def read_metadata(private_metadata: str) -> tuple[str, tuple[str, ...]]:
    """The channel and the languages ``view_metadata`` stored."""
    data = json.loads(private_metadata)
    return str(data["channel_id"]), tuple(str(language) for language in data["languages"])


def build_schedule_view(
    *,
    languages: Sequence[str],
    channel_id: str,
    required: Sequence[str],
    optional: Sequence[str],
    settings: IncidentPostmortemSettings,
    now: datetime,
    overview: AttendeeOverview | None = None,
) -> dict[str, Any]:
    """The schedule view, its pickers prefilled; ``overview`` adds the preview's warnings."""
    policy = settings.slot_policy()
    blocks: list[dict[str, Any]] = [
        _section(_body("schedule.intro", languages)),
        _context(_body("schedule.rules", languages, **_rules(policy, now))),
        _users_input(REQUIRED_BLOCK_ID, REQUIRED_ACTION_ID, "schedule.required", languages, required, optional=False),
        _users_input(OPTIONAL_BLOCK_ID, OPTIONAL_ACTION_ID, "schedule.optional", languages, optional, optional=True),
        {
            "type": "input",
            "block_id": START_AFTER_BLOCK_ID,
            "label": _plain(_label("schedule.start_after.label", languages)),
            "element": {
                "type": "number_input",
                "action_id": START_AFTER_ACTION_ID,
                "is_decimal_allowed": False,
                "initial_value": str(settings.default_start_offset_days),
                "min_value": "0",
                "max_value": str(settings.max_start_offset_days),
            },
        },
    ]
    if overview is not None and overview.always_busy:
        blocks.append(_context(_body("schedule.warning.busy", languages, names=_names(overview.always_busy))))
    if overview is not None and overview.unknown:
        blocks.append(_context(_body("schedule.warning.unknown", languages, names=_names(overview.unknown))))
    return {
        "type": "modal",
        "callback_id": SCHEDULE_CALLBACK_ID,
        "title": _plain(_capped("schedule.title", languages)),
        "submit": _plain(_capped("schedule.submit", languages)),
        "close": _plain(_capped("schedule.close", languages)),
        "private_metadata": view_metadata(channel_id, languages),
        "blocks": blocks,
    }


def build_working_view(*, languages: Sequence[str], channel_id: str) -> dict[str, Any]:
    """The view shown while the search runs."""
    return _result_view(languages, channel_id, [_section(_body("working.text", languages))], title="working.title")


def build_outcome_view(
    outcome: ScheduleOutcome, *, languages: Sequence[str], channel_id: str, policy: SlotPolicy
) -> dict[str, Any]:
    """The view after a schedule: the meeting booked, recreated or already scheduled, or why there is none.

    An existing meeting is shown with its time, link and invitees; this view offers no
    action on it.
    """
    meeting = outcome.meeting
    if outcome.state is ScheduleState.NO_SLOT or meeting is None:
        blocked = outcome.search.blocking_required if outcome.search is not None else ()
        reason = outcome.reason.value if outcome.reason is not None else "no_candidate"
        blocks = [_section(_body(f"result.no_slot.{reason}", languages, names=_names(blocked)))]
        return _result_view(languages, channel_id, blocks)

    key = {
        ScheduleState.BOOKED: "result.booked",
        ScheduleState.RECREATED: "result.recreated",
        ScheduleState.ALREADY_SCHEDULED: "result.already",
    }[outcome.state]
    blocks = [
        _section(_lines(languages, lambda language: text(key, language, when=when_text(meeting.start, policy, language)))),
        _section(_body("result.link", languages, url=meeting.url)),
        _context(_body("result.attendees", languages, names=", ".join(meeting.attendees))),
    ]
    if outcome.holidays_unavailable:
        blocks.append(_context(_body("result.holidays_unavailable", languages)))
    search = outcome.search
    if search is not None:
        for group, attendees in (
            ("required_unknown", search.required_unknown),
            ("optional_busy", search.optional_busy),
            ("optional_unknown", search.optional_unknown),
            ("excluded_optional", search.excluded_optional),
        ):
            if attendees:
                blocks.append(_context(_body(f"result.{group}", languages, names=_names(attendees))))
    return _result_view(languages, channel_id, blocks)


def build_error_view(key: str, *, languages: Sequence[str], channel_id: str) -> dict[str, Any]:
    """A refusal or failure: ``error.not_an_incident`` or ``error.failed``."""
    return _result_view(languages, channel_id, [_section(_body(key, languages))])


def _result_view(
    languages: Sequence[str], channel_id: str, blocks: list[dict[str, Any]], *, title: str = "schedule.title"
) -> dict[str, Any]:
    return {
        "type": "modal",
        "callback_id": SCHEDULE_CALLBACK_ID,
        "title": _plain(_capped(title, languages)),
        "close": _plain(_capped("result.close", languages)),
        "private_metadata": view_metadata(channel_id, languages),
        "blocks": blocks,
    }


def _rules(policy: SlotPolicy, now: datetime) -> dict[str, str]:
    """The rules sentence's values; the zone abbreviation is today's (it changes with daylight saving time)."""
    return {
        "duration": str(int(policy.duration.total_seconds() // 60)),
        "start": policy.window_start.strftime("%H:%M"),
        "end": policy.window_end.strftime("%H:%M"),
        "zone": local_time(now, policy).zone,
        "quorum": str(policy.optional_quorum_percent),
    }


def _users_input(
    block_id: str, action_id: str, key: str, languages: Sequence[str], users: Sequence[str], *, optional: bool
) -> dict[str, Any]:
    element: dict[str, Any] = {"type": "multi_users_select", "action_id": action_id}
    if users:
        element["initial_users"] = list(users)
    return {
        "type": "input",
        "block_id": block_id,
        "optional": optional,
        "label": _plain(_label(f"{key}.label", languages)),
        "hint": _plain(_label(f"{key}.hint", languages)),
        "element": element,
    }


def _names(attendees: Sequence[Attendee]) -> str:
    return ", ".join(f"<@{attendee.account_id}>" for attendee in attendees)


def _capped(key: str, languages: Sequence[str]) -> str:
    """A label Slack caps: the first language only (decisions/languages.md)."""
    return text(key, languages[0])


def _label(key: str, languages: Sequence[str]) -> str:
    """An uncapped label: every language, joined by " / "."""
    return " / ".join(text(key, language) for language in languages)


def _body(key: str, languages: Sequence[str], **variables: str) -> str:
    """A body text: one line per language."""
    return _lines(languages, lambda language: text(key, language, **variables))


def _lines(languages: Sequence[str], line: Callable[[str], str]) -> str:
    return "\n".join(line(language) for language in languages)


def _plain(value: str) -> dict[str, Any]:
    return {"type": "plain_text", "text": value, "emoji": True}


def _section(value: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": value}}


def _context(value: str) -> dict[str, Any]:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": value}]}

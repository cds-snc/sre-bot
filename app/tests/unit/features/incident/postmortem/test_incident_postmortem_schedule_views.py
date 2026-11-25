"""The schedule flow's views and the catalogue wording of the meeting and the channel notice.

Pure builders over hand-built inputs, rendered from the EN and FR catalogues the
conftest loads. Assertions read the Block Kit dicts: one language from a command,
every instance language from a button (a line per language in a body, " / " in an
input label, the first language in a title Slack caps), the metadata round trip,
the rules sentence built from the settings, the preview's warnings, and the
outcome views. The texts tests pin the shared order of the notice and the meeting
label, and the meeting time in each language with that date's zone abbreviation.
"""

from datetime import UTC, datetime, timedelta

import pytest

from features.incident.core.api import MeetingStatus, ScheduledMeeting
from features.incident.postmortem.domain import Attendee, AttendeeOverview, NoSlotReason, SlotPolicy, SlotSearch
from features.incident.postmortem.entrypoints.slack_views import (
    OPTIONAL_BLOCK_ID,
    REQUIRED_BLOCK_ID,
    START_AFTER_BLOCK_ID,
    build_error_view,
    build_outcome_view,
    build_schedule_view,
    build_working_view,
    read_metadata,
)
from features.incident.postmortem.entrypoints.texts import CatalogueScheduleTexts, when_text
from features.incident.postmortem.service.schedule import ScheduleOutcome, ScheduleState
from features.incident.postmortem.settings import IncidentPostmortemSettings
from tests.factories.incident import incident_on

pytestmark = pytest.mark.unit

NOW = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)
START = datetime(2026, 12, 2, 18, 0, tzinfo=UTC)
MEETING = ScheduledMeeting(
    id="abc123",
    title="Retro / Rétro — Incident INC1",
    start=START,
    end=START + timedelta(minutes=30),
    status=MeetingStatus.CONFIRMED,
    url="https://calendar.example/abc123",
    video_url=None,
    attendees=("ic@example.org", "bo@example.org"),
)
ENGLISH = ("en-US",)

BOTH = ("en-US", "fr-FR")
FRENCH_FIRST = ("fr-FR", "en-US")


def _policy() -> SlotPolicy:
    """The policy base.toml declares (the configuration files are installed per test)."""
    return IncidentPostmortemSettings().slot_policy()


def _view(languages: tuple[str, ...], overview: AttendeeOverview | None = None) -> dict:
    return build_schedule_view(
        languages=languages,
        channel_id="C0INC",
        required=("U0IC",),
        optional=("U0BO", "U0OPS"),
        settings=IncidentPostmortemSettings(),
        now=NOW,
        overview=overview,
    )


def _block(view: dict, block_id: str) -> dict:
    return next(block for block in view["blocks"] if block.get("block_id") == block_id)


def _texts(view: dict) -> str:
    parts = []
    for block in view["blocks"]:
        if "text" in block:
            parts.append(block["text"]["text"])
        parts += [element["text"] for element in block.get("elements", [])]
    return "\n".join(parts)


def test_a_view_opened_by_a_command_is_in_the_openers_language_only() -> None:
    view = _view(ENGLISH)

    assert view["title"]["text"] == "Schedule retro 🗓️"
    assert _block(view, REQUIRED_BLOCK_ID)["label"]["text"] == "Must attend"
    assert "Planifier" not in _texts(view)


def test_a_view_opened_by_a_button_carries_every_instance_language() -> None:
    """The title is capped, so it shows the first language; labels join; bodies take a line per language."""
    view = _view(FRENCH_FIRST)

    assert view["title"]["text"] == "Planifier la rétro 🗓️"
    assert view["submit"]["text"] == "Planifier"
    assert _block(view, REQUIRED_BLOCK_ID)["label"]["text"] == "Présence requise / Must attend"
    intro = view["blocks"][0]["text"]["text"].split("\n")
    assert intro == [
        "Réserver la rencontre de rétro de cet incident au premier moment qui convient.",
        "Book the retro meeting for this incident on the first time that works.",
    ]


def test_the_pickers_are_prefilled_and_only_the_invite_picker_is_optional() -> None:
    view = _view(ENGLISH)

    required, optional = _block(view, REQUIRED_BLOCK_ID), _block(view, OPTIONAL_BLOCK_ID)
    assert (required["element"]["type"], required["element"]["initial_users"], required["optional"]) == (
        "multi_users_select",
        ["U0IC"],
        False,
    )
    assert (optional["element"]["initial_users"], optional["optional"]) == (["U0BO", "U0OPS"], True)


def test_the_start_offset_input_takes_its_default_and_bounds_from_the_settings() -> None:
    element = _block(_view(ENGLISH), START_AFTER_BLOCK_ID)["element"]

    assert (element["initial_value"], element["min_value"], element["max_value"]) == ("1", "0", "60")


def test_the_rules_sentence_comes_from_the_settings_with_todays_zone_abbreviation() -> None:
    rules = _view(ENGLISH)["blocks"][1]["elements"][0]["text"]

    assert rules == (
        "I book the first 30-minute time between 13:00 and 15:00 (EST) on a working day, skipping public holidays, "
        "when nobody who must attend is busy and at least 50% of the invited people are free."
    )


def test_the_preview_warns_about_people_busy_throughout_and_unreadable_calendars() -> None:
    overview = AttendeeOverview(
        always_busy=(Attendee("U0AWAY", "away@example.org", False),), unknown=(Attendee("U0NOMAIL", None, True),)
    )

    texts = _texts(_view(ENGLISH, overview))

    assert "Busy for the whole search: <@U0AWAY>" in texts
    assert "counted as not free: <@U0NOMAIL>" in texts


def test_the_metadata_round_trips_the_channel_and_languages() -> None:
    assert read_metadata(_view(FRENCH_FIRST)["private_metadata"]) == ("C0INC", FRENCH_FIRST)


def test_a_booked_outcome_shows_the_time_link_invitees_and_who_to_name() -> None:
    search = SlotSearch(slot=None, optional_busy=(Attendee("U0BO", "bo@example.org", False),))
    outcome = ScheduleOutcome(state=ScheduleState.BOOKED, meeting=MEETING, search=search, holidays_unavailable=True)

    texts = _texts(build_outcome_view(outcome, languages=ENGLISH, channel_id="C0INC", policy=_policy()))

    assert "The retro is booked for Wednesday, December 2, 2026 at 13:00 EST." in texts
    assert "<https://calendar.example/abc123|Open the meeting in the calendar>" in texts
    assert "Invited: ic@example.org, bo@example.org" in texts
    assert "Public holidays could not be checked" in texts
    assert "Busy at that time: <@U0BO>" in texts


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (ScheduleState.ALREADY_SCHEDULED, "This incident's retro is already scheduled for Wednesday"),
        (ScheduleState.RECREATED, "The previous retro meeting was removed from the calendar"),
    ],
)
def test_an_existing_or_recreated_meeting_says_so(state: ScheduleState, expected: str) -> None:
    view = build_outcome_view(
        ScheduleOutcome(state=state, meeting=MEETING), languages=ENGLISH, channel_id="C0INC", policy=_policy()
    )

    assert expected in _texts(view)
    assert "submit" not in view


def test_no_slot_names_the_reason_and_the_people_blocking() -> None:
    search = SlotSearch(
        slot=None, reason=NoSlotReason.REQUIRED_ALWAYS_BUSY, blocking_required=(Attendee("U0IC", "ic@example.org", True),)
    )
    outcome = ScheduleOutcome(state=ScheduleState.NO_SLOT, search=search, reason=NoSlotReason.REQUIRED_ALWAYS_BUSY)

    texts = _texts(build_outcome_view(outcome, languages=ENGLISH, channel_id="C0INC", policy=_policy()))

    assert texts.startswith("These people must attend but are busy for the whole search")
    assert texts.endswith("<@U0IC>")


@pytest.mark.parametrize("reason", list(NoSlotReason))
def test_every_no_slot_reason_has_wording(reason: NoSlotReason) -> None:
    outcome = ScheduleOutcome(state=ScheduleState.NO_SLOT, reason=reason)

    texts = _texts(build_outcome_view(outcome, languages=BOTH, channel_id="C0INC", policy=_policy()))

    assert "incident_postmortem." not in texts


def test_the_working_and_error_views_render_catalogue_wording() -> None:
    working = _texts(build_working_view(languages=ENGLISH, channel_id="C0INC"))
    error = _texts(build_error_view("error.not_an_incident", languages=ENGLISH, channel_id="C0INC"))

    assert working == "Looking for a time that works…"
    assert error.startswith("This channel is not an incident channel")


@pytest.mark.parametrize(
    ("moment", "language", "expected"),
    [
        (START, "en-US", "Wednesday, December 2, 2026 at 13:00 EST"),
        (START, "fr-FR", "mercredi 2 décembre 2026 à 13:00 EST"),
        (datetime(2026, 10, 30, 17, 0, tzinfo=UTC), "en-US", "Friday, October 30, 2026 at 13:00 EDT"),
    ],
)
def test_a_meeting_time_reads_in_each_language_with_its_dates_zone(moment: datetime, language: str, expected: str) -> None:
    assert when_text(moment, _policy(), language) == expected


@pytest.mark.parametrize("languages", [BOTH, FRENCH_FIRST, ENGLISH])
def test_the_notice_and_the_meeting_label_follow_the_shared_order(languages: tuple[str, ...]) -> None:
    texts = CatalogueScheduleTexts(languages, _policy())

    notice = texts.scheduled_notice(MEETING, recreated=False, holidays_unavailable=False)

    assert [language for language, _ in notice.parts] == list(languages)
    assert [language for language, _ in texts.meeting_label().parts] == list(languages)
    assert dict(notice.parts)["en-US"] == (
        "The retro is scheduled for Wednesday, December 2, 2026 at 13:00 EST: https://calendar.example/abc123"
    )


def test_a_recreated_notice_with_holidays_unavailable_says_both() -> None:
    notice = CatalogueScheduleTexts(ENGLISH, _policy()).scheduled_notice(MEETING, recreated=True, holidays_unavailable=True)

    (line,) = (text for _, text in notice.parts)
    assert line.startswith("The retro meeting was removed from the calendar, so a new one is scheduled for")
    assert line.endswith("Public holidays could not be checked, so the time may fall on one.")


def test_the_meeting_description_names_the_incident_and_the_report_title_joins_languages() -> None:
    texts = CatalogueScheduleTexts(FRENCH_FIRST, _policy())

    description = texts.meeting_description(incident_on("C0INC", "INC1"))

    assert dict(description.parts)["fr-FR"] == "Rétrospective de l'incident « Incident INC1 ». Le rapport d'incident est joint."
    assert texts.report_title() == "Rapport d'incident / Incident report"

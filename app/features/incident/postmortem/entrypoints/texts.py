"""The postmortem's wording from the ``incident_postmortem`` catalogue.

``CatalogueScheduleTexts`` is the schedule service's ``ScheduleTexts`` in the
languages it is built with: the conversation's shared languages, since the meeting
and the channel notice are shared (decisions/languages.md). ``when_text`` renders a
meeting time in one language from the catalogue's weekday and month names and the
date's own zone abbreviation, in-house until TASK-118 chooses a formatting library
(decisions/i18n.md). ``register_catalogue`` registers the catalogue; it is a plain
function, not a hookimpl, until the cutover (TASK-145.10.4) adds ``plugin.py`` with an
entry point whose ``register_i18n_resources`` calls it.
"""

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from contracts.i18n.resources import I18nResourceRegistrar, I18nResourceSpec
from contracts.languages import MultilingualText
from features.incident.core.api import Incident, ScheduledMeeting
from features.incident.core.api import translate as t
from features.incident.postmortem.domain import SlotPolicy, local_time

DOMAIN = "incident_postmortem"
LOCALES_DIR = Path(__file__).parent.parent / "locales"


def register_catalogue(registry: I18nResourceRegistrar) -> None:
    """Register the ``incident_postmortem`` catalogue in ``locales``."""
    registry.register(
        I18nResourceSpec(
            owner="features.incident.postmortem", path=str(LOCALES_DIR), required=False, format="yaml", domain=DOMAIN
        )
    )


def text(key: str, language: str, **variables: str) -> str:
    """Translate ``key`` of the postmortem catalogue; the key itself is the neutral fallback (decisions/i18n.md)."""
    full_key = f"{DOMAIN}.{key}"
    return t(full_key, language, full_key, **variables)


def when_text(moment: datetime, policy: SlotPolicy, language: str) -> str:
    """``moment`` in the policy's zone as a sentence fragment in ``language``."""
    parts = local_time(moment, policy)
    return text(
        "time.format",
        language,
        weekday=text(f"time.weekday.{parts.weekday}", language),
        month=text(f"time.month.{parts.month}", language),
        day=str(parts.day),
        year=str(parts.year),
        clock=parts.clock,
        zone=parts.zone,
    )


class CatalogueScheduleTexts:
    """``ScheduleTexts`` from the catalogue, in ``languages`` (in order)."""

    def __init__(self, languages: Sequence[str], policy: SlotPolicy) -> None:
        self._languages = tuple(languages)
        self._policy = policy

    def meeting_label(self) -> MultilingualText:
        """``meeting.label`` in every language."""
        return MultilingualText.of(self._languages, lambda language: text("meeting.label", language))

    def meeting_description(self, incident: Incident) -> MultilingualText:
        """``meeting.description`` naming the incident title (user content, once per language's sentence)."""
        return MultilingualText.of(self._languages, lambda language: text("meeting.description", language, title=incident.title))

    def report_title(self) -> str:
        """``meeting.report`` in every language, joined as an uncapped label (decisions/languages.md)."""
        return " / ".join(text("meeting.report", language) for language in self._languages)

    def scheduled_notice(self, meeting: ScheduledMeeting, *, recreated: bool, holidays_unavailable: bool) -> MultilingualText:
        """``notice.booked`` or ``notice.recreated``, then the holiday caveat when it applies, per language."""
        key = "notice.recreated" if recreated else "notice.booked"

        def line(language: str) -> str:
            notice = text(key, language, when=when_text(meeting.start, self._policy, language), url=meeting.url)
            if holidays_unavailable:
                notice = f"{notice} {text('notice.holidays_unavailable', language)}"
            return notice

        return MultilingualText.of(self._languages, line)

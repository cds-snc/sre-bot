"""Domain values and rules for the incident comms use case: public status updates.

Frozen, platform-neutral dataclasses shared by the services, the publisher and
the platform adapters, and the default comms profile: how a status update
reads as public text. This module depends only on the stdlib and the incident
core's public types.

The profile is modelled on GC Notify's published incident history. It shows
the stage, affected service, impact, current action, workaround and, unless
the incident is resolved, the next update time in America/Toronto as
``YYYY-MM-DD HH:MM`` followed by the language's zone suffix (ET or HE).
Rendering is pure: the caller supplies already-localized labels, so this
module has no translation lookups and no platform SDK. The copy-ready text
and every status page publisher render through ``render_copy_ready`` so they
cannot drift.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateText

_TEXT_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_PROFILE_ZONE = ZoneInfo("America/Toronto")
_TIME_FORMAT = "%Y-%m-%d %H:%M"


class StatusUpdateOutcomeKind(StrEnum):
    """How a status-update run produced the draft it returns."""

    DRAFTED = "drafted"
    CARRIED_FORWARD = "carried_forward"
    PENDING = "pending"
    MANUAL = "manual"


@dataclass(frozen=True)
class StatusUpdateDraftOutcome:
    """The draft a status-update run returns, and how it came to be.

    Attributes:
        update: The draft record, as stored.
        kind: ``DRAFTED`` from new activity by one model call,
            ``CARRIED_FORWARD`` from the prior update with nothing new,
            ``PENDING`` when an existing draft already covers everything, or
            ``MANUAL`` for the responder to write, prefilled from the latest
            approved update, when they chose to or the model call failed.
    """

    update: StatusUpdate
    kind: StatusUpdateOutcomeKind


@dataclass(frozen=True)
class DraftedFields:
    """The stage and the language-specific fields the model filled."""

    stage: StatusUpdateStage
    en: StatusUpdateText
    fr: StatusUpdateText


@dataclass(frozen=True)
class NoNewInformationWording:
    """The current-action wording of a carried-forward update, per language.

    Supplied by the platform layer from the catalogues, so the service stays
    free of translation lookups.
    """

    en: str
    fr: str


@dataclass(frozen=True)
class StatusUpdateEdit:
    """The stage and both languages' fields a responder submits, saves or hands to the model as its base."""

    stage: StatusUpdateStage
    en: StatusUpdateText
    fr: StatusUpdateText

    def blank_fields(self) -> tuple[str, ...]:
        """Return the names (``en.impact``, ``fr.workaround``, ...) of the fields blank after trimming."""
        return tuple(
            f"{language}.{name}"
            for language, text in (("en", self.en), ("fr", self.fr))
            for name in _TEXT_FIELDS
            if not getattr(text, name).strip()
        )


@dataclass(frozen=True)
class CopyReadyText:
    """An approved update rendered as plain text to paste, one string per language."""

    en: str
    fr: str


@dataclass(frozen=True)
class StatusUpdateOverview:
    """An incident's status updates as the form lists them.

    Attributes:
        pending: The latest record when it is a draft, else ``None``.
        approved: Every approved or published record, newest first.
    """

    pending: StatusUpdate | None
    approved: tuple[StatusUpdate, ...]


@dataclass(frozen=True)
class StatusUpdateFormState:
    """The review form to show after a status-update action.

    Attributes:
        update: The draft whose stage and fields fill the form: the new or
            stored draft, or, when ``kept``, the stored draft overlaid with the
            responder's typed values.
        ai_available: Whether the form offers Draft with AI.
        kind: How a start or fill produced ``update``; ``None`` for a read or a save.
        kept: ``True`` when the action changed nothing and the stored draft was kept.
        failure_code: The classified code that explains a kept draft, when known.
    """

    update: StatusUpdate
    ai_available: bool
    kind: StatusUpdateOutcomeKind | None = None
    kept: bool = False
    failure_code: str | None = None


@dataclass(frozen=True)
class PublishedRecord:
    """An approved status update with its copy-ready text, as the copy-ready text shows it."""

    update: StatusUpdate
    text: CopyReadyText


@dataclass(frozen=True)
class ProfileLabels:
    """The localized labels of one language's rendered profile.

    Attributes:
        stage: Label of the stage line.
        affected_service: Label of the affected service line.
        impact: Label of the impact line.
        current_action: Label of the current action line.
        workaround: Label of the workaround line.
        next_update: Label of the next update line.
        time_suffix: Zone suffix after the time (ET in English, HE in French).
        stage_names: Display name of each stage.
    """

    stage: str
    affected_service: str
    impact: str
    current_action: str
    workaround: str
    next_update: str
    time_suffix: str
    stage_names: Mapping[StatusUpdateStage, str]


def format_profile_time(moment: datetime, labels: ProfileLabels) -> str:
    """Return ``moment`` as ``YYYY-MM-DD HH:MM`` in America/Toronto followed by the language's zone suffix."""
    return f"{moment.astimezone(_PROFILE_ZONE).strftime(_TIME_FORMAT)} {labels.time_suffix}"


def render_profile_sections(
    text: StatusUpdateText,
    stage: StatusUpdateStage,
    next_update_at: datetime,
    labels: ProfileLabels,
) -> tuple[str, ...]:
    """Return one language of a status update as ``Label: value`` lines, one per field.

    Args:
        text: The update's fields in this language.
        stage: The update's stage.
        next_update_at: When the next update is due; timezone-aware.
        labels: The language's labels and zone suffix.

    Returns:
        The lines in order: stage, affected service, impact, current action,
        workaround, then the next update time. A resolved incident has no
        next update, so that line is left out.
    """
    lines = [
        f"{labels.stage}: {labels.stage_names[stage]}",
        f"{labels.affected_service}: {text.affected_service}",
        f"{labels.impact}: {text.impact}",
        f"{labels.current_action}: {text.current_action}",
        f"{labels.workaround}: {text.workaround}",
    ]
    if stage is not StatusUpdateStage.RESOLVED:
        lines.append(f"{labels.next_update}: {format_profile_time(next_update_at, labels)}")
    return tuple(lines)


def render_profile(
    text: StatusUpdateText,
    stage: StatusUpdateStage,
    next_update_at: datetime,
    labels: ProfileLabels,
) -> str:
    """Render one language of a status update, the lines of ``render_profile_sections`` one per row."""
    return "\n".join(render_profile_sections(text, stage, next_update_at, labels))


def render_copy_ready(update: StatusUpdate, labels_en: ProfileLabels, labels_fr: ProfileLabels) -> CopyReadyText:
    """Return the update's English and French text, label lines separated by a blank line.

    Args:
        update: The update; its stored ``next_update_at`` is rendered.
        labels_en: English labels and zone suffix.
        labels_fr: French labels and zone suffix.
    """
    en = render_profile_sections(update.en, update.stage, update.next_update_at, labels_en)
    fr = render_profile_sections(update.fr, update.stage, update.next_update_at, labels_fr)
    return CopyReadyText(en="\n\n".join(en), fr="\n\n".join(fr))

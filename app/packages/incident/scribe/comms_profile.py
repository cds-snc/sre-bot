"""Default comms profile: how a status update reads as public text.

Modelled on GC Notify's published incident history. The profile shows the
stage, affected service, impact, current action, workaround and, unless the
incident is resolved, the next update time in America/Toronto as
``YYYY-MM-DD HH:MM`` followed by the language's zone suffix (ET or HE).

Pure rendering: the caller supplies already-localized labels, so this module
has no translation lookups and no platform SDK.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from packages.incident.core.api import StatusUpdateStage, StatusUpdateText

_PROFILE_ZONE = ZoneInfo("America/Toronto")
_TIME_FORMAT = "%Y-%m-%d %H:%M"


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
        local = next_update_at.astimezone(_PROFILE_ZONE)
        lines.append(f"{labels.next_update}: {local.strftime(_TIME_FORMAT)} {labels.time_suffix}")
    return tuple(lines)


def render_profile(
    text: StatusUpdateText,
    stage: StatusUpdateStage,
    next_update_at: datetime,
    labels: ProfileLabels,
) -> str:
    """Render one language of a status update, the lines of ``render_profile_sections`` one per row."""
    return "\n".join(render_profile_sections(text, stage, next_update_at, labels))

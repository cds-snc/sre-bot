"""Render an approved status update as copy-ready text.

Pure and side-effect free, so the copy-ready adapter and the later status page
publisher render the same text. Each language is the comms profile's lines
joined by a blank line, which pastes cleanly into plain-text and Markdown
targets.
"""

from features.incident.core.api import StatusUpdate
from features.incident.scribe.comms_profile import ProfileLabels, render_profile_sections
from features.incident.scribe.domain import CopyReadyText


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

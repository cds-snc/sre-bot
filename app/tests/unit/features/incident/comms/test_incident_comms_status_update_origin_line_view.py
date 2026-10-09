"""Tests for the line above a pending draft that says who made it, how and when.

``origin_line`` words the draft's origin (written by a responder, drafted by AI,
redrafted with instructions, carried forward) with its creation time through
``format_profile_time``; a record from before origins existed names only its
author. ``build_overview_view`` shows the line in a context block just above
the pending draft, and never when nothing is pending. The builders are pure and
called directly. The comms catalogue is loaded by the directory's conftest,
so wording is the catalogue's EN or FR template, pinned literally; the
catalogue test reads both YAML files and requires the same templates.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

import features.incident.comms as comms_pkg
from features.incident.comms.domain import StatusUpdateOverview
from features.incident.comms.entrypoints.slack_views import build_overview_view, origin_line
from features.incident.core.api import (
    StatusUpdate,
    StatusUpdateOrigin,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": "C123", "locale": "en-US"})
_LOCALES_DIR = Path(comms_pkg.__file__).parent / "locales"

_EN_TEMPLATES = {
    "origin.hand": "Written by {author} at {time}",
    "origin.model": "Drafted by AI at {time}",
    "origin.model_instructed": "Redrafted with instructions at {time}",
    "origin.carried_forward": "Carried forward at {time}",
    "origin.unknown": "By {author} at {time}",
}
_FR_TEMPLATES = {
    "origin.hand": "Rédigée par {author} le {time}",
    "origin.model": "Rédigée par l'IA le {time}",
    "origin.model_instructed": "Rédigée à nouveau selon des instructions le {time}",
    "origin.carried_forward": "Reprise de la mise à jour précédente le {time}",
    "origin.unknown": "Par {author} le {time}",
}


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


_DRAFT = StatusUpdate(
    incident_id="inc-uuid-1",
    sequence=2,
    state=StatusUpdateState.DRAFT,
    stage=StatusUpdateStage.IDENTIFIED,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW,
    author="U999",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc123",
    created_at=_NOW,
    origin=StatusUpdateOrigin.HAND,
)


class TestOriginLine:
    @pytest.mark.parametrize(
        ("origin", "expected"),
        [
            (StatusUpdateOrigin.HAND, "Written by <@U999> at 2026-10-07 11:00 ET"),
            (StatusUpdateOrigin.MODEL, "Drafted by AI at 2026-10-07 11:00 ET"),
            (StatusUpdateOrigin.MODEL_INSTRUCTED, "Redrafted with instructions at 2026-10-07 11:00 ET"),
            (StatusUpdateOrigin.CARRIED_FORWARD, "Carried forward at 2026-10-07 11:00 ET"),
            (None, "By <@U999> at 2026-10-07 11:00 ET"),
        ],
        ids=["hand", "model", "model-instructed", "carried-forward", "no-origin"],
    )
    def test_each_origin_is_worded_with_the_eastern_time(self, origin: StatusUpdateOrigin | None, expected: str) -> None:
        """The responder sees how the draft was made and when, in Eastern time; an old record shows its author only."""
        assert origin_line(replace(_DRAFT, origin=origin), "en-US") == expected

    @pytest.mark.parametrize(
        ("origin", "expected"),
        [
            (StatusUpdateOrigin.HAND, "Rédigée par <@U999> le 2026-10-07 11:00 HE"),
            (StatusUpdateOrigin.MODEL, "Rédigée par l'IA le 2026-10-07 11:00 HE"),
            (None, "Par <@U999> le 2026-10-07 11:00 HE"),
        ],
        ids=["hand", "model", "no-origin"],
    )
    def test_french_wording_and_zone_suffix(self, origin: StatusUpdateOrigin | None, expected: str) -> None:
        """A French modal words the line in French with the HE suffix."""
        assert origin_line(replace(_DRAFT, origin=origin), "fr-FR") == expected

    @pytest.mark.parametrize(("locale", "templates"), [("en-US", _EN_TEMPLATES), ("fr-FR", _FR_TEMPLATES)])
    def test_catalogue_holds_the_origin_templates(self, locale: str, templates: dict[str, str]) -> None:
        """Each template is in the catalogue exactly as ``origin_line`` renders it."""
        data = yaml.safe_load((_LOCALES_DIR / f"incident_status_update.{locale}.yml").read_text(encoding="utf-8"))
        catalogue: dict[str, str] = data["incident_status_update"]

        assert {key: catalogue.get(key) for key in templates} == templates


class TestOverviewOriginBlock:
    def test_the_line_sits_just_above_the_pending_draft(self) -> None:
        """The overview opens with the origin context block, then the draft's English heading."""
        view = build_overview_view(StatusUpdateOverview(pending=_DRAFT, approved=()), "en-US", _METADATA)

        assert view["blocks"][0] == {
            "type": "context",
            "block_id": "pending_origin",
            "elements": [{"type": "mrkdwn", "text": "Written by <@U999> at 2026-10-07 11:00 ET"}],
        }
        assert view["blocks"][1] == {"type": "header", "text": {"type": "plain_text", "text": "English"}}

    def test_no_line_without_a_pending_draft(self) -> None:
        """With nothing pending there is nobody to credit, so no origin block is shown."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=()), "en-US", _METADATA)

        assert "pending_origin" not in [block.get("block_id") for block in view["blocks"]]

"""Tests for the views of writing a status update by hand.

With no pending draft the status-updates modal offers New update as its only
button, and with one it offers Review only: AI drafting lives inside the form,
never on the overview. The builders are pure and called directly. The scribe catalogue is not loaded in unit tests, so
wording is the in-code EN or FR fallback, pinned literally; the catalogue test
reads both YAML files and requires the same strings, so the fallbacks and the
catalogue cannot drift apart.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

import packages.incident.scribe as scribe_pkg
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.domain import StatusUpdateOverview
from packages.incident.scribe.entrypoints.slack_views import (
    NEW_ACTION_ID,
    REVIEW_ACTION_ID,
    build_overview_view,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": "C123", "locale": "en-US"})
_LOCALES_DIR = Path(scribe_pkg.__file__).parent / "locales"

_EN_STRINGS = {"new_update_button": "New update"}
_FR_STRINGS = {"new_update_button": "Nouvelle mise à jour"}


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
)


def _button_ids(view: dict[str, Any]) -> list[str]:
    (actions,) = [block for block in view["blocks"] if block.get("block_id") == "overview_actions"]
    return [element["action_id"] for element in actions["elements"]]


class TestNewUpdateButton:
    def test_with_no_pending_draft_new_update_is_the_only_primary_button(self) -> None:
        """With nothing pending the responder starts by writing; there is no Draft button beside it."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=()), "en-US", _METADATA)

        (actions,) = [block for block in view["blocks"] if block.get("block_id") == "overview_actions"]
        assert [(element["action_id"], element.get("style")) for element in actions["elements"]] == [
            (NEW_ACTION_ID, "primary"),
        ]

    def test_with_a_pending_draft_only_review_is_offered(self) -> None:
        """A pending draft is reviewed, not restarted or redrafted from the overview."""
        view = build_overview_view(StatusUpdateOverview(pending=_DRAFT, approved=()), "en-US", _METADATA)

        assert _button_ids(view) == [REVIEW_ACTION_ID]

    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    def test_the_button_is_labelled_in_the_responder_locale(self, locale: str, strings: dict[str, str]) -> None:
        """The label follows the modal's locale."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=()), locale, _METADATA)

        (actions,) = [block for block in view["blocks"] if block.get("block_id") == "overview_actions"]
        assert actions["elements"][0]["text"] == {"type": "plain_text", "text": strings["new_update_button"]}

    def test_action_id_carries_the_plugin_prefix(self) -> None:
        """The button's action id is the scribe's stable, plugin-prefixed id."""
        assert NEW_ACTION_ID == "incident.scribe.status_update.new"


class TestCatalogue:
    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    def test_catalogue_holds_the_manual_strings(self, locale: str, strings: dict[str, str]) -> None:
        """Each string is in the catalogue with exactly the wording the in-code fallback renders."""
        data = yaml.safe_load((_LOCALES_DIR / f"incident_status_update.{locale}.yml").read_text(encoding="utf-8"))
        catalogue: dict[str, str] = data["incident_status_update"]

        assert {key: catalogue.get(key) for key in strings} == strings

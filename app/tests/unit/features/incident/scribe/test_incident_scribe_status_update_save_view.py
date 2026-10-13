"""Tests for the review form's Save draft button and its notices.

``build_review_view`` ends with an actions block holding Save draft, a block
action, so Approve stays the form's only submit. ``save_notice`` words the
notice shown after a save or a failed save. The builders are pure and called
directly. The scribe catalogues are loaded by the directory's conftest, so
wording is the catalogue's EN or FR string, pinned literally; the catalogue
test reads both YAML files and requires the same strings.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

import features.incident.scribe as scribe_pkg
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from features.incident.scribe.entrypoints.slack_views import (
    REVIEW_CALLBACK_ID,
    SAVE_ACTION_ID,
    build_review_view,
    save_notice,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": "C123", "locale": "en-US", "incident_id": "inc-uuid-1", "sequence": 2})
_LOCALES_DIR = Path(scribe_pkg.__file__).parent / "locales"

_EN_STRINGS = {
    "save_button": "Save draft",
    "saved_note": "Draft saved.",
    "save_failed": "The draft could not be saved; your text is still here.",
}
_FR_STRINGS = {
    "save_button": "Enregistrer le brouillon",
    "saved_note": "Brouillon enregistré.",
    "save_failed": "Le brouillon n'a pas pu être enregistré; votre texte est toujours là.",
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
)


class TestSaveButton:
    @pytest.mark.parametrize("with_ai", [True, False], ids=["with-ai", "without-ai"])
    def test_the_form_ends_with_save_draft(self, with_ai: bool) -> None:
        """Every form, with or without the AI section, ends with the Save draft actions block after the French fields."""
        view = build_review_view(_DRAFT, "en-US", _METADATA, with_ai=with_ai)

        assert view["blocks"][-2]["block_id"] == "fr.workaround"
        assert view["blocks"][-1] == {
            "type": "actions",
            "block_id": "save_button",
            "elements": [{"type": "button", "action_id": SAVE_ACTION_ID, "text": {"type": "plain_text", "text": "Save draft"}}],
        }

    def test_approve_stays_the_only_submit(self) -> None:
        """Saving is a block action, so the form's submit is still Approve under the approval callback."""
        view = build_review_view(_DRAFT, "en-US", _METADATA)

        assert (view["callback_id"], view["submit"]) == (REVIEW_CALLBACK_ID, {"type": "plain_text", "text": "Approve"})

    def test_the_button_is_labelled_in_french(self) -> None:
        """A French form labels the button in French."""
        view = build_review_view(_DRAFT, "fr-FR", _METADATA)

        assert view["blocks"][-1]["elements"][0]["text"] == {"type": "plain_text", "text": _FR_STRINGS["save_button"]}

    def test_action_id_carries_the_plugin_prefix(self) -> None:
        """The button's action id is the scribe's stable, plugin-prefixed id."""
        assert SAVE_ACTION_ID == "incident.scribe.status_update.save"


class TestSaveNotice:
    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    @pytest.mark.parametrize("key", ["saved_note", "save_failed"])
    def test_notices_are_localized(self, locale: str, strings: dict[str, str], key: str) -> None:
        """Each notice follows the modal's locale."""
        assert save_notice(key, locale) == strings[key]

    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    def test_catalogue_holds_the_save_strings(self, locale: str, strings: dict[str, str]) -> None:
        """Each string is in the catalogue with exactly the wording ``save_notice`` renders."""
        data = yaml.safe_load((_LOCALES_DIR / f"incident_status_update.{locale}.yml").read_text(encoding="utf-8"))
        catalogue: dict[str, str] = data["incident_status_update"]

        assert {key: catalogue.get(key) for key in strings} == strings

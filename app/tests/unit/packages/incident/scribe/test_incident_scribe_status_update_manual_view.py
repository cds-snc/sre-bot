"""Tests for the views of writing a status update by hand.

With no pending draft the status-updates modal offers New update as its
primary button beside Draft, the review form can leave out its Redraft section, and ``manual_fallback_notice`` explains why
the responder is writing the update when AI drafting failed. The builders are
pure and called directly. The scribe catalogue is not loaded in unit tests, so
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
from packages.incident.scribe.domain import StatusUpdateDraftOutcome, StatusUpdateOutcomeKind, StatusUpdateOverview
from packages.incident.scribe.entrypoints.slack_views import (
    DRAFT_ACTION_ID,
    NEW_ACTION_ID,
    REVIEW_ACTION_ID,
    build_overview_view,
    build_result_view,
    build_review_view,
    manual_fallback_notice,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": "C123", "locale": "en-US"})
_LOCALES_DIR = Path(scribe_pkg.__file__).parent / "locales"

_EN_STRINGS = {
    "new_update_button": "New update",
    "manual_fallback": "AI drafting isn't available right now. Write the update in the fields below, then press Approve.",
}
_FR_STRINGS = {
    "new_update_button": "Nouvelle mise à jour",
    "manual_fallback": "La rédaction par IA n'est pas disponible pour le moment. Rédigez la mise à jour dans les champs "
    "ci-dessous, puis appuyez sur Approuver.",
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


def _button_ids(view: dict[str, Any]) -> list[str]:
    (actions,) = [block for block in view["blocks"] if block.get("block_id") == "draft_button"]
    return [element["action_id"] for element in actions["elements"]]


def _block_ids(view: dict[str, Any]) -> list[str | None]:
    return [block.get("block_id") for block in view["blocks"]]


class TestNewUpdateButton:
    def test_with_no_pending_draft_new_update_leads_then_draft(self) -> None:
        """With nothing pending, writing by hand is the primary path and AI drafting is the secondary one."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=()), "en-US", _METADATA)

        (actions,) = [block for block in view["blocks"] if block.get("block_id") == "draft_button"]
        assert [(element["action_id"], element.get("style")) for element in actions["elements"]] == [
            (NEW_ACTION_ID, "primary"),
            (DRAFT_ACTION_ID, None),
        ]

    def test_with_a_pending_draft_draft_and_review_are_offered(self) -> None:
        """A pending draft is reviewed, not restarted, so New update is absent and Draft and Review stay as before."""
        view = build_overview_view(StatusUpdateOverview(pending=_DRAFT, approved=()), "en-US", _METADATA)

        assert _button_ids(view) == [DRAFT_ACTION_ID, REVIEW_ACTION_ID]

    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    def test_the_button_is_labelled_in_the_responder_locale(self, locale: str, strings: dict[str, str]) -> None:
        """The label follows the modal's locale."""
        view = build_overview_view(StatusUpdateOverview(pending=None, approved=()), locale, _METADATA)

        (actions,) = [block for block in view["blocks"] if block.get("block_id") == "draft_button"]
        assert actions["elements"][0]["text"] == {"type": "plain_text", "text": strings["new_update_button"]}

    def test_a_result_view_offers_neither_draft_nor_new_update(self) -> None:
        """After a run the modal leads to Review only, as before."""
        outcome = StatusUpdateDraftOutcome(update=_DRAFT, kind=StatusUpdateOutcomeKind.DRAFTED)

        assert _button_ids(build_result_view(outcome, "en-US", _METADATA)) == [REVIEW_ACTION_ID]

    def test_action_id_carries_the_plugin_prefix(self) -> None:
        """The button's action id is the scribe's stable, plugin-prefixed id."""
        assert NEW_ACTION_ID == "incident.scribe.status_update.new"


class TestReviewWithoutRedraft:
    def test_the_redraft_section_is_left_out(self) -> None:
        """A hand-written update has no AI to redraft it, so the form opens on the notice and the stage select."""
        view = build_review_view(_DRAFT, "en-US", _METADATA, notice="Read me.", with_redraft=False)

        assert view["blocks"][0] == {"type": "section", "text": {"type": "mrkdwn", "text": "Read me."}}
        assert "instructions" not in _block_ids(view) and "redraft_button" not in _block_ids(view)
        assert view["blocks"][1]["block_id"] == "stage"

    def test_the_rest_of_the_form_is_unchanged(self) -> None:
        """Leaving out Redraft removes only its two blocks; fields, submit and callback stay the same."""
        plain = build_review_view(_DRAFT, "en-US", _METADATA)
        view = build_review_view(_DRAFT, "en-US", _METADATA, with_redraft=False)

        assert view["blocks"] == plain["blocks"][2:]
        assert {key: value for key, value in view.items() if key != "blocks"} == {
            key: value for key, value in plain.items() if key != "blocks"
        }


class TestManualFallbackNotice:
    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    def test_the_notice_is_localized(self, locale: str, strings: dict[str, str]) -> None:
        """The notice tells the responder AI drafting failed and what to do instead."""
        assert manual_fallback_notice(locale) == strings["manual_fallback"]

    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    def test_catalogue_holds_the_manual_strings(self, locale: str, strings: dict[str, str]) -> None:
        """Each string is in the catalogue with exactly the wording the in-code fallback renders."""
        data = yaml.safe_load((_LOCALES_DIR / f"incident_status_update.{locale}.yml").read_text(encoding="utf-8"))
        catalogue: dict[str, str] = data["incident_status_update"]

        assert {key: catalogue.get(key) for key in strings} == strings

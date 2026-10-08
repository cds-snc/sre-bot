"""Tests for the published toggle and published line of the reopened copy-ready view.

For a reopened approved or published update, ``build_copy_ready_view`` puts one
toggle button beside the status line, as the status section's accessory. The
button names the state it will set, not the state shown: an approved update
offers Mark as published (``published: true``) and a published one offers Mark
as not published (``published: false``), so a press from a stale view can never
invert a newer state. A published update also shows who marked it published and
when, in ET or HE, directly under the status line. The Back button stays the
last block. ``build_published_error_view`` maps a toggle conflict onto its own
wording and every other code onto the generic modal errors.

The builders are pure and called directly. The scribe catalogue is not loaded
in unit tests, so wording is the in-code EN or FR fallback, pinned literally;
the catalogue test reads both YAML files and requires the same strings, so the
fallbacks and the catalogue cannot drift apart. Blocks are located by block id
and buttons by action id, and every button value is decoded from JSON, because
that is what Slack renders and the listener reads back.
"""

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

import packages.incident.scribe as scribe_pkg
from contracts.operations.codes import ErrorCode
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.domain import CopyReadyText
from packages.incident.scribe.platforms.slack import (
    HISTORY_ACTION_ID,
    PUBLISHED_ACTION_ID,
    build_copy_ready_view,
    build_draft_error_view,
    build_published_error_view,
)

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_SEQUENCE = 2
_PUBLISHER = "U0PUBLISHER"
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_PUBLISHED_AT = datetime(2026, 10, 7, 13, 10, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "en-US"})
_FR_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "fr-FR"})
_COPY = CopyReadyText(en="Stage: Identified\n\nImpact: en impact", fr="Étape : Identifié\n\nIncidence : fr impact")
_LOCALES_DIR = Path(scribe_pkg.__file__).parent / "locales"

_EN_STRINGS = {
    "mark_published": "Mark as published",
    "mark_unpublished": "Mark as not published",
    "published_line.by": "Published by",
    "published_line.at": "at",
    "toggle_conflict": "This update was marked published or not published elsewhere. "
    "Reopen the status updates to see the latest version.",
}
_FR_STRINGS = {
    "mark_published": "Marquer comme publiée",
    "mark_unpublished": "Marquer comme non publiée",
    "published_line.by": "Publiée par",
    "published_line.at": "le",
    "toggle_conflict": "Cette mise à jour a été marquée comme publiée ou non publiée ailleurs. "
    "Rouvrez les mises à jour de statut pour voir la dernière version.",
}


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


_APPROVED = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=_SEQUENCE,
    state=StatusUpdateState.APPROVED,
    stage=StatusUpdateStage.IDENTIFIED,
    en=_text("en"),
    fr=_text("fr"),
    next_update_at=_NOW + timedelta(minutes=30),
    author="U999",
    transcript_cutoff=_NOW,
    transcript_fingerprint="v1:sha256:abc123",
    created_at=_NOW,
    approver="U0APPROVER",
    approved_at=_NOW,
)


def _published(published_by: str | None = _PUBLISHER) -> StatusUpdate:
    """The approved update marked published at 09:10 Toronto time by ``published_by``."""
    return replace(_APPROVED, state=StatusUpdateState.PUBLISHED, published_at=_PUBLISHED_AT, published_by=published_by)


def _block(view: dict[str, Any], block_id: str) -> dict[str, Any]:
    (block,) = [block for block in view["blocks"] if block.get("block_id") == block_id]
    return block


def _decoded_button(button: dict[str, Any]) -> dict[str, Any]:
    return {**button, "value": json.loads(button["value"])}


def _toggle(view: dict[str, Any]) -> dict[str, Any]:
    """The toggle button: the status section's accessory, with its value decoded."""
    return _decoded_button(_block(view, "approved_status")["accessory"])


def _action_ids(view: dict[str, Any]) -> list[str]:
    """Every button action id in the view, from actions blocks and section accessories, in block order."""
    ids: list[str] = []
    for block in view["blocks"]:
        candidates = [*block.get("elements", []), block.get("accessory", {})]
        ids.extend(candidate["action_id"] for candidate in candidates if candidate.get("type") == "button")
    return ids


def _expected_toggle(text: str, *, published: bool) -> dict[str, Any]:
    return {
        "type": "button",
        "action_id": PUBLISHED_ACTION_ID,
        "text": {"type": "plain_text", "text": text},
        "value": {"incident_id": _INCIDENT, "sequence": _SEQUENCE, "published": published},
    }


def _catalogue(locale: str) -> dict[str, str]:
    data = yaml.safe_load((_LOCALES_DIR / f"incident_status_update.{locale}.yml").read_text(encoding="utf-8"))
    entries: dict[str, str] = data["incident_status_update"]
    return entries


class TestToggleButton:
    def test_approved_update_offers_mark_as_published(self) -> None:
        """An approved update's toggle targets the published state and reads Mark as published."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_APPROVED)

        assert _toggle(view) == _expected_toggle("Mark as published", published=True)

    def test_published_update_offers_mark_as_not_published(self) -> None:
        """A published update's toggle targets the approved state and reads Mark as not published."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_published())

        assert _toggle(view) == _expected_toggle("Mark as not published", published=False)

    def test_french_toggle_texts(self) -> None:
        """French invokers see Marquer comme publiée and Marquer comme non publiée, with the same targets."""
        approved_view = build_copy_ready_view(_COPY, "fr-FR", _FR_METADATA, update=_APPROVED)
        published_view = build_copy_ready_view(_COPY, "fr-FR", _FR_METADATA, update=_published())

        assert (_toggle(approved_view), _toggle(published_view)) == (
            _expected_toggle("Marquer comme publiée", published=True),
            _expected_toggle("Marquer comme non publiée", published=False),
        )

    def test_status_line_text_is_unchanged(self) -> None:
        """The status section keeps the list row's wording; the toggle is added beside it."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_APPROVED)

        assert {key: value for key, value in _block(view, "approved_status").items() if key != "accessory"} == {
            "type": "section",
            "block_id": "approved_status",
            "text": {
                "type": "mrkdwn",
                "text": "*Identified* - 2026-10-07 11:00 ET - approved by <@U0APPROVER> - Not published",
            },
        }

    def test_reopened_view_has_exactly_the_toggle_and_back(self) -> None:
        """A reopened update offers one toggle, beside the status line, and Back last."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_APPROVED)

        assert _action_ids(view) == [PUBLISHED_ACTION_ID, HISTORY_ACTION_ID]

    def test_approval_view_has_no_toggle(self) -> None:
        """The view shown right after approval (no update given) has no button at all."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA)

        assert _action_ids(view) == []

    def test_action_id_carries_the_plugin_prefix(self) -> None:
        """The toggle's action id is the scribe's stable, plugin-prefixed id."""
        assert PUBLISHED_ACTION_ID == "incident.scribe.status_update.published"


class TestPublishedLine:
    def test_published_update_shows_who_and_when_in_english(self) -> None:
        """Directly under the status line, a published update names its publisher and the ET time."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_published())

        assert view["blocks"][1] == {
            "type": "section",
            "block_id": "published_status",
            "text": {"type": "mrkdwn", "text": "Published by <@U0PUBLISHER> at 2026-10-07 09:10 ET"},
        }

    def test_published_line_in_french(self) -> None:
        """The French line uses Publiée par, le and the HE suffix."""
        view = build_copy_ready_view(_COPY, "fr-FR", _FR_METADATA, update=_published())

        assert _block(view, "published_status")["text"] == {
            "type": "mrkdwn",
            "text": "Publiée par <@U0PUBLISHER> le 2026-10-07 09:10 HE",
        }

    def test_approved_update_has_no_published_line(self) -> None:
        """An update that is not published shows the status line, the approval text and Back only."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_APPROVED)

        assert [block.get("block_id") for block in view["blocks"]] == [
            "approved_status",
            None,
            None,
            None,
            None,
            None,
            "history_button",
        ]

    def test_published_update_without_a_publisher_has_no_published_line(self) -> None:
        """A published record that names nobody shows no line rather than an empty mention."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_published(published_by=None))

        assert [block.get("block_id") for block in view["blocks"]] == [
            "approved_status",
            None,
            None,
            None,
            None,
            None,
            "history_button",
        ]

    def test_published_view_keeps_the_approval_text_between_the_status_and_back(self) -> None:
        """After the status and published lines come the approval view's blocks unchanged, then Back."""
        view = build_copy_ready_view(_COPY, "en-US", _METADATA, update=_published())

        assert view["blocks"][2:-1] == build_copy_ready_view(_COPY, "en-US", _METADATA)["blocks"]


class TestBackStays:
    @pytest.mark.parametrize(
        ("locale", "metadata", "back"),
        [("en-US", _METADATA, "Back"), ("fr-FR", _FR_METADATA, "Retour")],
    )
    @pytest.mark.parametrize("make_update", [lambda: _APPROVED, _published], ids=["approved", "published"])
    def test_back_is_the_last_block(self, locale: str, metadata: str, back: str, make_update: Callable[[], StatusUpdate]) -> None:
        """Whatever the state, the last block is the Back button alone, valued with the channel id."""
        view = build_copy_ready_view(_COPY, locale, metadata, update=make_update())

        last = view["blocks"][-1]
        assert {**last, "elements": [_decoded_button(element) for element in last["elements"]]} == {
            "type": "actions",
            "block_id": "history_button",
            "elements": [
                {
                    "type": "button",
                    "action_id": HISTORY_ACTION_ID,
                    "text": {"type": "plain_text", "text": back},
                    "value": {"channel_id": _CHANNEL},
                }
            ],
        }


class TestPublishedErrorView:
    @pytest.mark.parametrize(
        ("locale", "metadata", "strings", "title", "close"),
        [
            ("en-US", _METADATA, _EN_STRINGS, "Status updates", "Close"),
            ("fr-FR", _FR_METADATA, _FR_STRINGS, "Mises à jour de statut", "Fermer"),
        ],
    )
    def test_conflict_has_its_own_wording(
        self, locale: str, metadata: str, strings: dict[str, str], title: str, close: str
    ) -> None:
        """A toggle conflict says the published state changed elsewhere; the modal offers Close only."""
        view = build_published_error_view(ErrorCode.STATUS_UPDATE_CONFLICT, locale, metadata)

        assert view == {
            "type": "modal",
            "title": {"type": "plain_text", "text": title},
            "private_metadata": metadata,
            "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": strings["toggle_conflict"]}}],
            "close": {"type": "plain_text", "text": close},
        }

    @pytest.mark.parametrize("error_code", [ErrorCode.STATUS_UPDATE_NOT_APPROVED, ErrorCode.RATE_LIMITED, None])
    def test_other_codes_use_the_generic_modal_error(self, error_code: str | None) -> None:
        """Every other failure shows the same Close-only error view the other modal buttons use."""
        assert build_published_error_view(error_code, "en-US", _METADATA) == build_draft_error_view(
            error_code, "en-US", _METADATA
        )


class TestCatalogue:
    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    def test_catalogue_holds_the_toggle_strings(self, locale: str, strings: dict[str, str]) -> None:
        """Each toggle string is in the catalogue with exactly the wording the in-code fallback renders."""
        catalogue = _catalogue(locale)

        assert {key: catalogue.get(key) for key in strings} == strings

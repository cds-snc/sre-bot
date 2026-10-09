"""Tests for the Redraft section of the review modal, its parsing and the redrafting view.

The review form opens with a Redraft section, below any notice and above the
stage select: an optional multiline instructions input capped at 500
characters, an optional security confirmation checkbox when asked for, and the
Redraft button. ``parse_redraft_form`` reads the instructions and the checkbox
back from a block action's view state. ``build_redrafting_view`` is the
button-less modal shown while the model runs.

The builders are pure and called directly. The scribe catalogue is not loaded
in unit tests, so wording is the in-code EN or FR fallback, pinned literally;
the catalogue test reads both YAML files and requires the same strings, so the
fallbacks and the catalogue cannot drift apart. Blocks are compared whole, by
block id and in order, because that is what Slack renders and what the
listener reads back.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

import packages.incident.scribe as scribe_pkg
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.entrypoints.slack_views import (
    REDRAFT_ACTION_ID,
    REVIEW_CALLBACK_ID,
    build_redrafting_view,
    build_review_view,
    parse_redraft_form,
)

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_SEQUENCE = 3
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "en-US", "incident_id": _INCIDENT, "sequence": _SEQUENCE})
_FR_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "fr-FR", "incident_id": _INCIDENT, "sequence": _SEQUENCE})
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_FIELD_BLOCK_IDS = tuple(f"{language}.{field}" for language in ("en", "fr") for field in _FIELDS)
_LOCALES_DIR = Path(scribe_pkg.__file__).parent / "locales"

_EN_STRINGS = {
    "redraft_label": "Instructions for a new draft",
    "redraft_hint": "Tell the AI what to change, for example: do not name the vendor. Then press Redraft.",
    "redraft_button": "Redraft",
    "redrafting": "Redrafting the status update. This usually takes up to a minute...",
    "redrafted_note": "Redrafted from your instructions. Review the new draft before you approve it.",
    "redraft_blank": "Enter instructions for the new draft, then press Redraft.",
    "redraft_failed": "Couldn't redraft the status update right now, so the previous draft was kept. Please try again shortly.",
    "redraft_unparseable": "I couldn't turn the model's answer into a status update, so the previous draft was kept. "
    "Please try again.",
    "redraft_security": "This incident is, or may be, a security incident. Redrafting sends the incident channel and "
    "comms content to the AI model. To continue, check the box below, then press Redraft.",
    "security_confirm_title": "Security confirmation",
    "security_confirm_label": "I confirm sending this content to the AI model",
}
_FR_STRINGS = {
    "redraft_label": "Instructions pour un nouveau brouillon",
    "redraft_hint": "Indiquez à l'IA ce qu'il faut changer, par exemple : ne pas nommer le fournisseur. "
    "Appuyez ensuite sur Rédiger à nouveau.",
    "redraft_button": "Rédiger à nouveau",
    "redrafting": "Nouvelle rédaction de la mise à jour de statut en cours. Cela prend généralement jusqu'à une minute...",
    "redrafted_note": "Nouveau brouillon rédigé selon vos instructions. Révisez-le avant de l'approuver.",
    "redraft_blank": "Entrez des instructions pour le nouveau brouillon, puis appuyez sur Rédiger à nouveau.",
    "redraft_failed": "Impossible de rédiger à nouveau la mise à jour de statut pour le moment; le brouillon précédent "
    "a été conservé. Veuillez réessayer sous peu.",
    "redraft_unparseable": "Je n'ai pas pu transformer la réponse du modèle en mise à jour de statut; le brouillon "
    "précédent a été conservé. Veuillez réessayer.",
    "redraft_security": "Cet incident est, ou pourrait être, un incident de sécurité. La nouvelle rédaction envoie le "
    "contenu du canal de l'incident et des communications au modèle d'IA. Pour continuer, cochez la case ci-dessous, "
    "puis appuyez sur Rédiger à nouveau.",
    "security_confirm_title": "Confirmation de sécurité",
    "security_confirm_label": "Je confirme l'envoi de ce contenu au modèle d'IA",
}
_STRINGS = {"en-US": _EN_STRINGS, "fr-FR": _FR_STRINGS}


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


_DRAFT = StatusUpdate(
    incident_id=_INCIDENT,
    sequence=_SEQUENCE,
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


def _instructions_block(locale: str, **initial_value: str) -> dict[str, Any]:
    """The instructions input; pass ``initial_value=...`` for a prefilled one."""
    strings = _STRINGS[locale]
    element = {"type": "plain_text_input", "action_id": "text", "multiline": True, "max_length": 500, **initial_value}
    return {
        "type": "input",
        "block_id": "instructions",
        "label": {"type": "plain_text", "text": strings["redraft_label"]},
        "element": element,
        "hint": {"type": "plain_text", "text": strings["redraft_hint"]},
        "optional": True,
    }


def _redraft_button_block(locale: str) -> dict[str, Any]:
    return {
        "type": "actions",
        "block_id": "redraft_button",
        "elements": [
            {
                "type": "button",
                "action_id": REDRAFT_ACTION_ID,
                "text": {"type": "plain_text", "text": _STRINGS[locale]["redraft_button"]},
            }
        ],
    }


def _security_confirm_block(locale: str) -> dict[str, Any]:
    strings = _STRINGS[locale]
    return {
        "type": "input",
        "block_id": "security_confirm",
        "label": {"type": "plain_text", "text": strings["security_confirm_title"]},
        "element": {
            "type": "checkboxes",
            "action_id": "confirm",
            "options": [{"text": {"type": "plain_text", "text": strings["security_confirm_label"]}, "value": "confirmed"}],
        },
        "optional": True,
    }


def _notice(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _form_blocks(view: dict[str, Any]) -> list[dict[str, Any]]:
    """The review form's blocks from the stage select on, which the Redraft section must not change."""
    blocks: list[dict[str, Any]] = view["blocks"]
    block_ids = [block.get("block_id") for block in blocks]
    return blocks[block_ids.index("stage") :]


def _block_ids(view: dict[str, Any]) -> list[str | None]:
    return [block.get("block_id") for block in view["blocks"]]


def _catalogue(locale: str) -> dict[str, str]:
    data = yaml.safe_load((_LOCALES_DIR / f"incident_status_update.{locale}.yml").read_text(encoding="utf-8"))
    entries: dict[str, str] = data["incident_status_update"]
    return entries


def _checkbox(*selected: str) -> dict[str, Any]:
    """The security confirmation checkbox's state with ``selected`` option values."""
    options = [{"text": {"type": "plain_text", "text": "x"}, "value": value} for value in selected]
    return {"security_confirm": {"confirm": {"type": "checkboxes", "selected_options": options}}}


def _redraft_state(instructions: Any, *, extra_values: dict[str, Any] | None = None) -> dict[str, Any]:
    """A review view as a block action carries it, with the instructions input and any ``extra_values`` blocks."""
    values: dict[str, Any] = {
        block_id: {"text": {"type": "plain_text_input", "value": f"edited {block_id}"}} for block_id in _FIELD_BLOCK_IDS
    }
    values["stage"] = {
        "stage": {
            "type": "static_select",
            "selected_option": {"text": {"type": "plain_text", "text": "x"}, "value": "identified"},
        }
    }
    values["instructions"] = {"text": {"type": "plain_text_input", "value": instructions}}
    values |= extra_values or {}
    return {"id": "VREVIEW", "callback_id": REVIEW_CALLBACK_ID, "private_metadata": _METADATA, "state": {"values": values}}


class TestRedraftSection:
    @pytest.mark.parametrize(("locale", "metadata"), [("en-US", _METADATA), ("fr-FR", _FR_METADATA)])
    def test_the_section_opens_the_form_with_the_instructions_input_then_the_button(self, locale: str, metadata: str) -> None:
        """Without a notice the form starts with the optional, capped instructions input and the Redraft button."""
        view = build_review_view(_DRAFT, locale, metadata)

        assert view["blocks"][:2] == [_instructions_block(locale), _redraft_button_block(locale)]
        assert view["blocks"][2]["block_id"] == "stage"

    def test_block_order_without_a_notice(self) -> None:
        """Instructions and Redraft come first, then the stage, the EN header and fields, the FR header and fields."""
        view = build_review_view(_DRAFT, "en-US", _METADATA)

        assert _block_ids(view) == [
            "instructions",
            "redraft_button",
            "stage",
            None,
            "en.affected_service",
            "en.impact",
            "en.current_action",
            "en.workaround",
            None,
            "fr.affected_service",
            "fr.impact",
            "fr.current_action",
            "fr.workaround",
        ]

    def test_a_notice_sits_above_the_redraft_section(self) -> None:
        """A notice is the first block, so the reviewer reads it before the instructions input."""
        view = build_review_view(_DRAFT, "en-US", _METADATA, notice="Something to read first.")

        assert view["blocks"][:3] == [
            _notice("Something to read first."),
            _instructions_block("en-US"),
            _redraft_button_block("en-US"),
        ]

    def test_instructions_are_prefilled_when_given(self) -> None:
        """After a failed redraft the reviewer's instructions come back as the input's initial value."""
        view = build_review_view(_DRAFT, "en-US", _METADATA, instructions="do not name the vendor")

        assert view["blocks"][0] == _instructions_block("en-US", initial_value="do not name the vendor")

    def test_the_security_checkbox_sits_between_the_instructions_and_the_button(self) -> None:
        """When confirmation is asked for, the optional checkbox comes right before the Redraft button."""
        view = build_review_view(
            _DRAFT,
            "fr-FR",
            _FR_METADATA,
            notice=_FR_STRINGS["redraft_security"],
            instructions="ne pas nommer le fournisseur",
            security_confirm=True,
        )

        assert view["blocks"][:4] == [
            _notice(_FR_STRINGS["redraft_security"]),
            _instructions_block("fr-FR", initial_value="ne pas nommer le fournisseur"),
            _security_confirm_block("fr-FR"),
            _redraft_button_block("fr-FR"),
        ]

    def test_no_checkbox_unless_asked_for(self) -> None:
        """The plain review form has no security confirmation block."""
        view = build_review_view(_DRAFT, "en-US", _METADATA)

        assert "security_confirm" not in _block_ids(view)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"notice": "Read me."},
            {"instructions": "say only sign-in is affected"},
            {"notice": "Read me.", "instructions": "x", "security_confirm": True},
        ],
        ids=["notice", "instructions", "security"],
    )
    def test_the_redraft_section_leaves_the_review_form_unchanged(self, kwargs: dict[str, Any]) -> None:
        """From the stage select on, the form is the same whatever the Redraft section shows."""
        plain = build_review_view(_DRAFT, "en-US", _METADATA)
        view = build_review_view(_DRAFT, "en-US", _METADATA, **kwargs)

        assert _form_blocks(view) == _form_blocks(plain)
        assert {key: value for key, value in view.items() if key != "blocks"} == {
            key: value for key, value in plain.items() if key != "blocks"
        }

    def test_the_modal_still_submits_as_the_approval(self) -> None:
        """Approve stays the modal's only submit; Redraft is a block action and never submits the form."""
        view = build_review_view(_DRAFT, "en-US", _METADATA, instructions="x")

        assert (view["callback_id"], view["submit"]) == (REVIEW_CALLBACK_ID, {"type": "plain_text", "text": "Approve"})

    def test_action_id_carries_the_plugin_prefix(self) -> None:
        """The Redraft button's action id is the scribe's stable, plugin-prefixed id."""
        assert REDRAFT_ACTION_ID == "incident.scribe.status_update.redraft"


class TestParseRedraftForm:
    def test_reads_the_instructions_unchecked(self) -> None:
        """The instructions are returned as typed, and no checkbox block means not confirmed."""
        assert parse_redraft_form(_redraft_state("do not name the vendor")) == ("do not name the vendor", False)

    def test_whitespace_is_kept_for_the_blank_check(self) -> None:
        """Parsing does not trim; the listener and the service decide what is blank."""
        assert parse_redraft_form(_redraft_state("  say only sign-in  ")) == ("  say only sign-in  ", False)

    def test_a_cleared_input_reads_as_empty(self) -> None:
        """Slack sends an untouched or cleared optional input as null; it reads as an empty string."""
        assert parse_redraft_form(_redraft_state(None)) == ("", False)

    def test_a_missing_instructions_block_reads_as_empty(self) -> None:
        """A view state without the instructions block reads as empty instructions."""
        view = _redraft_state("x")
        del view["state"]["values"]["instructions"]

        assert parse_redraft_form(view) == ("", False)

    def test_a_checked_box_is_a_confirmation(self) -> None:
        """The confirmed option selected in the checkbox block confirms the security warning."""
        assert parse_redraft_form(_redraft_state("x", extra_values=_checkbox("confirmed"))) == ("x", True)

    def test_an_unchecked_box_is_not_a_confirmation(self) -> None:
        """The checkbox block shown but left unchecked does not confirm."""
        assert parse_redraft_form(_redraft_state("x", extra_values=_checkbox())) == ("x", False)

    def test_an_unknown_option_is_not_a_confirmation(self) -> None:
        """Only the confirmed value counts; any other selected value does not confirm."""
        assert parse_redraft_form(_redraft_state("x", extra_values=_checkbox("something-else"))) == ("x", False)

    def test_a_view_without_state_reads_as_empty_and_unconfirmed(self) -> None:
        """A malformed view never raises."""
        assert parse_redraft_form({}) == ("", False)


class TestRedraftingView:
    @pytest.mark.parametrize(
        ("locale", "metadata", "title"),
        [("en-US", _METADATA, "Status updates"), ("fr-FR", _FR_METADATA, "Mises à jour de statut")],
    )
    def test_is_a_buttonless_modal_with_its_own_wording(self, locale: str, metadata: str, title: str) -> None:
        """While the model runs the modal shows only the redrafting text: no close, no submit, no button."""
        assert build_redrafting_view(locale, metadata) == {
            "type": "modal",
            "title": {"type": "plain_text", "text": title},
            "private_metadata": metadata,
            "blocks": [_notice(_STRINGS[locale]["redrafting"])],
        }


class TestCatalogue:
    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    def test_catalogue_holds_the_redraft_strings(self, locale: str, strings: dict[str, str]) -> None:
        """Each redraft string is in the catalogue with exactly the wording the in-code fallback renders."""
        catalogue = _catalogue(locale)

        assert {key: catalogue.get(key) for key in strings} == strings

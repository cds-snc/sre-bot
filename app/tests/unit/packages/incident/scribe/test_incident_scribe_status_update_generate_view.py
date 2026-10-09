"""Tests for the AI section of the review modal, its parsing, its notices and the generating view.

With ``with_ai=True`` the review form opens with an AI section, below any
notice and above the stage select: an optional multiline instructions input
capped at 500 characters, an optional security confirmation checkbox when asked
for, and the Draft with AI button. With ``with_ai=False`` (text generation not
configured) the section is left out and the rest of the form is unchanged.
``parse_ai_form`` reads the instructions and the checkbox back from a block
action's view state. ``build_generating_view`` is the button-less modal shown
while the model runs, and ``generate_notice`` renders the outcome notices.

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
    GENERATE_ACTION_ID,
    REVIEW_CALLBACK_ID,
    build_generating_view,
    build_review_view,
    generate_notice,
    parse_ai_form,
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
    "generate_label": "Instructions for the AI (optional)",
    "generate_hint": "Leave empty to draft from the conversation, or say what to change, for example: do not name the vendor.",
    "generate_button": "Draft with AI",
    "generating": "Drafting the status update with AI. This usually takes up to a minute...",
    "generated_note": "Drafted with AI. Review the new draft before you approve it.",
    "generate_carried_forward": "Nothing new since the last approved update, so the current action now says there is no "
    "new information.",
    "generate_failed": "Couldn't draft with AI right now, so your text was kept. Please try again shortly.",
    "generate_unparseable": "I couldn't turn the model's answer into a status update, so your text was kept. Please try again.",
    "generate_security": "This incident is, or may be, a security incident. Drafting with AI sends the incident channel "
    "and comms content to the AI model. To continue, check the box below, then press Draft with AI.",
    "generate_unavailable": "AI drafting isn't available right now, so your text was kept. Write the update in the fields below.",
    "generate_empty_history": "There's no conversation from people to draft from yet, so your text was kept.",
    "security_confirm_title": "Security confirmation",
    "security_confirm_label": "I confirm sending this content to the AI model",
}
_FR_STRINGS = {
    "generate_label": "Instructions pour l'IA (facultatif)",
    "generate_hint": "Laissez vide pour rédiger à partir de la conversation, ou indiquez ce qu'il faut changer, "
    "par exemple : ne pas nommer le fournisseur.",
    "generate_button": "Rédiger avec l'IA",
    "generating": "Rédaction de la mise à jour de statut avec l'IA en cours. Cela prend généralement jusqu'à une minute...",
    "generated_note": "Brouillon rédigé avec l'IA. Révisez-le avant de l'approuver.",
    "generate_carried_forward": "Rien de nouveau depuis la dernière mise à jour approuvée; la mesure en cours indique "
    "maintenant qu'il n'y a aucune nouvelle information.",
    "generate_failed": "Impossible de rédiger avec l'IA pour le moment; votre texte a été conservé. Veuillez réessayer sous peu.",
    "generate_unparseable": "Je n'ai pas pu transformer la réponse du modèle en mise à jour de statut; votre texte a été "
    "conservé. Veuillez réessayer.",
    "generate_security": "Cet incident est, ou pourrait être, un incident de sécurité. La rédaction avec l'IA envoie le "
    "contenu du canal de l'incident et des communications au modèle d'IA. Pour continuer, cochez la case ci-dessous, "
    "puis appuyez sur Rédiger avec l'IA.",
    "generate_unavailable": "La rédaction par IA n'est pas disponible pour le moment; votre texte a été conservé. "
    "Rédigez la mise à jour dans les champs ci-dessous.",
    "generate_empty_history": "Il n'y a pas encore de conversation à partir de laquelle rédiger; votre texte a été conservé.",
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
        "label": {"type": "plain_text", "text": strings["generate_label"]},
        "element": element,
        "hint": {"type": "plain_text", "text": strings["generate_hint"]},
        "optional": True,
    }


def _generate_button_block(locale: str) -> dict[str, Any]:
    return {
        "type": "actions",
        "block_id": "generate_button",
        "elements": [
            {
                "type": "button",
                "action_id": GENERATE_ACTION_ID,
                "text": {"type": "plain_text", "text": _STRINGS[locale]["generate_button"]},
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
    """The review form's blocks from the stage select on, which the AI section must not change."""
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


def _ai_state(instructions: Any, *, extra_values: dict[str, Any] | None = None) -> dict[str, Any]:
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


class TestAiSection:
    @pytest.mark.parametrize(("locale", "metadata"), [("en-US", _METADATA), ("fr-FR", _FR_METADATA)])
    def test_the_section_opens_the_form_with_the_instructions_input_then_the_button(self, locale: str, metadata: str) -> None:
        """Without a notice the form starts with the optional, capped instructions input and the Draft with AI button."""
        view = build_review_view(_DRAFT, locale, metadata)

        assert view["blocks"][:2] == [_instructions_block(locale), _generate_button_block(locale)]
        assert view["blocks"][2]["block_id"] == "stage"

    def test_block_order_without_a_notice(self) -> None:
        """Instructions and Draft with AI come first, then the stage, the EN header and fields, the FR header and fields, then Save draft."""
        view = build_review_view(_DRAFT, "en-US", _METADATA)

        assert _block_ids(view) == [
            "instructions",
            "generate_button",
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
            "save_button",
        ]

    def test_a_notice_sits_above_the_ai_section(self) -> None:
        """A notice is the first block, so the reviewer reads it before the instructions input."""
        view = build_review_view(_DRAFT, "en-US", _METADATA, notice="Something to read first.")

        assert view["blocks"][:3] == [
            _notice("Something to read first."),
            _instructions_block("en-US"),
            _generate_button_block("en-US"),
        ]

    def test_instructions_are_prefilled_when_given(self) -> None:
        """After a failed fill the responder's instructions come back as the input's initial value."""
        view = build_review_view(_DRAFT, "en-US", _METADATA, instructions="do not name the vendor")

        assert view["blocks"][0] == _instructions_block("en-US", initial_value="do not name the vendor")

    def test_the_security_checkbox_sits_between_the_instructions_and_the_button(self) -> None:
        """When confirmation is asked for, the optional checkbox comes right before the Draft with AI button."""
        view = build_review_view(
            _DRAFT,
            "fr-FR",
            _FR_METADATA,
            notice=_FR_STRINGS["generate_security"],
            instructions="ne pas nommer le fournisseur",
            security_confirm=True,
        )

        assert view["blocks"][:4] == [
            _notice(_FR_STRINGS["generate_security"]),
            _instructions_block("fr-FR", initial_value="ne pas nommer le fournisseur"),
            _security_confirm_block("fr-FR"),
            _generate_button_block("fr-FR"),
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
    def test_the_ai_section_leaves_the_review_form_unchanged(self, kwargs: dict[str, Any]) -> None:
        """From the stage select on, the form is the same whatever the AI section shows."""
        plain = build_review_view(_DRAFT, "en-US", _METADATA)
        view = build_review_view(_DRAFT, "en-US", _METADATA, **kwargs)

        assert _form_blocks(view) == _form_blocks(plain)
        assert {key: value for key, value in view.items() if key != "blocks"} == {
            key: value for key, value in plain.items() if key != "blocks"
        }

    def test_the_modal_still_submits_as_the_approval(self) -> None:
        """Approve stays the modal's only submit; Draft with AI is a block action and never submits the form."""
        view = build_review_view(_DRAFT, "en-US", _METADATA, instructions="x")

        assert (view["callback_id"], view["submit"]) == (REVIEW_CALLBACK_ID, {"type": "plain_text", "text": "Approve"})

    def test_action_id_carries_the_plugin_prefix(self) -> None:
        """The Draft with AI button's action id is the scribe's stable, plugin-prefixed id."""
        assert GENERATE_ACTION_ID == "incident.scribe.status_update.generate"


class TestWithoutAi:
    @pytest.mark.parametrize(
        "kwargs",
        [{}, {"notice": "Read me."}, {"instructions": "x", "security_confirm": True}],
        ids=["plain", "notice", "after-refusal"],
    )
    def test_without_text_generation_the_form_has_no_ai_section(self, kwargs: dict[str, Any]) -> None:
        """No instructions, checkbox or Draft with AI block; the stage, fields, Save draft and Approve remain unchanged."""
        with_ai = build_review_view(_DRAFT, "en-US", _METADATA, **kwargs)
        view = build_review_view(_DRAFT, "en-US", _METADATA, with_ai=False, **kwargs)

        assert not {"instructions", "security_confirm", "generate_button"} & set(_block_ids(view))
        assert _form_blocks(view) == _form_blocks(with_ai)
        assert (view["callback_id"], view["submit"]) == (REVIEW_CALLBACK_ID, {"type": "plain_text", "text": "Approve"})

    def test_a_notice_still_opens_the_form(self) -> None:
        """A notice is shown above the stage select when there is no AI section."""
        view = build_review_view(_DRAFT, "en-US", _METADATA, notice="Draft saved.", with_ai=False)

        assert view["blocks"][0] == _notice("Draft saved.")
        assert view["blocks"][1]["block_id"] == "stage"


class TestParseAiForm:
    def test_reads_the_instructions_unchecked(self) -> None:
        """The instructions are returned as typed, and no checkbox block means not confirmed."""
        assert parse_ai_form(_ai_state("do not name the vendor")) == ("do not name the vendor", False)

    def test_whitespace_is_kept_for_the_blank_check(self) -> None:
        """Parsing does not trim; the listener and the service decide what is blank."""
        assert parse_ai_form(_ai_state("  say only sign-in  ")) == ("  say only sign-in  ", False)

    def test_a_cleared_input_reads_as_empty(self) -> None:
        """Slack sends an untouched or cleared optional input as null; it reads as an empty string."""
        assert parse_ai_form(_ai_state(None)) == ("", False)

    def test_a_missing_instructions_block_reads_as_empty(self) -> None:
        """A view state without the instructions block (a form without AI) reads as empty instructions."""
        view = _ai_state("x")
        del view["state"]["values"]["instructions"]

        assert parse_ai_form(view) == ("", False)

    def test_a_checked_box_is_a_confirmation(self) -> None:
        """The confirmed option selected in the checkbox block confirms the security warning."""
        assert parse_ai_form(_ai_state("x", extra_values=_checkbox("confirmed"))) == ("x", True)

    def test_an_unchecked_box_is_not_a_confirmation(self) -> None:
        """The checkbox block shown but left unchecked does not confirm."""
        assert parse_ai_form(_ai_state("x", extra_values=_checkbox())) == ("x", False)

    def test_an_unknown_option_is_not_a_confirmation(self) -> None:
        """Only the confirmed value counts; any other selected value does not confirm."""
        assert parse_ai_form(_ai_state("x", extra_values=_checkbox("something-else"))) == ("x", False)

    def test_a_view_without_state_reads_as_empty_and_unconfirmed(self) -> None:
        """A malformed view never raises."""
        assert parse_ai_form({}) == ("", False)


class TestGeneratingView:
    @pytest.mark.parametrize(
        ("locale", "metadata", "title"),
        [("en-US", _METADATA, "Status updates"), ("fr-FR", _FR_METADATA, "Mises à jour de statut")],
    )
    def test_is_a_buttonless_modal_with_its_own_wording(self, locale: str, metadata: str, title: str) -> None:
        """While the model runs the modal shows only the generating text: no close, no submit, no button."""
        assert build_generating_view(locale, metadata) == {
            "type": "modal",
            "title": {"type": "plain_text", "text": title},
            "private_metadata": metadata,
            "blocks": [_notice(_STRINGS[locale]["generating"])],
        }


_NOTICE_KEYS = (
    "generated_note",
    "generate_carried_forward",
    "generate_failed",
    "generate_unparseable",
    "generate_security",
    "generate_unavailable",
    "generate_empty_history",
)


class TestGenerateNotice:
    @pytest.mark.parametrize("key", _NOTICE_KEYS)
    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_each_notice_renders_its_localized_wording(self, key: str, locale: str) -> None:
        """Every outcome of Draft with AI has its own notice in both languages."""
        assert generate_notice(key, locale) == _STRINGS[locale][key]


class TestCatalogue:
    @pytest.mark.parametrize(("locale", "strings"), [("en-US", _EN_STRINGS), ("fr-FR", _FR_STRINGS)])
    def test_catalogue_holds_the_ai_strings(self, locale: str, strings: dict[str, str]) -> None:
        """Each AI string is in the catalogue with exactly the wording the in-code fallback renders."""
        catalogue = _catalogue(locale)

        assert {key: catalogue.get(key) for key in strings} == strings

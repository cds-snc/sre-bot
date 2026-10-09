"""Tests for the review views of the incident status-updates modal.

The Review button sits beside Draft on the pending view and alone on the Draft
result view; its value names the draft's incident and sequence. The review
modal prefills the stage select and the eight EN and FR fields from the draft,
and its submission parses back into a ``StatusUpdateEdit``. The saving, copy-ready
and review error views are what the modal shows after an approval is submitted.
Assertions navigate the view dicts by block id and element type, because those
are what Slack renders and what the submission listener reads back.
"""

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.slack.models import CommandPayload
from packages.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from packages.incident.scribe.domain import (
    CopyReadyText,
    StatusUpdateDraftOutcome,
    StatusUpdateEdit,
    StatusUpdateOutcomeKind,
    StatusUpdateOverview,
)
from packages.incident.scribe.entrypoints import slack as slack_entrypoints
from packages.incident.scribe.entrypoints.slack import handle_status_update_command
from packages.incident.scribe.entrypoints.slack_views import (
    DRAFT_ACTION_ID,
    NEW_ACTION_ID,
    REVIEW_ACTION_ID,
    REVIEW_CALLBACK_ID,
    build_copy_ready_view,
    build_draft_error_view,
    build_drafting_view,
    build_profile_labels,
    build_result_view,
    build_review_error_view,
    build_review_field_errors,
    build_review_view,
    build_saving_view,
    build_security_confirmation_view,
    parse_review_submission,
)
from tests.factories.slack import FakeSlackReply

pytestmark = pytest.mark.unit

_INCIDENT = "inc-uuid-1"
_CHANNEL = "C123"
_SEQUENCE = 3
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
_METADATA = json.dumps({"channel_id": _CHANNEL, "locale": "en-US", "incident_id": _INCIDENT, "sequence": _SEQUENCE})
_FIELDS = ("affected_service", "impact", "current_action", "workaround")
_FIELD_BLOCK_IDS = tuple(f"{language}.{field}" for language in ("en", "fr") for field in _FIELDS)


def _text(language: str) -> StatusUpdateText:
    return StatusUpdateText(
        affected_service=f"{language} service",
        impact=f"{language} impact",
        current_action=f"{language} action",
        workaround=f"{language} workaround",
    )


def _draft(stage: StatusUpdateStage = StatusUpdateStage.IDENTIFIED) -> StatusUpdate:
    return StatusUpdate(
        incident_id=_INCIDENT,
        sequence=_SEQUENCE,
        state=StatusUpdateState.DRAFT,
        stage=stage,
        en=_text("en"),
        fr=_text("fr"),
        next_update_at=_NOW,
        author="U999",
        transcript_cutoff=_NOW,
        transcript_fingerprint="v1:sha256:abc123",
        created_at=_NOW,
    )


def _button_action_ids(view: dict[str, Any]) -> list[str]:
    """Action ids of every button in the view's actions blocks, in order."""
    return [
        element["action_id"]
        for block in view["blocks"]
        if block["type"] == "actions"
        for element in block["elements"]
        if element["type"] == "button"
    ]


def _button(view: dict[str, Any], action_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = [
        element
        for block in view["blocks"]
        if block["type"] == "actions"
        for element in block["elements"]
        if element.get("action_id") == action_id
    ]
    (button,) = matches
    return button


def _block(view: dict[str, Any], block_id: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = [block for block in view["blocks"] if block.get("block_id") == block_id]
    (block,) = matches
    return block


def _section_text(view: dict[str, Any]) -> str:
    """The mrkdwn text of the view's section blocks, joined in order."""
    return "".join(block["text"]["text"] for block in view["blocks"] if block["type"] == "section")


def _pending_view(monkeypatch: pytest.MonkeyPatch, overview: OperationResult[StatusUpdateOverview]) -> dict[str, Any]:
    """Run the status-update command with the overview read stubbed and return the final modal view."""
    monkeypatch.setattr(slack_entrypoints, "get_status_update_overview", lambda channel_id: overview)
    reply = FakeSlackReply()
    payload = CommandPayload(
        text="", user_id="U9", channel_id=_CHANNEL, user_locale="en-US", platform_metadata={"trigger_id": "T1"}
    )
    handle_status_update_command(payload, {}, reply)
    view: dict[str, Any] = reply.calls_to("update_view")[-1]["view"]
    return view


def _submitted_view(
    *,
    stage: dict[str, Any] | None,
    values: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """A submitted review view's ``state.values``; ``stage`` is the select's state or None to omit the block."""
    texts = {block_id: f"edited {block_id}" for block_id in _FIELD_BLOCK_IDS} | (values or {})
    state: dict[str, Any] = {
        block_id: {"text": {"type": "plain_text_input", "value": value}} for block_id, value in texts.items()
    }
    if stage is not None:
        state["stage"] = {"stage": stage}
    return {
        "id": "VREVIEW",
        "callback_id": REVIEW_CALLBACK_ID,
        "private_metadata": _METADATA,
        "state": {"values": state},
    }


def _selected(value: str | None) -> dict[str, Any]:
    option = None if value is None else {"text": {"type": "plain_text", "text": value}, "value": value}
    return {"type": "static_select", "selected_option": option}


class TestReviewButton:
    def test_pending_view_shows_draft_then_review(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The pending view's buttons are Draft then Review, so a draft can be reviewed without redrafting."""
        view = _pending_view(monkeypatch, OperationResult.success(data=StatusUpdateOverview(pending=_draft(), approved=())))

        assert _button_action_ids(view) == [DRAFT_ACTION_ID, REVIEW_ACTION_ID]

    def test_pending_view_review_value_names_the_draft(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The Review button's value is JSON naming the shown draft's incident id and sequence."""
        view = _pending_view(monkeypatch, OperationResult.success(data=StatusUpdateOverview(pending=_draft(), approved=())))

        button = _button(view, REVIEW_ACTION_ID)
        assert json.loads(button["value"]) == {"incident_id": _INCIDENT, "sequence": _SEQUENCE}

    def test_review_button_label(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The Review button is a plain-text button labelled Review in English."""
        view = _pending_view(monkeypatch, OperationResult.success(data=StatusUpdateOverview(pending=_draft(), approved=())))

        button = _button(view, REVIEW_ACTION_ID)
        assert button["type"] == "button"
        assert button["text"] == {"type": "plain_text", "text": "Review"}

    def test_no_pending_view_has_draft_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no draft there is nothing to review, so only New update and Draft are offered."""
        view = _pending_view(monkeypatch, OperationResult.success(data=StatusUpdateOverview(pending=None, approved=())))

        assert _button_action_ids(view) == [NEW_ACTION_ID, DRAFT_ACTION_ID]

    def test_lookup_error_view_has_no_buttons(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failed lookup shows the error with no Draft or Review button."""
        view = _pending_view(monkeypatch, OperationResult.permanent_error(message="x", error_code=ErrorCode.NOT_AN_INCIDENT))

        assert _button_action_ids(view) == []

    @pytest.mark.parametrize(
        "kind",
        [StatusUpdateOutcomeKind.DRAFTED, StatusUpdateOutcomeKind.CARRIED_FORWARD, StatusUpdateOutcomeKind.PENDING],
    )
    def test_result_view_has_review_only(self, kind: StatusUpdateOutcomeKind) -> None:
        """After drafting, the result view offers Review alone, valued with the drafted record."""
        view = build_result_view(StatusUpdateDraftOutcome(update=_draft(), kind=kind), "en-US", _METADATA)

        assert _button_action_ids(view) == [REVIEW_ACTION_ID]
        assert json.loads(_button(view, REVIEW_ACTION_ID)["value"]) == {"incident_id": _INCIDENT, "sequence": _SEQUENCE}

    @pytest.mark.parametrize(
        "view",
        [
            build_draft_error_view(ErrorCode.EMPTY_HISTORY, "en-US", _METADATA),
            build_security_confirmation_view("en-US", _METADATA),
            build_drafting_view("en-US", _METADATA),
        ],
        ids=["error", "confirmation", "drafting"],
    )
    def test_views_without_a_shown_draft_have_no_review(self, view: dict[str, Any]) -> None:
        """Error, confirmation and drafting views show no draft, so none carries a Review button."""
        assert REVIEW_ACTION_ID not in _button_action_ids(view)


class TestReviewView:
    def test_is_the_approval_modal(self) -> None:
        """The review view is a modal whose submission routes to the approval listener."""
        view = build_review_view(_draft(), "en-US", _METADATA)

        assert view["type"] == "modal"
        assert view["callback_id"] == REVIEW_CALLBACK_ID

    def test_private_metadata_is_passed_through(self) -> None:
        """The given private metadata is carried verbatim so the submission knows the draft and locale."""
        view = build_review_view(_draft(), "en-US", _METADATA)

        assert view["private_metadata"] == _METADATA

    @pytest.mark.parametrize(
        ("locale", "submit", "close"),
        [("en-US", "Approve", "Cancel"), ("fr-FR", "Approuver", "Annuler")],
    )
    def test_submit_and_close_are_localized(self, locale: str, submit: str, close: str) -> None:
        """Submit reads Approve and close reads Cancel, in the invoker's locale."""
        view = build_review_view(_draft(), locale, _METADATA)

        assert view["submit"] == {"type": "plain_text", "text": submit}
        assert view["close"] == {"type": "plain_text", "text": close}

    def test_input_block_ids_in_order(self) -> None:
        """Inputs are the redraft instructions, the stage, then the four EN and the four FR fields, keyed by validation field name."""
        view = build_review_view(_draft(), "en-US", _METADATA)

        input_ids = [block["block_id"] for block in view["blocks"] if block["type"] == "input"]
        assert input_ids == ["instructions", "stage", *_FIELD_BLOCK_IDS]

    def test_language_headers_precede_their_fields(self) -> None:
        """A header block sits right before the first EN field and right before the first FR field."""
        view = build_review_view(_draft(), "en-US", _METADATA)

        block_ids = [block.get("block_id") for block in view["blocks"]]
        for first in ("en.affected_service", "fr.affected_service"):
            assert view["blocks"][block_ids.index(first) - 1]["type"] == "header"

    @pytest.mark.parametrize("locale", ["en-US", "fr-FR"])
    def test_stage_select_offers_all_four_stages(self, locale: str) -> None:
        """The stage select offers every stage in forward order, named in the invoker's locale."""
        view = build_review_view(_draft(), locale, _METADATA)

        element = _block(view, "stage")["element"]
        assert element["type"] == "static_select"
        assert element["action_id"] == "stage"
        assert [option["value"] for option in element["options"]] == [
            "investigating",
            "identified",
            "monitoring",
            "resolved",
        ]
        names = build_profile_labels(locale).stage_names
        assert [option["text"] for option in element["options"]] == [
            {"type": "plain_text", "text": names[stage]} for stage in StatusUpdateStage
        ]

    @pytest.mark.parametrize("stage", list(StatusUpdateStage))
    def test_stage_select_starts_on_the_draft_stage(self, stage: StatusUpdateStage) -> None:
        """The initial option is the draft's stage and equals one of the offered options, as Slack requires."""
        view = build_review_view(_draft(stage), "en-US", _METADATA)

        element = _block(view, "stage")["element"]
        assert element["initial_option"]["value"] == stage.value
        assert element["initial_option"] in element["options"]

    @pytest.mark.parametrize("block_id", _FIELD_BLOCK_IDS)
    def test_field_inputs_are_optional_multiline_and_prefilled(self, block_id: str) -> None:
        """Each field is an optional multiline text input prefilled from the draft.

        Optional so Slack never blocks a blank field itself; blank handling stays
        with the submission listener's validation.
        """
        language, field = block_id.split(".")
        expected = getattr(_draft().en if language == "en" else _draft().fr, field)
        view = build_review_view(_draft(), "en-US", _METADATA)

        block = _block(view, block_id)
        assert block["optional"] is True
        assert block["element"]["type"] == "plain_text_input"
        assert block["element"]["action_id"] == "text"
        assert block["element"]["multiline"] is True
        assert block["element"]["initial_value"] == expected

    @pytest.mark.parametrize("block_id", _FIELD_BLOCK_IDS)
    def test_field_labels_come_from_the_language_profile(self, block_id: str) -> None:
        """EN fields use the English profile labels and FR fields the French ones, whatever the invoker's locale."""
        language, field = block_id.split(".")
        labels = build_profile_labels("en-US" if language == "en" else "fr-FR")
        view = build_review_view(_draft(), "en-US", _METADATA)

        assert _block(view, block_id)["label"] == {"type": "plain_text", "text": getattr(labels, field)}


class TestParseReviewSubmission:
    def test_parses_stage_and_both_languages(self) -> None:
        """A complete submission becomes the edit with the selected stage and every field's text."""
        edit = parse_review_submission(_submitted_view(stage=_selected("monitoring")))

        assert edit == StatusUpdateEdit(
            stage=StatusUpdateStage.MONITORING,
            en=StatusUpdateText(
                affected_service="edited en.affected_service",
                impact="edited en.impact",
                current_action="edited en.current_action",
                workaround="edited en.workaround",
            ),
            fr=StatusUpdateText(
                affected_service="edited fr.affected_service",
                impact="edited fr.impact",
                current_action="edited fr.current_action",
                workaround="edited fr.workaround",
            ),
        )

    @pytest.mark.parametrize("block_id", _FIELD_BLOCK_IDS)
    def test_cleared_field_parses_as_empty_text(self, block_id: str) -> None:
        """Slack sends a cleared optional input as null; it parses as "" so validation can name it."""
        edit = parse_review_submission(_submitted_view(stage=_selected("identified"), values={block_id: None}))

        assert edit is not None
        language, field = block_id.split(".")
        assert getattr(edit.en if language == "en" else edit.fr, field) == ""

    def test_whitespace_is_kept_for_validation(self) -> None:
        """Parsing does not trim; whitespace-only text reaches the validator unchanged."""
        edit = parse_review_submission(_submitted_view(stage=_selected("identified"), values={"fr.impact": "   "}))

        assert edit is not None
        assert edit.fr.impact == "   "

    def test_no_selected_stage_is_unparseable(self) -> None:
        """A stage select with no selected option yields None."""
        assert parse_review_submission(_submitted_view(stage=_selected(None))) is None

    def test_missing_stage_block_is_unparseable(self) -> None:
        """A submission without the stage block yields None."""
        assert parse_review_submission(_submitted_view(stage=None)) is None

    def test_unknown_stage_value_is_unparseable(self) -> None:
        """A stage value outside the four stages yields None rather than raising."""
        assert parse_review_submission(_submitted_view(stage=_selected("not-a-stage"))) is None


class TestReviewFieldErrors:
    def test_maps_exactly_the_named_fields(self) -> None:
        """Errors are keyed by exactly the given block ids, so Slack marks only those inputs."""
        errors = build_review_field_errors(("en.impact", "fr.workaround"), "en-US")

        assert set(errors) == {"en.impact", "fr.workaround"}

    def test_every_field_gets_the_same_non_empty_message(self) -> None:
        """Each named field carries the one non-empty blank-field message."""
        errors = build_review_field_errors(_FIELD_BLOCK_IDS, "en-US")

        assert len(set(errors.values())) == 1
        assert next(iter(errors.values())).strip() != ""

    def test_message_is_localized(self) -> None:
        """The French message differs from the English one."""
        en = build_review_field_errors(("en.impact",), "en-US")["en.impact"]
        fr = build_review_field_errors(("en.impact",), "fr-FR")["en.impact"]

        assert fr != en

    def test_no_fields_no_errors(self) -> None:
        """An empty name list maps to an empty errors dict."""
        assert build_review_field_errors((), "en-US") == {}


class TestSavingView:
    def test_is_a_modal_without_submit_or_buttons(self) -> None:
        """The saving view cannot be submitted again and offers no button while approval runs."""
        view = build_saving_view("en-US", _METADATA)

        assert view["type"] == "modal"
        assert "submit" not in view
        assert _button_action_ids(view) == []
        assert _section_text(view).strip() != ""

    def test_private_metadata_is_passed_through(self) -> None:
        """The saving view keeps the review's private metadata."""
        assert build_saving_view("en-US", _METADATA)["private_metadata"] == _METADATA


class TestCopyReadyView:
    _COPY = CopyReadyText(
        en="Stage: Monitoring\n\nImpact: Logins *fail* for `some` users",
        fr="Étape : Surveillance\n\nIncidence : Les connexions échouent",
    )

    def _rich_text_blocks(self) -> list[dict[str, Any]]:
        view = build_copy_ready_view(self._COPY, "en-US", _METADATA)
        return [block for block in view["blocks"] if block["type"] == "rich_text"]

    def test_one_preformatted_block_per_language_with_the_exact_text(self) -> None:
        """EN then FR each get one rich_text block holding one preformatted element with the text verbatim."""
        blocks = self._rich_text_blocks()

        assert [block["elements"] for block in blocks] == [
            [{"type": "rich_text_preformatted", "elements": [{"type": "text", "text": self._COPY.en}]}],
            [{"type": "rich_text_preformatted", "elements": [{"type": "text", "text": self._COPY.fr}]}],
        ]

    def test_each_language_is_under_a_header(self) -> None:
        """The block right before each preformatted block is a header."""
        view = build_copy_ready_view(self._COPY, "en-US", _METADATA)

        indexes = [index for index, block in enumerate(view["blocks"]) if block["type"] == "rich_text"]
        assert len(indexes) == 2
        assert [view["blocks"][index - 1]["type"] for index in indexes] == ["header", "header"]

    def test_close_only(self) -> None:
        """The copy-ready view has a Close button and no submit or other button."""
        view = build_copy_ready_view(self._COPY, "en-US", _METADATA)

        assert view["type"] == "modal"
        assert view["close"] == {"type": "plain_text", "text": "Close"}
        assert "submit" not in view
        assert _button_action_ids(view) == []

    def test_private_metadata_is_passed_through(self) -> None:
        """The copy-ready view keeps the review's private metadata."""
        assert build_copy_ready_view(self._COPY, "en-US", _METADATA)["private_metadata"] == _METADATA


class TestReviewErrorView:
    def _text(self, error_code: str | None, locale: str = "en-US") -> str:
        return _section_text(build_review_error_view(error_code, locale, _METADATA))

    @pytest.mark.parametrize(
        "error_code",
        [ErrorCode.STATUS_UPDATE_STAGE_BELOW_FLOOR, ErrorCode.STATUS_UPDATE_CONFLICT],
    )
    def test_specific_refusals_differ_from_the_generic_error(self, error_code: ErrorCode) -> None:
        """Stage-below-floor and review conflict each have their own message, not the generic one."""
        assert self._text(error_code) != self._text(ErrorCode.RATE_LIMITED)

    def test_stage_below_floor_differs_from_conflict(self) -> None:
        """The two review refusals are told apart."""
        assert self._text(ErrorCode.STATUS_UPDATE_STAGE_BELOW_FLOOR) != self._text(ErrorCode.STATUS_UPDATE_CONFLICT)

    def test_review_conflict_differs_from_the_draft_conflict(self) -> None:
        """A review conflict means the draft changed or was approved elsewhere, unlike a drafting conflict."""
        draft_conflict = _section_text(build_draft_error_view(ErrorCode.STATUS_UPDATE_CONFLICT, "en-US", _METADATA))

        assert self._text(ErrorCode.STATUS_UPDATE_CONFLICT) != draft_conflict

    @pytest.mark.parametrize(
        "error_code",
        [ErrorCode.STATUS_UPDATE_STAGE_BELOW_FLOOR, ErrorCode.STATUS_UPDATE_CONFLICT],
    )
    def test_messages_exist_in_english_and_french(self, error_code: ErrorCode) -> None:
        """Each message is non-empty in both locales and the French differs from the English."""
        en = self._text(error_code, "en-US")
        fr = self._text(error_code, "fr-FR")

        assert en.strip() != ""
        assert fr.strip() != ""
        assert fr != en

    def test_close_only(self) -> None:
        """The error view can only be closed: Close, no submit, no buttons."""
        view = build_review_error_view(ErrorCode.STATUS_UPDATE_CONFLICT, "en-US", _METADATA)

        assert view["type"] == "modal"
        assert view["close"] == {"type": "plain_text", "text": "Close"}
        assert "submit" not in view
        assert _button_action_ids(view) == []

"""Tests for the status-update prompt: the transcript it sends and the strict parsing of the model's answer."""

import json
from typing import Any

import pytest

from packages.incident.core.api import StatusUpdateStage, StatusUpdateText, TranscriptMessage
from packages.incident.scribe.domain import DraftedFields
from packages.incident.scribe.status_update_prompt import (
    INSTRUCTIONS,
    MAX_FIELD_CHARS,
    build_transcript,
    parse_drafted_fields,
)

pytestmark = pytest.mark.unit

_FIELDS = ("affected_service", "impact", "current_action", "workaround")


def _answer(**overrides: Any) -> dict[str, Any]:
    """Return a complete, valid model answer with ``overrides`` applied."""
    answer: dict[str, Any] = {"stage": "identified"}
    for language in ("en", "fr"):
        for field in _FIELDS:
            answer[f"{language}_{field}"] = f"{language} {field}"
    answer.update(overrides)
    return answer


def _expected() -> DraftedFields:
    return DraftedFields(
        stage=StatusUpdateStage.IDENTIFIED,
        en=StatusUpdateText(**{field: f"en {field}" for field in _FIELDS}),
        fr=StatusUpdateText(**{field: f"fr {field}" for field in _FIELDS}),
    )


class TestParseDraftedFields:
    def test_a_complete_answer_gives_the_stage_and_both_languages(self) -> None:
        """Every key maps onto the stage and the four fields of each language."""
        assert parse_drafted_fields(json.dumps(_answer())) == _expected()

    def test_a_fenced_answer_with_surrounding_prose_is_read(self) -> None:
        """Models often wrap JSON in a code fence and a sentence; the first object is what counts."""
        raw = f"Here is the update:\n```json\n{json.dumps(_answer())}\n```\nLet me know."

        assert parse_drafted_fields(raw) == _expected()

    def test_fields_are_trimmed(self) -> None:
        """Surrounding whitespace never reaches the stored text."""
        result = parse_drafted_fields(json.dumps(_answer(en_impact="  slow sign-in  ")))

        assert result is not None
        assert result.en.impact == "slow sign-in"

    def test_an_overlong_field_is_capped(self) -> None:
        """A runaway field is cut to the cap rather than stored whole."""
        result = parse_drafted_fields(json.dumps(_answer(fr_impact="x" * (MAX_FIELD_CHARS + 50))))

        assert result is not None
        assert len(result.fr.impact) == MAX_FIELD_CHARS

    @pytest.mark.parametrize(
        "answer",
        [
            _answer(stage="degraded"),
            _answer(stage=None),
            {key: value for key, value in _answer().items() if key != "fr_workaround"},
            _answer(en_current_action="   "),
            _answer(en_impact=42),
            _answer(fr_affected_service=["a", "b"]),
        ],
        ids=["unknown-stage", "null-stage", "missing-key", "blank-field", "number-field", "list-field"],
    )
    def test_an_incomplete_or_malformed_answer_gives_nothing(self, answer: dict[str, Any]) -> None:
        """A public update is never assembled from a partial answer: any bad field rejects the whole draft."""
        assert parse_drafted_fields(json.dumps(answer)) is None

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "no json here",
            json.dumps(_answer())[:-20],
            "[1, 2, 3]",
        ],
        ids=["empty", "prose", "truncated", "not-an-object"],
    )
    def test_unreadable_output_gives_nothing_and_is_never_salvaged(self, raw: str) -> None:
        """A cut-off or non-object answer is rejected outright, unlike the report drafter's salvage."""
        assert parse_drafted_fields(raw) is None


class TestPrompt:
    def test_the_transcript_is_one_author_and_text_line_per_message_in_order(self) -> None:
        """The model reads the conversation as ``author: text`` lines, oldest first."""
        messages = [
            TranscriptMessage(author="Alertmanager", text="ALARM: 5xx", is_bot=True),
            TranscriptMessage(author="Ada", text="rolling back"),
        ]

        assert build_transcript(messages) == "Alertmanager: ALARM: 5xx\nAda: rolling back"

    def test_the_instructions_name_every_key_and_every_stage(self) -> None:
        """The model is told the exact flat keys and the only stage values the parser accepts."""
        for key in _answer():
            assert key in INSTRUCTIONS
        for stage in StatusUpdateStage:
            assert stage.value in INSTRUCTIONS

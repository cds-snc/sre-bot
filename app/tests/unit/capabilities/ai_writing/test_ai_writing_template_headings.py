"""Tests for pairing a model's answer keys with the requested sections and fields.

Pure functions over literal answer maps. Assertions are on the answer text each requested key
receives and on the logged match shape.
"""

import pytest

from capabilities.ai_writing.domain import (
    TemplateAnswer,
    TemplateField,
    TemplateSection,
    describe_match,
    fill,
    match_answer,
    normalize_heading,
)

pytestmark = pytest.mark.unit


def test_an_exact_key_wins() -> None:
    assert match_answer("Trigger", {"Trigger": " A bad deploy. ", "trigger": "other"}) == "A bad deploy."


@pytest.mark.parametrize("key", ["1. Trigger", "TRIGGER", "Trigger:", "2) trigger!"])
def test_a_drifted_key_matches_its_heading(key: str) -> None:
    assert match_answer("Trigger", {key: "A bad deploy."}) == "A bad deploy."


def test_a_blank_answer_reads_as_unanswered() -> None:
    assert match_answer("Trigger", {"Trigger": "   "}) == ""


def test_when_two_keys_normalise_alike_the_later_wins() -> None:
    assert match_answer("Impact", {"1. Impact": "first", "impact": "second"}) == "second"


def test_normalising_drops_numbering_case_and_punctuation() -> None:
    assert normalize_heading(" 3 - What  Happened? ") == "what happened"


def test_fill_answers_every_requested_key_in_order() -> None:
    answers = {"impact": "Checkout down.", "Trigger": "A deploy.", "On-call": "Ada"}

    filled = fill(
        answers,
        [TemplateSection("Trigger"), TemplateSection("Impact"), TemplateSection("Detection")],
        [TemplateField("On-call"), TemplateField("Detection time")],
        truncated=False,
    )

    assert filled.sections == (
        TemplateAnswer("Trigger", "A deploy."),
        TemplateAnswer("Impact", "Checkout down."),
        TemplateAnswer("Detection", ""),
    )
    assert filled.fields == (TemplateAnswer("On-call", "Ada"), TemplateAnswer("Detection time", ""))
    assert filled.truncated is False


def test_the_match_shape_counts_keys_and_names_blank_sections() -> None:
    answers = {"Trigger": "A deploy.", "On-call": "Ada", "Stray": "x", "Impact": " "}
    filled = fill(answers, [TemplateSection("Trigger"), TemplateSection("Impact")], [TemplateField("On-call")], truncated=False)

    match = describe_match(answers, filled)

    assert (match.key_count, match.unmatched_key_count, match.blank_key_count) == (4, 1, 1)
    assert match.blank_requested == ("Impact",)

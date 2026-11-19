"""Tests for reading a model's JSON answer: the strict extractor and the forgiving template parse.

Pure functions over literal model outputs; no writer is involved. The corpus pins the extractor's
results, which were checked equal to the two extractors it replaced (the incident draft's balanced
brace scan and the status update's first-object decode) before they were deleted.
"""

import pytest

from capabilities.ai_writing.domain import coerce_answer, extract_json_object, parse_answers

pytestmark = pytest.mark.unit

_CORPUS = [
    ('{"a": "b"}', {"a": "b"}),
    ('Here you go:\n{"a": "b"}\nHope that helps.', {"a": "b"}),
    ('{"a": "x {y} z", "b": "q\\"}"}', {"a": "x {y} z", "b": 'q"}'}),
    ('{"a": {"n": "v"}, "b": ["l1", "l2"]}', {"a": {"n": "v"}, "b": ["l1", "l2"]}),
    ('[{"a": "b"}]', {"a": "b"}),
    ('{"a": "b"', None),
    ("no object here", None),
    ("", None),
    ('Use {curly} braces: {"a": "b"}', None),
    ('{"a": "b",}', None),
    ('{"a": "b"} trailing {"c": "d"}', {"a": "b"}),
    ('{"a": 1, "b": null, "c": true}', {"a": 1, "b": None, "c": True}),
    ('"just a string"', None),
    ('{"a": "line\nbreak"}', None),
    ('{"a": "\\u00e9t\\u00e9"}', {"a": "été"}),
]


@pytest.mark.parametrize(("raw", "expected"), _CORPUS)
def test_the_extractor_returns_the_first_complete_object_uncoerced(raw: str, expected: object) -> None:
    assert extract_json_object(raw) == expected


def test_a_clean_object_is_not_truncated() -> None:
    assert parse_answers('{"Trigger": "A bad deploy."}') == ({"Trigger": "A bad deploy."}, False)


def test_prose_around_the_object_is_ignored() -> None:
    raw = 'Here you go:\n{"Trigger": "A bad deploy."}\nHope that helps.'

    assert parse_answers(raw) == ({"Trigger": "A bad deploy."}, False)


def test_a_code_fenced_object_is_read() -> None:
    assert parse_answers('```json\n{"Trigger": "A bad deploy."}\n```') == ({"Trigger": "A bad deploy."}, False)


def test_a_cut_off_answer_keeps_its_complete_pairs_with_escapes() -> None:
    raw = '{"Trigger": "A \\"bad\\" deploy.\\nRolled back.", "Impact": "Checkout'

    assert parse_answers(raw) == ({"Trigger": 'A "bad" deploy.\nRolled back.'}, True)


@pytest.mark.parametrize("raw", ["", "not json at all", '{"Trigger": "cut', '["a", "b"]'])
def test_nothing_recoverable_gives_none(raw: str) -> None:
    assert parse_answers(raw) == (None, True)


def test_empty_and_non_text_values_are_dropped() -> None:
    answers, truncated = parse_answers('{"A": "", "B": 3, "C": null, "D": "kept"}')

    assert (answers, truncated) == ({"D": "kept"}, False)


def test_a_list_value_becomes_one_line_per_item() -> None:
    assert coerce_answer(["first", " ", {"time": "10:00", "text": "second"}, 4]) == "first\n10:00 second"


def test_an_object_value_is_flattened_in_field_order() -> None:
    assert coerce_answer({"time": " 10:00 ", "text": "deploy", "blank": " "}) == "10:00 deploy"

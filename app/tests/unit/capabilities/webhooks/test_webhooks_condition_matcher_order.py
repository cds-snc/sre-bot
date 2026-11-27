"""Unit tests for the declarative matcher: operators, groups and the instance's declared order.

Kinds are built from the conftest's valid file with their match replaced; the matcher runs
over in-memory payloads.
"""

from typing import Any

import pytest

from capabilities.webhooks.domain.kinds import first_match
from tests.unit.capabilities.webhooks.conftest import build_kind, kind_document

pytestmark = pytest.mark.unit


def _kind(kind_id: str, match: dict[str, Any]):  # noqa: ANN202 - SenderKind
    return build_kind(kind_document(id=kind_id, match=match))


@pytest.mark.parametrize(
    ("condition", "payload", "expected"),
    [
        ({"path": "$.type", "op": "equals", "value": "alarm"}, {"type": "alarm"}, True),
        ({"path": "$.type", "op": "equals", "value": "alarm"}, {"type": "other"}, False),
        ({"path": "$.count", "op": "equals", "value": 1}, {"count": True}, False),
        ({"path": "$.state", "op": "in", "value": ["ALARM", "OK"]}, {"state": "OK"}, True),
        ({"path": "$.state", "op": "exists", "value": True}, {"state": None}, True),
        ({"path": "$.state", "op": "exists", "value": False}, {}, True),
        ({"path": "$.arn", "op": "starts_with", "value": "arn:aws:budgets"}, {"arn": "arn:aws:budgets::1"}, True),
        ({"path": "$.arn", "op": "starts_with", "value": "arn"}, {"arn": 5}, False),
        ({"path": "$.subject", "op": "contains", "value": "Budget"}, {"subject": "AWS Budget alert"}, True),
        ({"path": "$.tags", "op": "contains", "value": "prod"}, {"tags": ["dev", "prod"]}, True),
        ({"path": "$.records[0].source", "op": "equals", "value": "s3"}, {"records": [{"source": "s3"}]}, True),
        ({"path": "$.records[3].source", "op": "equals", "value": "s3"}, {"records": []}, False),
        ({"path": "$.missing.deep", "op": "equals", "value": "x"}, {"missing": "text"}, False),
    ],
)
def test_each_operator_tests_the_payload(condition: dict[str, Any], payload: dict[str, Any], expected: bool) -> None:
    kind = _kind("k", {"all": [condition]})

    assert (first_match([kind], payload) is kind) is expected


def test_all_needs_every_condition_and_any_needs_one() -> None:
    a = {"path": "$.a", "op": "equals", "value": 1}
    b = {"path": "$.b", "op": "equals", "value": 2}
    both = _kind("both", {"all": [a, b]})
    either = _kind("either", {"any": [a, b]})

    assert first_match([both], {"a": 1}) is None
    assert first_match([either], {"a": 1}) is either


def test_groups_nest() -> None:
    nested = _kind(
        "nested",
        {"all": [{"path": "$.a", "op": "equals", "value": 1}, {"any": [{"path": "$.b", "op": "exists", "value": True}]}]},
    )

    assert first_match([nested], {"a": 1, "b": 0}) is nested
    assert first_match([nested], {"a": 1}) is None


def test_the_first_matching_kind_in_the_declared_order_wins() -> None:
    """Two kinds match the same payload; the instance's order decides, never the file system."""
    broad = _kind("broad", {"all": [{"path": "$.source", "op": "exists", "value": True}]})
    narrow = _kind("narrow", {"all": [{"path": "$.source", "op": "equals", "value": "aws.budgets"}]})
    payload = {"source": "aws.budgets"}

    assert first_match([narrow, broad], payload) is narrow
    assert first_match([broad, narrow], payload) is broad


def test_no_matching_kind_returns_none() -> None:
    assert first_match([_kind("k", {"all": [{"path": "$.x", "op": "exists", "value": True}]})], {}) is None

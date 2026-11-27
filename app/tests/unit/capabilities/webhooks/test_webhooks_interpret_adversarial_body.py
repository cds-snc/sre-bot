"""Adversarial bodies at the body cap through matching, extraction, rendering and the email finder.

Each body is about 512 KiB, twice the SNS message limit, shaped to make a naive engine
slow: deep nesting, one very long string, a wide object, and floods of the characters an
address scanner or a template engine would backtrack on. Each must finish well under a second.
"""

import time
from typing import Any

import pytest

from capabilities.webhooks.domain.interpret import interpret
from capabilities.webhooks.domain.mentions import find_email_addresses
from tests.unit.capabilities.webhooks.conftest import LANGUAGES, build_kind, delivery, kind_document, limits

pytestmark = pytest.mark.unit

BODY_CAP = 512 * 1024


def _deep(levels: int) -> dict[str, Any]:
    node: dict[str, Any] = {"leaf": "x"}
    for _ in range(levels):
        node = {"n": node}
    return node


BODIES = {
    "long string": {"source": "aws.budgets", "detail": {"name": "a" * BODY_CAP, "message": "@." * (BODY_CAP // 4)}},
    "wide object": {"source": "aws.budgets", "detail": {"name": "w"}, **{f"k{index}": index for index in range(40_000)}},
    "deep object": {"source": "aws.budgets", "detail": {"name": "d", "message": "m"}, "deep": _deep(500)},
    "invisible flood": {"source": "aws.budgets", "detail": {"name": "‮​" * (BODY_CAP // 2)}},
    "address flood": {"source": "aws.budgets", "detail": {"name": "n", "message": "a@b." * (BODY_CAP // 4)}},
}


@pytest.mark.parametrize("name", sorted(BODIES))
def test_an_adversarial_body_is_interpreted_well_under_a_second(name: str) -> None:
    kind = build_kind(kind_document())
    started = time.perf_counter()

    interpret([kind] * 20, BODIES[name], delivery(), languages=LANGUAGES, limits=limits())

    assert time.perf_counter() - started < 0.5


@pytest.mark.parametrize(
    "text",
    ["@" * BODY_CAP, "a." * (BODY_CAP // 2), ("x" * 63 + "@") * (BODY_CAP // 64), ("u@d.co " * (BODY_CAP // 7))],
)
def test_the_email_finder_is_linear_on_a_body_sized_text(text: str) -> None:
    started = time.perf_counter()

    find_email_addresses(text, limit=10)

    assert time.perf_counter() - started < 0.5

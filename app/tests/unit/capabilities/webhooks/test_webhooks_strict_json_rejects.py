"""Unit tests for the strict JSON decoder every protocol uses (RFC 7493, I-JSON).

Each case feeds raw bytes to ``loads_strict`` and asserts it either returns the parsed value or
raises ``StrictJsonError``; parsers disagree on these inputs, so a refusal is the only safe
answer. The adversarial case asserts the decoder stays linear at a large body.
"""

import time

import pytest

from capabilities.webhooks.domain.strict_json import StrictJsonError, loads_strict

pytestmark = pytest.mark.unit

DEPTH = 64


def test_a_plain_object_parses() -> None:
    assert loads_strict(b'{"a": [1, 2.5, "x", true, null]}', max_depth=DEPTH) == {"a": [1, 2.5, "x", True, None]}


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param(b'{"a": 1, "a": 2}', id="duplicate-member"),
        pytest.param(b'{"a": {"b": 1, "b": 1}}', id="nested-duplicate-member"),
        pytest.param(b'{"a": NaN}', id="nan"),
        pytest.param(b'{"a": Infinity}', id="infinity"),
        pytest.param(b'{"a": -Infinity}', id="negative-infinity"),
        pytest.param(b'{"a": 1e400}', id="non-finite-number"),
        pytest.param(b'{"a": "\\ud800"}', id="lone-surrogate-value"),
        pytest.param(b'{"\\udfff": 1}', id="lone-surrogate-key"),
        pytest.param(b'{"a": 1', id="truncated"),
        pytest.param(b"\xff\xfe{}", id="not-utf8"),
        pytest.param(b'{"a": 1}{"b": 2}', id="trailing-data"),
        pytest.param(b'{"a": ' + b"9" * 5000 + b"}", id="integer-past-the-digit-limit"),
    ],
)
def test_ambiguous_json_is_refused(raw: bytes) -> None:
    with pytest.raises(StrictJsonError):
        loads_strict(raw, max_depth=DEPTH)


def test_nesting_past_the_depth_limit_is_refused() -> None:
    within = b"[" * DEPTH + b"]" * DEPTH
    beyond = b"[" * (DEPTH + 1) + b"]" * (DEPTH + 1)

    assert loads_strict(within, max_depth=DEPTH) is not None
    with pytest.raises(StrictJsonError):
        loads_strict(beyond, max_depth=DEPTH)


def test_nesting_past_the_interpreter_recursion_limit_is_refused_not_crashed() -> None:
    raw = b"[" * 100_000 + b"]" * 100_000

    with pytest.raises(StrictJsonError):
        loads_strict(raw, max_depth=DEPTH)


def test_a_large_flat_body_decodes_in_linear_time() -> None:
    """A body near the SNS cap of many members decodes well under a second."""
    raw = b"{" + b",".join(b'"k%d": "%s"' % (i, b"v" * 40) for i in range(10_000)) + b"}"
    started = time.perf_counter()

    loads_strict(raw, max_depth=DEPTH)

    assert time.perf_counter() - started < 1.0

"""Strict JSON decoding for untrusted bodies (RFC 7493, I-JSON).

Parsers disagree on duplicate member names, NaN and Infinity, non-finite numbers, lone
surrogates and deep nesting, and the standard library keeps the last duplicate silently,
so a body that carries any of them is refused rather than read one way here and another
way downstream (decisions/webhooks.md 3 Pipeline, step 2; Bishop Fox, JSON
interoperability vulnerabilities). Decoding is linear in the body: one parse and one
iterative walk, no recursion of our own.
"""

import json
import math
from typing import Any


class StrictJsonError(ValueError):
    """The body is not strict JSON; the protocol answers 400."""


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError("duplicate member name")
        result[key] = value
    return result


def _no_constant(name: str) -> Any:
    raise StrictJsonError(f"{name} is not JSON")


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise StrictJsonError("non-finite number")
    return value


def _is_scalar_text_ok(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _check(value: Any, max_depth: int) -> None:
    """Walk ``value`` iteratively: nesting within ``max_depth`` and no lone surrogate anywhere."""
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        node, depth = stack.pop()
        if isinstance(node, str):
            if not _is_scalar_text_ok(node):
                raise StrictJsonError("lone surrogate")
            continue
        if isinstance(node, dict | list):
            if depth >= max_depth:
                raise StrictJsonError("nesting past the depth limit")
            if isinstance(node, dict):
                for key, child in node.items():
                    if not _is_scalar_text_ok(key):
                        raise StrictJsonError("lone surrogate")
                    stack.append((child, depth + 1))
            else:
                stack.extend((child, depth + 1) for child in node)


def loads_strict(raw: bytes | str, *, max_depth: int) -> Any:
    """Parse ``raw`` as strict JSON, or raise ``StrictJsonError``.

    Args:
        raw: The body; bytes must be UTF-8.
        max_depth: The deepest nesting of objects and arrays accepted.
    """
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        value = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant, parse_float=_finite_float)
    except StrictJsonError:
        raise
    except (ValueError, RecursionError) as exc:
        # UnicodeDecodeError and JSONDecodeError are ValueErrors; so is Python's integer digit limit.
        raise StrictJsonError("not strict JSON") from exc
    _check(value, max_depth)
    return value

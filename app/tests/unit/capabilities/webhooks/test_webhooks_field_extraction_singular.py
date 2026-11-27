"""Unit tests for field extraction: singular paths, types, caps, links and text hygiene.

Fields are extracted from in-memory payloads with the conftest's kind and default limits.
"""

from typing import Any

import pytest

from capabilities.webhooks.domain.extraction import ExtractionMiss, compile_path, extract
from capabilities.webhooks.domain.values import normalise_https_url
from tests.unit.capabilities.webhooks.conftest import build_kind, kind_document, limits, payload

pytestmark = pytest.mark.unit


def _fields(fields: dict[str, Any], document: dict[str, Any]):  # noqa: ANN202 - mapping or miss
    plain = {"en-US": "Title", "fr-FR": "Titre"}
    kind = kind_document(fields=fields, links=[], alert=None, event="notification", templates={"title": plain, "summary": plain})
    return extract(build_kind(kind), document, limits())


def test_the_kind_fields_are_extracted_by_name() -> None:
    fields = extract(build_kind(kind_document()), payload(), limits())

    assert dict(fields) == {  # type: ignore[arg-type]
        "budget": "sandbox",
        "spent": 120.5,
        "console": "https://console.aws.amazon.com/billing/home",
        "message": "Actual spend is over the budget.",
    }


def test_a_missing_required_field_names_the_kind_and_the_field() -> None:
    document = payload()
    del document["detail"]["name"]

    assert extract(build_kind(kind_document()), document, limits()) == ExtractionMiss("budget-alert", "budget", "missing")


def test_a_missing_or_mistyped_optional_field_is_none() -> None:
    fields = _fields({"a": {"path": "$.a", "type": "integer"}, "b": {"path": "$.b"}}, {"a": "1"})

    assert dict(fields) == {"a": None, "b": None}  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("spec", "raw", "expected"),
    [
        ({"type": "string"}, 42, "42"),
        ({"type": "string"}, True, None),
        ({"type": "string"}, {"nested": 1}, None),
        ({"type": "integer"}, 7, 7),
        ({"type": "integer"}, True, None),
        ({"type": "number"}, float("inf"), None),
        ({"type": "boolean"}, False, False),
        ({"type": "string_list"}, ["a", 1, None, {"x": 1}], ("a", "1")),
    ],
)
def test_values_are_type_checked(spec: dict[str, Any], raw: object, expected: object) -> None:
    fields = _fields({"value": {"path": "$.value", **spec}}, {"value": raw})

    assert fields["value"] == expected  # type: ignore[index]


def test_text_and_lists_are_capped() -> None:
    fields = _fields(
        {"text": {"path": "$.text"}, "items": {"path": "$.items", "type": "string_list"}},
        {"text": "x" * 10_000, "items": [str(index) for index in range(500)]},
    )

    assert len(fields["text"]) == 4096 and fields["text"].endswith("…")  # type: ignore[index,union-attr]
    assert len(fields["items"]) == 50  # type: ignore[index,arg-type]


def test_invisible_and_direction_changing_characters_are_removed() -> None:
    """Trojan Source and zero-width characters never reach a template or a post."""
    raw = "pay‮loads​⁦ ok\u0007\tline\ncaféㅤ"

    fields = _fields({"text": {"path": "$.text"}}, {"text": raw})

    assert fields["text"] == "payloads ok\tline\ncafé"  # type: ignore[index]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://console.aws.amazon.com/a?b=1#c", "https://console.aws.amazon.com/a?b=1#c"),
        ("HTTPS://Example.COM/path", "https://example.com/path"),
        ("https://example.com/a|b>c<d", "https://example.com/a%7Cb%3Ec%3Cd"),
        ("https://example.com/?q=<!channel>|x", "https://example.com/?q=%3C!channel%3E%7Cx"),
        ("https://bücher.example/", "https://xn--bcher-kva.example/"),
        ("https://example.com:8443/x", "https://example.com:8443/x"),
        ("http://example.com/", None),
        ("javascript:alert(1)", None),
        ("https://user:pass@example.com/", None),
        ("https://@example.com/", None),
        ("https:///path", None),
        ("https://example.com/a b", None),
        ("https://example.com/‮", None),
        ("https://example.com:99999/", None),
        ("https://" + "a" * 3000 + ".com/", None),
    ],
)
def test_link_urls_are_validated_and_reencoded(raw: str, expected: str | None) -> None:
    assert normalise_https_url(raw, max_chars=2048) == expected


def test_a_url_field_honours_its_allowed_hosts() -> None:
    spec = {"link": {"path": "$.link", "type": "url", "allowed_hosts": ["github.com"]}}

    assert _fields(spec, {"link": "https://github.com/org/repo"})["link"] == "https://github.com/org/repo"  # type: ignore[index]
    assert _fields(spec, {"link": "https://evil.example/github.com"})["link"] is None  # type: ignore[index]


def test_compile_path_refuses_a_non_singular_query() -> None:
    with pytest.raises(ValueError, match="singular"):
        compile_path("$.items[*].name")

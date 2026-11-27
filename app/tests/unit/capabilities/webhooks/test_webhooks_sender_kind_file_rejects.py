"""Unit tests for the sender-kind file model: what a valid file holds and each rule that refuses one.

Each test validates a copy of the conftest's valid kind with one change; a refusal is a
pydantic ValidationError whose message names the problem, which the content loader reports
with the file and the field.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from capabilities.webhooks.domain.events import EventType
from capabilities.webhooks.schemas import SenderKindFile
from tests.unit.capabilities.webhooks.conftest import build_kind, kind_document

pytestmark = pytest.mark.unit


def _refused(document: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        SenderKindFile.model_validate(document)


def test_a_valid_file_builds_a_kind() -> None:
    kind = build_kind(kind_document())

    assert (kind.id, kind.event_type, [spec.name for spec in kind.fields]) == (
        "budget-alert",
        EventType.ALERT,
        ["budget", "spent", "console", "message"],
    )
    assert kind.title is not None and set(kind.title.templates) == {"en-US", "fr-FR"}


def test_a_suppressed_kind_needs_no_templates() -> None:
    kind = build_kind(kind_document(templates=None, links=None, alert=None, suppress=True))

    assert kind.suppress and kind.title is None


def test_bot_wording_must_cover_every_supported_language() -> None:
    document = kind_document()
    del document["templates"]["title"]["fr-FR"]

    _refused(document, "fr-FR")


@pytest.mark.parametrize(
    "path",
    ["$.detail[?@.name]", "$.detail.*", "$..name", "$.detail[0:2]", "$.a | $.b", "detail.name"],
)
def test_a_path_that_is_not_a_singular_query_is_refused(path: str) -> None:
    document = kind_document()
    document["fields"]["budget"]["path"] = path

    _refused(document, "singular|invalid JSONPath")


@pytest.mark.parametrize(
    ("template", "message"),
    [
        ("{{ fields.nope }}", "fields.nope"),
        ("{{ raw.body }}", "raw.body"),
        ("{{ instance.url }}", "instance.url"),
        ("{% assign x = 1 %}{{ x }}", "unexpected tag 'assign'"),
        ("{% include 'other' %}", "unexpected tag 'include'"),
        ("{% capture x %}y{% endcapture %}", "unexpected tag 'capture'"),
        ("{{ fields.budget | base64_decode }}", "base64_decode"),
        ("{% if %}x{% endif %}", "invalid template"),
    ],
)
def test_a_template_that_reads_outside_the_data_model_or_uses_a_removed_tag_is_refused(template: str, message: str) -> None:
    document = kind_document()
    document["templates"]["title"]["en-US"] = template

    _refused(document, message)


def test_a_link_label_may_not_name_a_payload_field() -> None:
    document = kind_document()
    document["links"][0]["label"]["en-US"] = "Open {{ fields.budget }}"

    _refused(document, "fields.budget")


def test_a_link_must_use_an_extracted_url_field() -> None:
    _refused(kind_document(links=[{"field": "budget", "label": {"en-US": "a", "fr-FR": "b"}}]), "url field")


def test_conditions_past_the_depth_limit_are_refused() -> None:
    deep = {"all": [{"any": [{"all": [{"path": "$.a", "op": "exists", "value": True}]}]}]}

    _refused(kind_document(match=deep), "nests 3 groups")


def test_conditions_past_the_count_limit_are_refused() -> None:
    many = {"any": [{"path": "$.a", "op": "equals", "value": index} for index in range(51)]}

    _refused(kind_document(match=many), "51 conditions")


@pytest.mark.parametrize(
    ("condition", "message"),
    [
        ({"path": "$.a", "op": "matches", "value": ".*"}, "op"),
        ({"path": "$.a", "op": "in", "value": "x"}, "non-empty list"),
        ({"path": "$.a", "op": "exists", "value": "yes"}, "true or false"),
        ({"path": "$.a", "op": "equals", "value": ["x"]}, "single value"),
    ],
)
def test_a_condition_with_an_unknown_operator_or_a_mismatched_operand_is_refused(condition: dict[str, Any], message: str) -> None:
    _refused(kind_document(match={"all": [condition]}), message)


def test_a_group_sets_exactly_one_mode() -> None:
    condition = {"path": "$.a", "op": "exists", "value": True}

    _refused(kind_document(match={"all": [condition], "any": [condition]}), "exactly one")


def test_an_overlong_template_is_refused() -> None:
    document = kind_document()
    document["templates"]["summary"]["fr-FR"] = "x" * 2049

    _refused(document, "2048 characters")


def test_alert_values_on_a_notification_are_refused() -> None:
    _refused(kind_document(event="notification"), "event alert only")


def test_a_payload_cannot_be_given_the_passthrough_type() -> None:
    _refused(kind_document(event="slack.passthrough"), "event")


def test_unknown_keys_are_refused() -> None:
    _refused(kind_document(blocks=[{"type": "section"}]), "blocks")


def test_allowed_hosts_are_kept_in_punycode() -> None:
    document = kind_document()
    document["fields"]["console"]["allowed_hosts"] = ["Bücher.example"]

    kind = build_kind(document)

    assert next(spec for spec in kind.fields if spec.name == "console").allowed_hosts == {"xn--bcher-kva.example"}

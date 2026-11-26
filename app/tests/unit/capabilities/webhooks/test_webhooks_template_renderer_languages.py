"""Unit tests for rendering: per-language bot wording, sender details once, alert values, limits.

Kinds come from the conftest's valid file; fields are extracted from its payload, then
rendered with default limits.
"""

from typing import Any

import pytest

from capabilities.webhooks.domain.events import Alert, AlertStatus, Notification, Severity
from capabilities.webhooks.domain.extraction import extract
from capabilities.webhooks.domain.rendering import RenderFailure, render
from contracts.languages import MultilingualText
from tests.unit.capabilities.webhooks.conftest import RECEIVED_AT, build_kind, kind_document, limits, payload

pytestmark = pytest.mark.unit


def _render(document: dict[str, Any], body: dict[str, Any] | None = None, languages=("en-US", "fr-FR")):  # noqa: ANN001,ANN202
    kind = build_kind(document)
    fields = extract(kind, body or payload(), limits())
    return render(kind, fields, instance_name="Billing", received_at=RECEIVED_AT, languages=languages, limits=limits())  # type: ignore[arg-type]


def test_bot_wording_renders_in_the_given_languages_and_order() -> None:
    alert = _render(kind_document())

    assert isinstance(alert, Alert)
    assert alert.title == MultilingualText((("en-US", "Budget sandbox exceeded"), ("fr-FR", "Budget sandbox dépassé")))
    french_first = _render(kind_document(), languages=("fr-FR", "en-US"))
    assert [language for language, _ in french_first.title.parts] == ["fr-FR", "en-US"]


def test_sender_details_appear_once_in_their_source_language() -> None:
    alert = _render(kind_document())

    assert alert.details == "Actual spend is over the budget."


def test_links_carry_the_validated_url_and_a_fixed_label() -> None:
    (link,) = _render(kind_document()).links

    assert link.url == "https://console.aws.amazon.com/billing/home"
    assert link.label == MultilingualText((("en-US", "Open the console"), ("fr-FR", "Ouvrir la console")))


def test_a_link_without_a_valid_url_is_left_out() -> None:
    body = payload()
    body["detail"]["url"] = "http://insecure.example/"

    assert _render(kind_document(), body).links == ()


def test_alert_values_render_into_their_closed_sets() -> None:
    document = kind_document(
        alert={
            "status": "{% if fields.spent > 100 %}firing{% else %}resolved{% endif %}",
            "severity": "warning",
            "dedup_key": "budget:{{ fields.budget }}",
        }
    )

    alert = _render(document)

    assert (alert.status, alert.severity, alert.dedup_key) == (AlertStatus.FIRING, Severity.WARNING, "budget:sandbox")


def test_an_alert_value_outside_its_set_fails_rendering() -> None:
    with pytest.raises(RenderFailure) as failure:
        _render(kind_document(alert={"severity": "{{ fields.budget }}"}))

    assert (failure.value.kind_id, failure.value.field) == ("budget-alert", "alert.severity")


def test_a_notification_kind_renders_a_notification() -> None:
    assert isinstance(_render(kind_document(event="notification", alert=None)), Notification)


def test_the_template_sees_the_instance_name_and_received_time() -> None:
    document = kind_document()
    document["templates"]["summary"] = {"en-US": "{{ instance.name }} at {{ received_at }}", "fr-FR": "{{ instance.name }}"}

    assert _render(document).summary.parts[0] == ("en-US", "Billing at 2026-11-26T12:00:00+00:00")


def test_a_long_title_is_cut_with_an_ellipsis() -> None:
    document = kind_document()
    document["templates"]["title"] = {"en-US": "{{ fields.message }}{{ fields.message }}" * 3, "fr-FR": "t"}

    title = _render(document).title.parts[0][1]

    assert len(title) == 150 and title.endswith("…")


def test_payload_text_is_rendered_as_data_never_as_template() -> None:
    body = payload()
    body["detail"]["name"] = "{{ instance.name }} {% for x in (1..9) %}x{% endfor %}"

    assert (
        _render(kind_document(), body).title.parts[0][1]
        == "Budget {{ instance.name }} {% for x in (1..9) %}x{% endfor %} exceeded"
    )


def test_markup_in_payload_text_stays_plain_text() -> None:
    """The engine never escapes or interprets markup; the platform adapter escapes on output."""
    body = payload()
    body["detail"]["name"] = "<!channel> <@U123> <https://x|y>"

    assert _render(kind_document(), body).title.parts[0][1] == "Budget <!channel> <@U123> <https://x|y> exceeded"


def test_a_loop_past_its_limit_fails_rendering() -> None:
    document = kind_document()
    document["fields"]["items"] = {"path": "$.items", "type": "string_list"}
    document["templates"]["summary"] = {
        "en-US": "{% for x in fields.items %}{% for y in fields.items %}.{% endfor %}{% endfor %}",
        "fr-FR": "x",
    }
    body = payload() | {"items": [str(index) for index in range(50)]}

    with pytest.raises(RenderFailure) as failure:
        _render(document, body)

    assert failure.value.field == "summary"


def test_a_language_without_a_template_fails_rendering() -> None:
    with pytest.raises(RenderFailure, match="de-DE"):
        _render(kind_document(), languages=("en-US", "de-DE"))

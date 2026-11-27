"""The information view and the field views of ``/sre incident show``, built from a record.

The builders are pure: each test builds a view from an ``Incident`` and reads what a user
would see (section text, the options a select offers, what it preselects) in the locale
asked for, from the real catalogues the directory's conftest loads.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from features.incident.common.vocabulary import Severity
from features.incident.response.entrypoints.slack_show_views import Field, build_field_view, build_show_view, time_text
from tests.factories.incident import incident_on

pytestmark = pytest.mark.unit

INCIDENT = incident_on("C0INCIDENT", "inc-1")
DETECTED = datetime(2026, 10, 1, 13, 30, tzinfo=UTC)


def _input(view: dict[str, Any]) -> dict[str, Any]:
    [block] = [block for block in view["blocks"] if block["type"] == "input"]
    element: dict[str, Any] = block["element"]
    return element


def test_a_set_time_is_a_slack_date_token_and_an_unset_one_is_unknown() -> None:
    epoch = int(DETECTED.timestamp())

    assert time_text(DETECTED, "en-US") == f"<!date^{epoch}^{{date}} at {{time}}|Unknown>"
    assert time_text(DETECTED, "fr-FR") == f"<!date^{epoch}^{{date}} à {{time}}|Inconnu>"
    assert time_text(None, "en-US") == "Unknown"


def test_the_severity_field_offers_sev0_first_and_preselects_a_stored_sev0() -> None:
    element = _input(build_field_view(replace(INCIDENT, severity=Severity.SEV0), Field.SEVERITY, locale="en-US", channel_id="C0"))

    assert element["initial_option"]["value"] == "sev-0"
    assert [option["value"] for option in element["options"]] == ["none", "sev-0", "sev-1", "sev-2", "sev-3", "sev-4"]


def test_an_unrated_severity_preselects_none() -> None:
    element = _input(build_field_view(INCIDENT, Field.SEVERITY, locale="en-US", channel_id="C0"))

    assert element["initial_option"]["value"] == "none"


def test_the_security_field_offers_yes_and_no_in_the_locale_and_preselects_the_stored_flag() -> None:
    element = _input(
        build_field_view(replace(INCIDENT, security_incident=True), Field.SECURITY_INCIDENT, locale="fr-FR", channel_id="C0")
    )

    assert [(option["value"], option["text"]["text"]) for option in element["options"]] == [("yes", "Oui"), ("no", "Non")]
    assert element["initial_option"]["value"] == "yes"


def test_a_set_time_prefills_the_picker_with_its_instant() -> None:
    element = _input(
        build_field_view(replace(INCIDENT, detected_at=DETECTED), Field.DETECTION_TIME, locale="en-US", channel_id="C0")
    )

    assert (element["type"], element["initial_date_time"]) == ("datetimepicker", int(DETECTED.timestamp()))


def test_a_reference_without_a_link_shows_its_label_unlinked() -> None:
    view = build_show_view(INCIDENT, {}, report_link=None, call_link=None, locale="en-US", channel_id="C0")

    [links] = [block for block in view["blocks"] if "fields" in block][:1]
    assert [field_["text"] for field_ in links["fields"]] == [":memo: Incident Report", ":headphones: Google Meet"]

"""The declare form, loading and success views as Block Kit.

Pure builders over the real catalogues (the directory's conftest loads them).
Assertions are on what the user sees and on the ids the handlers read back: the
products in label order, the severity options equal to the update modal's with
SEV0 first after none, both yes/no questions defaulting to no, the locale carried
on the locale button, the product block left out with no placements, and the
success view naming the channel.
"""

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.api import ReportPlacement
from features.incident.response.entrypoints.slack_declare_views import (
    DECLARE_CALLBACK_ID,
    LOCALE_ACTION_ID,
    build_declare_view,
    build_loading_view,
    build_success_view,
    form_locale,
    toggled,
    view_locale,
)
from features.incident.response.entrypoints.slack_show_views import SEVERITY_OPTIONS
from tests.factories.incident import GOOGLE_TENANT

pytestmark = pytest.mark.unit

PLACEMENTS = tuple(
    ReportPlacement(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id=folder, label=label)
    for folder, label in (("F0FORMS", "Forms"), ("F0NOTIFY", "Notify"))
)


def _form(locale: str = "en-US", placements: tuple[ReportPlacement, ...] = PLACEMENTS) -> dict:
    return build_declare_view(
        name="db down", placements=placements, locale=locale, private_metadata="meta", handbook_url="https://h"
    )


def _block(view: dict, block_id: str) -> dict:
    return next(block for block in view["blocks"] if block.get("block_id") == block_id)


def test_the_form_offers_the_placements_and_the_update_modals_severities() -> None:
    form = _form()

    assert (form["callback_id"], form["private_metadata"]) == (DECLARE_CALLBACK_ID, "meta")
    assert [(o["value"], o["text"]["text"]) for o in _block(form, "product")["element"]["options"]] == [
        ("F0FORMS", "Forms"),
        ("F0NOTIFY", "Notify"),
    ]
    severities = _block(form, "severity")["element"]["options"]
    assert tuple(option["value"] for option in severities) == SEVERITY_OPTIONS
    assert [option["text"]["text"] for option in severities][:2] == ["None", "SEV-0"]


@pytest.mark.parametrize("block_id", ["security_incident", "policy_help"])
def test_both_questions_default_to_no(block_id: str) -> None:
    element = _block(_form(), block_id)["element"]

    assert element["initial_option"]["value"] == "no"
    assert [option["value"] for option in element["options"]] == ["yes", "no"]


def test_the_french_form_carries_its_locale_on_the_button_that_switches_to_english() -> None:
    form = _form("fr-FR")

    [button] = _block(form, "locale")["elements"]
    assert (button["action_id"], button["value"], button["text"]["text"]) == (LOCALE_ACTION_ID, "fr-FR", "English")
    assert _block(form, "product")["label"]["text"] == "Produit"
    assert view_locale(form) == "fr-FR"
    assert "<https://h|Guide de gestion des incidents>" in form["blocks"][-1]["elements"][0]["text"]


def test_without_placements_the_product_block_is_left_out() -> None:
    assert "product" not in [block.get("block_id") for block in _form(placements=())["blocks"]]


def test_the_toggle_and_unknown_locales() -> None:
    assert (toggled("en-US"), toggled("fr-FR")) == ("fr-FR", "en-US")
    assert (form_locale("de-DE"), form_locale(None)) == ("en-US", "en-US")
    assert view_locale({"blocks": []}) == "en-US"


def test_the_loading_and_success_views() -> None:
    assert "Lancement du processus d'incident..." in build_loading_view("fr-FR")["blocks"][0]["text"]["text"]
    success = build_success_view(locale="en-US", channel_id="C0NEW")
    assert success["blocks"][0]["text"]["text"] == "Incident successfully created"
    assert "<#C0NEW>" in success["blocks"][1]["text"]["text"]

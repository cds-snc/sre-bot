"""Block Kit views of the declare: the loading view, the declare form and the success view.

The form carries its language in the locale button's value, which the toggle flips
and the submission's success view reads; its private metadata is the caller's
(the source alert's channel and message when called from an alert) and passes
through every re-render unchanged. Product options are the report placements in
label order; with none listed the product block is left out and the report is
filed in the default folder. Severity offers the update modal's options, SEV0 first
after none. Every word comes from the ``incident_response`` catalogue.
"""

from collections.abc import Mapping, Sequence
from typing import Any

from features.incident.core.api import ReportPlacement
from features.incident.core.api import translate as t
from features.incident.response.entrypoints.slack_show_views import SEVERITY_OPTIONS

DECLARE_DOMAIN = "incident_response.declare"
DECLARE_CALLBACK_ID = "incident.response.declare"
LOCALE_ACTION_ID = "incident.response.locale"

LOCALE_BLOCK_ID = "locale"
NAME_BLOCK_ID = "name"
PRODUCT_BLOCK_ID = "product"
SEVERITY_BLOCK_ID = "severity"
SECURITY_BLOCK_ID = "security_incident"
POLICY_HELP_BLOCK_ID = "policy_help"

# The two languages the form toggles between, each naming the other on its button.
_TOGGLE = {"en-US": "fr-FR", "fr-FR": "en-US"}


def toggled(locale: str) -> str:
    """The language the locale button switches the form to."""
    return _TOGGLE.get(locale, "en-US")


def form_locale(locale: str | None) -> str:
    """A language the form is written in: ``locale`` when the form has it, English otherwise."""
    return locale if locale in _TOGGLE else "en-US"


def build_loading_view(locale: str) -> dict[str, Any]:
    """The view opened at once on the trigger, while the placements are read."""
    return {
        "type": "modal",
        "callback_id": DECLARE_CALLBACK_ID,
        "title": _plain(_t("modal.title", locale)),
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": _t("modal.launching", locale)}}],
    }


def build_declare_view(
    *,
    name: str,
    placements: Sequence[ReportPlacement],
    locale: str,
    private_metadata: str,
    handbook_url: str,
) -> dict[str, Any]:
    """The declare form in ``locale``, its name field prefilled with ``name``."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "actions",
            "block_id": LOCALE_BLOCK_ID,
            "elements": [
                {
                    "type": "button",
                    "text": _plain(_t("modal.locale_button", locale)),
                    "value": locale,
                    "action_id": LOCALE_ACTION_ID,
                }
            ],
        },
        {"type": "header", "text": _plain(_t("modal.congratulations", locale))},
        _section(_t("modal.something_wrong", locale)),
        _section(_t("modal.app_help", locale)),
        {"type": "divider"},
        {"type": "section", "text": _plain(_t("modal.fill_the_fields", locale))},
        {
            "block_id": NAME_BLOCK_ID,
            "type": "input",
            "element": {"type": "plain_text_input", "action_id": NAME_BLOCK_ID, "initial_value": name},
            "label": _plain(_t("modal.description", locale)),
        },
    ]
    if placements:
        blocks.append(
            {
                "block_id": PRODUCT_BLOCK_ID,
                "type": "input",
                "element": {
                    "type": "static_select",
                    "placeholder": _plain(_t("modal.product", locale)),
                    "options": [_option(placement.label, placement.vendor_id) for placement in placements],
                    "action_id": PRODUCT_BLOCK_ID,
                },
                "label": _plain(_t("modal.product_label", locale)),
            }
        )
    blocks += [
        {
            "block_id": SEVERITY_BLOCK_ID,
            "type": "input",
            "element": {
                "type": "static_select",
                "placeholder": _plain(_t("modal.severity", locale)),
                "options": [_option(_severity_text(value, locale), value) for value in SEVERITY_OPTIONS],
                "action_id": SEVERITY_BLOCK_ID,
            },
            "label": _plain(_t("modal.severity", locale)),
        },
        _yes_no(SECURITY_BLOCK_ID, "modal.security_incident", "modal.security_incident_hint", locale),
        _yes_no(POLICY_HELP_BLOCK_ID, "modal.policy_help", "modal.policy_help_hint", locale),
        {"type": "context", "elements": [{"type": "mrkdwn", "text": _t("modal.handbook", locale, url=handbook_url)}]},
    ]
    return {
        "type": "modal",
        "callback_id": DECLARE_CALLBACK_ID,
        "title": _plain(_t("modal.title", locale)),
        "submit": _plain(_t("modal.submit", locale)),
        "private_metadata": private_metadata,
        "blocks": blocks,
    }


def build_success_view(*, locale: str, channel_id: str) -> dict[str, Any]:
    """The view telling the declarer the incident exists, with its channel (Slack shows the name) and what to ask next."""
    channel = f"<#{channel_id}>"
    return {
        "type": "modal",
        "title": _plain(_t("success.title", locale)),
        "close": _plain(_t("success.close", locale)),
        "blocks": [
            {"type": "header", "text": _plain(_t("success.header", locale))},
            _section(_t("success.user_added", locale, channel=channel)),
            {"type": "divider"},
            {"type": "header", "text": _plain(_t("success.next_steps", locale))},
            _section(_t("success.next_steps_instructions", locale)),
            _section(_t("success.brief_up", locale)),
            _section(_t("success.planned_testing", locale)),
        ],
    }


def view_locale(view: Mapping[str, Any]) -> str:
    """The language of an open declare form, read from its locale button."""
    for block in view.get("blocks") or ():
        if block.get("block_id") == LOCALE_BLOCK_ID:
            elements = block.get("elements") or [{}]
            return form_locale(str(elements[0].get("value", "")))
    return "en-US"


def _severity_text(value: str, locale: str) -> str:
    return _t("modal.sev_none", locale) if value == "none" else value.upper()


def _yes_no(block_id: str, label: str, hint: str, locale: str) -> dict[str, Any]:
    no = _option(_t("modal.no", locale), "no")
    return {
        "block_id": block_id,
        "type": "input",
        "element": {
            "type": "radio_buttons",
            "action_id": block_id,
            "options": [_option(_t("modal.yes", locale), "yes"), no],
            "initial_option": no,
        },
        "label": _plain(_t(label, locale)),
        "hint": {"type": "plain_text", "text": _t(hint, locale)},
    }


def _option(text: str, value: str) -> dict[str, Any]:
    return {"text": {"type": "plain_text", "text": text}, "value": value}


def _plain(text: str) -> dict[str, Any]:
    return {"type": "plain_text", "text": text, "emoji": True}


def _section(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _t(key: str, locale: str, **variables: str) -> str:
    """Translate ``key`` of the declare catalogue; the key itself is the neutral fallback (decisions/i18n.md)."""
    full_key = f"{DECLARE_DOMAIN}.{key}"
    return t(full_key, locale, full_key, **variables)

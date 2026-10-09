"""Tests for ``core.api.translate``, the umbrella's one route to the translator."""

from unittest.mock import patch

import pytest

from features.incident.core import api
from features.incident.core.adapters import i18n

pytestmark = pytest.mark.unit


def test_translate_passes_key_locale_fallback_and_variables_through() -> None:
    """``translate`` hands every argument to the platform translator unchanged and returns its answer.

    The translator is stubbed where the adapter imports it, so the assertion is
    on the call the adapter makes, not on any catalogue.
    """
    with patch.object(i18n, "t", return_value="Written by <@U1> at 11:00") as translator:
        rendered = api.translate("incident_status_update.origin.hand", "en-US", "origin.hand", author="<@U1>", time="11:00")

    assert rendered == "Written by <@U1> at 11:00"
    translator.assert_called_once_with("incident_status_update.origin.hand", "en-US", "origin.hand", author="<@U1>", time="11:00")


def test_translate_defaults_to_an_empty_fallback() -> None:
    """Without a fallback the translator receives an empty string, matching its own default."""
    with patch.object(i18n, "t", return_value="") as translator:
        api.translate("incident_status_update.saved_note", "fr-FR")

    translator.assert_called_once_with("incident_status_update.saved_note", "fr-FR", "")


def test_api_exports_translate_from_the_i18n_adapter() -> None:
    """``core.api`` re-exports the adapter's function, so views never import the adapter or the platform module."""
    assert api.translate is i18n.translate
    assert "translate" in api.__all__

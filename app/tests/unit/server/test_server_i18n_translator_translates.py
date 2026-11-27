"""Unit tests for the host translator behind the ``Translator`` contract.

Stub strategy: a stand-in translation service records each call and returns a fixed
text, or raises ``KeyError`` as the real one does for a missing key; a real svcs
registry checks the registration. The assertions pin the contract's two promises: the
key, language and variables reach the catalogue unchanged, and a missing entry falls
back to the key instead of failing the caller.
"""

from typing import Any

import pytest
import svcs

from contracts.i18n.translator import Translator
from infrastructure.i18n.models import Locale, TranslationKey
from server.i18n.translator import CatalogueTranslator, register_translator

pytestmark = pytest.mark.unit


class _Service:
    def __init__(self, *, text: str | None = "Bonjour {name}") -> None:
        self.text = text
        self.calls: list[tuple[TranslationKey, Locale, dict[str, Any] | None]] = []

    def translate(self, key: TranslationKey, locale: Locale, variables: dict[str, Any] | None = None) -> str:
        self.calls.append((key, locale, variables))
        if self.text is None:
            raise KeyError(str(key))
        return self.text


def test_the_key_language_and_variables_reach_the_catalogue() -> None:
    """The adapter converts the plain key and tag to the catalogue's own types."""
    service = _Service()

    text = CatalogueTranslator(service).translate("webhooks.fallback.header", "fr-FR", name="Billing")

    assert text == "Bonjour {name}"
    key, locale, variables = service.calls[0]
    assert (str(key), locale, variables) == ("webhooks.fallback.header", Locale.FR_FR, {"name": "Billing"})


def test_a_missing_entry_falls_back_to_the_key() -> None:
    """A catalogue without the key never fails the message it was wording."""
    assert CatalogueTranslator(_Service(text=None)).translate("webhooks.missing", "en-US") == "webhooks.missing"


def test_an_unsupported_language_falls_back_to_the_key() -> None:
    """A language tag the catalogue cannot parse is a missing entry, not an error."""
    assert CatalogueTranslator(_Service()).translate("webhooks.fallback.header", "xx-YY") == "webhooks.fallback.header"


def test_the_translator_is_registered_under_the_contract() -> None:
    """Capabilities resolve the contract from the registry, never the catalogue package."""
    registry = svcs.Registry()
    service = _Service()

    register_translator(registry, service)

    translator = svcs.Container(registry).get(Translator)
    assert isinstance(translator, Translator)
    assert translator.translate("k.x", "en-US") == "Bonjour {name}"

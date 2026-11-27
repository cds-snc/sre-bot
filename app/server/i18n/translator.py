"""The host's ``Translator``: the translation service behind the contract.

Registered in the service registry once the catalogues are loaded, before the
extension-point phase, so a capability resolves wording through the contract and never
imports the catalogue package (decisions/i18n.md).
"""

from typing import Any, Protocol

import svcs

from contracts.i18n.translator import Translator
from infrastructure.i18n.models import Locale, TranslationKey


class _TranslationService(Protocol):
    def translate(self, key: TranslationKey, locale: Locale, variables: dict[str, Any] | None = None) -> str: ...


class CatalogueTranslator(Translator):
    """Translate through the loaded catalogues; a missing key or language returns the key."""

    def __init__(self, service: _TranslationService) -> None:
        self._service = service

    def translate(self, key: str, language: str, /, **variables: str) -> str:
        """Return the key's wording in ``language``, or the key when the catalogues lack it."""
        try:
            return self._service.translate(TranslationKey.from_string(key), Locale.from_string(language), dict(variables) or None)
        except KeyError, ValueError:
            return key


def register_translator(registry: svcs.Registry, service: _TranslationService) -> None:
    """Register the catalogue translator under the ``Translator`` contract."""
    registry.register_value(Translator, CatalogueTranslator(service))

"""Host implementation of the language policy over the [languages] slice (decisions/languages.md).

Shared and generic messages use the instance's languages in their order, the
same for every conversation today; a per-tenant or per-conversation rule would
change only this class. A direct interaction uses the user's language of
choice: an exact match to a supported language, else a match on the primary
language subtag (RFC 4647 lookup: fr-CA to fr-FR), else the instance's first
language. A request that names no language is answered in the instance's
languages.
"""

from collections.abc import Sequence

from contracts.workplace import WorkplaceSystem
from server.languages.settings import SUPPORTED_LANGUAGES, LanguageSettings


class ConfiguredLanguagePolicy:
    """The language policy fixed at construction; pure, no I/O."""

    def __init__(self, *, shared: Sequence[str], supported: Sequence[str]) -> None:
        self._shared = tuple(shared)
        self._supported = tuple(supported)

    @classmethod
    def from_settings(cls, settings: LanguageSettings) -> ConfiguredLanguagePolicy:
        """Build the policy from the validated slice and the app's supported languages."""
        return cls(shared=settings.shared, supported=SUPPORTED_LANGUAGES)

    def shared_languages(self, *, system: WorkplaceSystem, tenant: str, conversation_id: str) -> tuple[str, ...]:
        """Return the instance's languages, in order; the conversation does not change them yet."""
        return self._shared

    def reply_languages(self, user_locale: str | None) -> tuple[str, ...]:
        """Return the user's matched language, the instance's first when none matches, or all of them when none is named."""
        if user_locale is None or not user_locale.strip():
            return self._shared
        matched = self._match(user_locale.strip())
        return (matched,) if matched is not None else self._shared[:1]

    def _match(self, user_locale: str) -> str | None:
        wanted = user_locale.casefold()
        for language in self._supported:
            if language.casefold() == wanted:
                return language
        primary = wanted.split("-", 1)[0]
        for language in self._supported:
            if language.casefold().split("-", 1)[0] == primary:
                return language
        return None

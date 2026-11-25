"""The instance language policy and the message in several languages (decisions/languages.md).

Translation (a key and a language to a text) is the translator's job
(decisions/i18n.md). Which languages a message uses is the instance's policy:
a shared or generic message uses the instance's configured languages in their
order; a direct interaction uses the user's language of choice. Features ask
the policy through ``LanguagePolicy``, which the host provides, and hand a
``MultilingualText`` to the platform, which lays it out
(decisions/platform-transports.md, outbound messages are intents).

Languages are IETF language tags (``en-US``, ``fr-FR``).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, Self, runtime_checkable

from contracts.workplace import WorkplaceSystem


@dataclass(frozen=True)
class MultilingualText:
    """One message in one or more languages: each part is a language and its text, in display order.

    It carries the bot's own catalogue wording; text the bot forwards or
    generates keeps its source language and is not repeated per language.
    """

    parts: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not self.parts:
            raise ValueError("a multilingual text needs at least one language")
        seen: set[str] = set()
        for language, _ in self.parts:
            if language in seen:
                raise ValueError(f"language {language} appears more than once")
            seen.add(language)

    @classmethod
    def of(cls, languages: Sequence[str], line: Callable[[str], str]) -> Self:
        """Render ``line`` once per language, keeping the order of ``languages``."""
        return cls(tuple((language, line(language)) for language in languages))

    def plain_text(self) -> str:
        """Each language's text on its own line, in order: the layout every platform can show."""
        return "\n".join(text for _, text in self.parts)


@runtime_checkable
class LanguagePolicy(Protocol):
    """Which languages a message uses on this instance."""

    def shared_languages(self, *, system: WorkplaceSystem, tenant: str, conversation_id: str) -> tuple[str, ...]:
        """Return the languages, in order, of a message posted to a shared conversation."""
        ...

    def reply_languages(self, user_locale: str | None) -> tuple[str, ...]:
        """Return the languages of a direct reply to a user whose platform names ``user_locale``.

        The user's language when the app supports it (matched on its primary
        language subtag); the instance's first language when it does not; the
        instance's languages when the request names none.
        """
        ...

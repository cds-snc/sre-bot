"""The translator contract: a catalogue key and a language in, the wording out.

Features and capabilities depend on this contract, resolved from the service registry,
never on the catalogue package (decisions/i18n.md). Catalogues stay in each package's
``locales/`` and register through the ``register_i18n_resources`` hookspec.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class Translator(Protocol):
    """Translate a catalogue key into one language."""

    def translate(self, key: str, language: str, /, **variables: str) -> str:
        """Return the key's wording in ``language`` with ``variables`` substituted.

        A key or language the catalogues do not hold returns the key itself, so a
        missing entry never fails the message it was wording.
        """
        ...

"""Translator adapter: the incident umbrella's one import of ``infrastructure.i18n``.

Views reach the translator through ``core.api.translate`` so each subdomain can
own its own views module without a further import-linter ignore entry.
"""

from typing import Any

from infrastructure.i18n import t


def translate(key: str, locale: str, fallback: str = "", **variables: Any) -> str:
    """Translate ``key`` for ``locale`` with ``variables`` substituted.

    Returns ``fallback`` when the key is missing from both catalogues or the
    translation service is not ready, so callers never guard the lookup.
    """
    return t(key, locale, fallback, **variables)

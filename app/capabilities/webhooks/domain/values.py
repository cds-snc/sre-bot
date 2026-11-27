"""Hygiene for values taken from an untrusted payload: text neutralisation and https link URLs.

Text is NFC-normalised and stripped of characters that change how it reads without being
seen: control characters other than newline and tab, bidirectional controls (Trojan Source,
CVE-2021-42574), format characters such as zero-width ones, and the default-ignorable fillers.
This is not output encoding: the platform adapter still escapes every value it posts
(decisions/webhooks.md Security additions).

A link URL is parsed, refused when ambiguous (userinfo, no host, a non-https scheme, spaces or
control characters, over the length limit) and rebuilt from its parts with the host in
punycode and every character outside the URL's safe set percent-encoded, so no platform link
delimiter (``|``, ``<``, ``>``) survives (OWASP Unvalidated Redirects and Forwards).
"""

import unicodedata
from collections.abc import Collection
from urllib.parse import quote, urlsplit

ELLIPSIS = "…"

# Default-ignorable code points outside the Cf category that render as blank or nothing.
_INVISIBLE_FILLERS = frozenset({"͏", "ᅟ", "ᅠ", "ㅤ", "ﾠ"})
_REMOVED_CATEGORIES = frozenset({"Cc", "Cf", "Cs"})
_KEPT_CONTROLS = frozenset({"\n", "\t"})

_PATH_SAFE = "/%:@!$&'()*+,;=-._~"
_QUERY_SAFE = _PATH_SAFE + "?"


def neutralise_text(text: str) -> str:
    """Return ``text`` NFC-normalised, without invisible or direction-changing characters."""
    normalised = unicodedata.normalize("NFC", text)
    return "".join(
        character
        for character in normalised
        if character in _KEPT_CONTROLS
        or (unicodedata.category(character) not in _REMOVED_CATEGORIES and character not in _INVISIBLE_FILLERS)
    )


def truncate(text: str, limit: int) -> str:
    """Return ``text`` cut to ``limit`` characters, the last one an ellipsis when cut."""
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)] + ELLIPSIS


def normalise_https_url(raw: str, *, max_chars: int, allowed_hosts: Collection[str] = ()) -> str | None:
    """Return ``raw`` as a safe https URL, or None when it is ambiguous or not allowed.

    ``allowed_hosts``, when given, lists the punycode hosts the URL may point at, exactly.
    """
    if not raw or len(raw) > max_chars:
        return None
    if any(character.isspace() or unicodedata.category(character) in _REMOVED_CATEGORIES for character in raw):
        return None
    try:
        parts = urlsplit(raw)
        port = parts.port
        hostname = parts.hostname
    except ValueError:
        return None
    if parts.scheme.lower() != "https" or parts.username is not None or parts.password is not None or not hostname:
        return None
    try:
        host = hostname.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None
    if allowed_hosts and host not in allowed_hosts:
        return None
    authority = host if port is None else f"{host}:{port}"
    url = f"https://{authority}{quote(parts.path, safe=_PATH_SAFE) or ''}"
    if parts.query:
        url += "?" + quote(parts.query, safe=_QUERY_SAFE)
    if parts.fragment:
        url += "#" + quote(parts.fragment, safe=_QUERY_SAFE)
    return url if len(url) <= max_chars else None

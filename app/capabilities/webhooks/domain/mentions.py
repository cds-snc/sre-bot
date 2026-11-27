"""Find email addresses in untrusted text, in linear time and with no regular expression.

The text is split on whitespace; each token is trimmed of surrounding punctuation and checked
character by character against the address shape (RFC 5321 lengths: 64 for the local part,
254 in all). The finder stops after ``limit`` distinct addresses, so a message never asks a
platform for more lookups than the cap (decisions/security.md Request limits; the
linear-processing rule in decisions/webhooks.md).
"""

import string

MAX_LOCAL_PART = 64
MAX_ADDRESS = 254
MAX_LABEL = 63

_LOCAL_CHARACTERS = frozenset(string.ascii_letters + string.digits + "._%+-")
_LABEL_CHARACTERS = frozenset(string.ascii_letters + string.digits + "-")
_TRIM = "\"'()[]<>{},;:!?."


def find_email_addresses(text: str, limit: int) -> tuple[str, ...]:
    """Return up to ``limit`` distinct addresses in ``text``, in order, their domains in lowercase."""
    found: list[str] = []
    seen: set[str] = set()
    for token in text.split():
        if len(found) >= limit:
            break
        if len(token) > MAX_ADDRESS + len(_TRIM) or "@" not in token:
            continue
        address = _address(token.strip(_TRIM))
        if address is not None and address not in seen:
            seen.add(address)
            found.append(address)
    return tuple(found)


def _address(token: str) -> str | None:
    if len(token) > MAX_ADDRESS or token.count("@") != 1:
        return None
    local, domain = token.split("@")
    if not 0 < len(local) <= MAX_LOCAL_PART or not set(local) <= _LOCAL_CHARACTERS:
        return None
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return None
    labels = domain.split(".")
    if len(labels) < 2:
        return None
    for label in labels:
        if not 0 < len(label) <= MAX_LABEL or not set(label) <= _LABEL_CHARACTERS:
            return None
        if label.startswith("-") or label.endswith("-"):
            return None
    top = labels[-1]
    if len(top) < 2 or not top.isascii() or not top.isalpha():
        return None
    return f"{local}@{domain.lower()}"

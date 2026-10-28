"""Throwaway Google service-account keys for tests.

A key is a fresh RSA key in the JSON shape the Google console downloads, so
google-auth builds real credentials from it with no network call. Nothing is ever
signed against Google with it.
"""

import json
from functools import cache
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

CLIENT_EMAIL = "sre-bot-test@sre-bot-test.iam.gserviceaccount.com"


@cache
def _private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def service_account_info(**overrides: Any) -> dict[str, Any]:
    """The key as a mapping; an override set to None removes that field."""
    info: dict[str, Any] = {
        "type": "service_account",
        "project_id": "sre-bot-test",
        "private_key_id": "0123456789abcdef",
        "private_key": _private_key_pem(),
        "client_email": CLIENT_EMAIL,
        "client_id": "123456789012345678901",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    info.update(overrides)
    return {name: value for name, value in info.items() if value is not None}


def service_account_key(**overrides: Any) -> str:
    """The key as the JSON text GOOGLE_WORKSPACE__TENANT__SERVICE_ACCOUNT_KEY holds."""
    return json.dumps(service_account_info(**overrides))


def private_key_body() -> str:
    """A line from inside the PEM body, to assert the key never appears in a message or a log."""
    return _private_key_pem().splitlines()[5]

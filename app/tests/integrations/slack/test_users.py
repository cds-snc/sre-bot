from unittest.mock import MagicMock

from integrations.slack import users


def test_get_user_id_from_request_with_user_id():
    body = {"user_id": "U00AAAAAAA0"}
    assert users.get_user_id_from_request(body) == "U00AAAAAAA0"


def test_get_user_id_from_request_with_id():
    body = {"user": {"id": "U00AAAAAAA0"}}
    assert users.get_user_id_from_request(body) == "U00AAAAAAA0"


def test_get_user_id_from_request_without_id():
    body = {"user": "U00AAAAAAA0"}
    assert users.get_user_id_from_request(body) == "U00AAAAAAA0"


def test_get_user_id_from_event_request():
    body = {"event": {"user": "U00AAAAAAA0"}}
    assert users.get_user_id_from_request(body) == "U00AAAAAAA0"


def test_get_user_id_from_invalid_request():
    body = {"invalid": "invalid"}
    assert users.get_user_id_from_request(body) is None


def test_get_user_locale_supported_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {
        "ok": True,
        "user": {"id": "U00AAAAAAA0", "locale": "fr-FR"},
    }
    assert users.get_user_locale(client, user_id) == "fr-FR"


def test_get_user_locale_unsupported_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {
        "ok": True,
        "user": {"id": "U00AAAAAAA0", "locale": "es-ES"},
    }
    assert users.get_user_locale(client, user_id) == "en-US"


def test_get_user_locale_without_locale():
    client = MagicMock()
    user_id = MagicMock()
    client.users_info.return_value = {"ok": False}
    assert users.get_user_locale(client, user_id) == "en-US"


def test_get_user_locale_without_user_id():
    client = MagicMock()
    user_id = None
    assert users.get_user_locale(client, user_id) == "en-US"

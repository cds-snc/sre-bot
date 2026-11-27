"""Tests for the legacy SNS pattern's ``revoke_api_key``: one revocation through the Notify client.

The pattern module's ``get_notify_settings`` returns a real ``NotifySettings`` built with
``model_construct``, and ``httpx.AsyncHTTPTransport`` (the SDK edge) is replaced by an
``httpx.MockTransport``, so the real Notify client runs and each test answers the HTTP edge and
reads the request Notify would receive. Events are captured with structlog's
``capture_logs`` so the tests can assert that the leaked token never reaches a log event.
"""

from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from structlog.testing import capture_logs

from integrations.notify.settings import NotifySettings, NotifyTenant
from modules.webhooks.patterns.aws_sns_notification import api_key_detected

API_URL = "https://notify.example.test"
SERVICE_ID = "00000000-0000-0000-0000-000000000001"
KEY_ID = "00000000-0000-0000-0000-000000000002"
# Assembled at runtime so the source holds no literal in Notify's key layout (secret scanning).
TOKEN = f"gcntfy-leaked-key-{SERVICE_ID}-{KEY_ID}"
ARGS = (TOKEN, "cds_test_type", "https://github.com/example/repo/blob/main/x.txt", "content")
NAMES = {"key_name": "leaked-key", "service_id": SERVICE_ID}


def _settings(tenant: NotifyTenant | None = NotifyTenant(api_url=API_URL)) -> NotifySettings:
    return NotifySettings.model_construct(
        tenant=tenant,
        sre_user_name=SecretStr("sre-client" if tenant else ""),
        sre_client_secret=SecretStr("sre-secret-of-enough-length-000000" if tenant else ""),
        timeout_seconds=60.0,
        connect_retries=2,
    )


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    answer: Callable[[httpx.Request], httpx.Response],
    settings: NotifySettings | None = None,
) -> list[httpx.Request]:
    received: list[httpx.Request] = []
    given = settings or _settings()

    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return answer(request)

    def mock_transport(**_: Any) -> httpx.MockTransport:
        return httpx.MockTransport(handler)

    monkeypatch.setattr(api_key_detected, "get_notify_settings", lambda: given)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", mock_transport)
    return received


def _timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("slow", request=request)


def _bug(request: httpx.Request) -> httpx.Response:
    raise KeyError("bug")


@pytest.mark.parametrize(
    ("status_code", "outcome", "event"),
    [
        (201, "revoked", "revoke_api_key_success"),
        (200, "not_found", "revoke_api_key_not_found"),
        (202, "error", "revoke_api_key_error"),
    ],
)
def test_notify_answers_map_to_the_three_outcomes(
    monkeypatch: pytest.MonkeyPatch, status_code: int, outcome: str, event: str
) -> None:
    """201 revoked the key, 200 found none; any other success code is not a documented answer."""
    _wire(monkeypatch, lambda request: httpx.Response(status_code, json={"result": "ok"}))

    with capture_logs() as entries:
        assert api_key_detected.revoke_api_key(*ARGS, **NAMES) == outcome

    assert [entry["event"] for entry in entries] == [event]


@pytest.mark.parametrize(
    ("answer", "error_code"),
    [
        (lambda request: httpx.Response(400, json={"result": "error"}), "HTTP_ERROR"),
        (lambda request: httpx.Response(500), "SERVER_ERROR"),
        (_timeout, "TIMEOUT"),
    ],
    ids=["invalid-payload", "server-error", "timeout"],
)
def test_a_classified_failure_is_an_error_outcome(
    monkeypatch: pytest.MonkeyPatch, answer: Callable[[httpx.Request], httpx.Response], error_code: str
) -> None:
    _wire(monkeypatch, answer)

    with capture_logs() as entries:
        assert api_key_detected.revoke_api_key(*ARGS, **NAMES) == "error"

    assert [(entry["event"], entry["error_code"]) for entry in entries] == [("revoke_api_key_error", error_code)]


def test_the_request_posts_the_report_to_the_revoke_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    received = _wire(monkeypatch, lambda request: httpx.Response(201, json={"result": "ok"}))

    api_key_detected.revoke_api_key(*ARGS, **NAMES)

    (request,) = received
    assert (request.method, str(request.url)) == ("POST", f"{API_URL}/sre-tools/api-key-revoke")
    assert request.headers["Content-Type"] == "application/json"
    assert request.headers["Authorization"].startswith("Bearer ")
    assert httpx.Response(200, content=request.content).json() == {
        "token": TOKEN,
        "type": "cds_test_type",
        "url": "https://github.com/example/repo/blob/main/x.txt",
        "source": "content",
    }


def test_without_a_tenant_nothing_is_sent(monkeypatch: pytest.MonkeyPatch) -> None:
    received = _wire(monkeypatch, lambda request: httpx.Response(201), settings=_settings(tenant=None))

    with capture_logs() as entries:
        assert api_key_detected.revoke_api_key(*ARGS, **NAMES) == "error"

    assert received == []
    assert [entry["event"] for entry in entries] == ["revoke_api_key_not_configured"]


def test_an_unexpected_exception_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bug in the request path is not classified into an outcome."""
    _wire(monkeypatch, _bug)

    with pytest.raises(KeyError):
        api_key_detected.revoke_api_key(*ARGS, **NAMES)


@pytest.mark.parametrize("status_code", [201, 200, 500])
def test_the_token_never_reaches_a_log_event(monkeypatch: pytest.MonkeyPatch, status_code: int) -> None:
    """The events name the key by its name and service, never by its value (OWASP: exclude tokens)."""
    _wire(monkeypatch, lambda request: httpx.Response(status_code, json={"result": "ok"}))

    with capture_logs() as entries:
        api_key_detected.revoke_api_key(*ARGS, **NAMES)

    assert entries
    assert all(TOKEN not in repr(entry) for entry in entries)
    assert {(entry["api_key_name"], entry["service_id"]) for entry in entries} == {(NAMES["key_name"], NAMES["service_id"])}


def test_an_unparsed_report_logs_its_length_not_its_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """A report the pattern cannot parse still carries the token, so only its length is logged."""
    payload = type("Payload", (), {"Message": f"API Key with value token='{TOKEN}' in an unknown layout"})()

    with capture_logs() as entries:
        assert api_key_detected.handle_api_key_detected(payload, client=None) == []  # type: ignore[arg-type]

    assert [entry["event"] for entry in entries] == ["failed_to_parse_api_key_detection_message"]
    assert entries[0]["message_length"] == len(payload.Message)
    assert TOKEN not in repr(entries)

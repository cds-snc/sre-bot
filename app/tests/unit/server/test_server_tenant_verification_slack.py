"""Unit tests for the host tenant verifier: Slack auth.test judged by the inbound tenant rule.

The Slack settings provider read by server.tenant_verification is replaced with
settings built by model_construct, and the Web client factory with a fake whose
auth_test returns a real SlackResponse or raises a real SlackApiError, so no
token, environment or network is needed. classify_slack_error runs unchanged on
the test settings. The tests assert the verdict check_slack_tenant gives for each
id combination, the classified status of a failed call, that no call is made for
an unconfigured or unsupported system, and that neither the token nor the
exception text reaches the result or the logs.
"""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import SecretStr
from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import TenantVerifier, WorkplaceSystem
from integrations.slack.settings import SlackSettings, SlackTenant
from server.tenant_verification import HostTenantVerifier

pytestmark = pytest.mark.unit

TOKEN = "xoxb-never-shown"


def _response(data: dict[str, Any], *, headers: dict[str, str] | None = None, status_code: int = 200) -> SlackResponse:
    return SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/auth.test",
        req_args={},
        data=data,
        headers=headers or {},
        status_code=status_code,
    )


def _slack_error(code: str, *, headers: dict[str, str] | None = None, status_code: int = 200) -> SlackApiError:
    return SlackApiError(
        f"failed with {TOKEN} (error: {code})", _response({"ok": False, "error": code}, headers=headers, status_code=status_code)
    )


class _FakeClient:
    def __init__(self, outcome: SlackResponse | Exception) -> None:
        self._outcome = outcome
        self.calls = 0

    def auth_test(self) -> SlackResponse:
        self.calls += 1
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


@pytest.fixture
def configure(monkeypatch: pytest.MonkeyPatch) -> Callable[[SlackTenant | None, SlackResponse | Exception], _FakeClient]:
    def _configure(tenant: SlackTenant | None, outcome: SlackResponse | Exception) -> _FakeClient:
        settings = SlackSettings.model_construct(tenant=tenant, bot_token=SecretStr(TOKEN))
        client = _FakeClient(outcome)
        monkeypatch.setattr("server.tenant_verification.get_slack_settings", lambda: settings)
        monkeypatch.setattr("server.tenant_verification.get_slack_web_client", lambda: client)
        return client

    return _configure


def _auth(team_id: str | None, enterprise_id: str | None) -> SlackResponse:
    return _response({"ok": True, "team_id": team_id, "enterprise_id": enterprise_id, "user_id": "UBOT"})


def test_the_host_verifier_satisfies_the_protocol() -> None:
    verifier: TenantVerifier = HostTenantVerifier()

    assert isinstance(verifier, HostTenantVerifier)


@pytest.mark.parametrize(
    ("tenant", "team_id", "enterprise_id", "expected"),
    [
        (SlackTenant(team_id="T0123"), "T0123", None, "T0123"),
        (SlackTenant(enterprise_id="E0123"), "T0999", "E0123", "E0123"),
        (SlackTenant(team_id="T0123", enterprise_id="E0123"), "T0123", "E0123", "E0123"),
    ],
    ids=["team-only", "enterprise-only", "both"],
)
def test_a_matching_auth_test_returns_the_configured_tenant_id(
    configure: Callable[..., _FakeClient], tenant: SlackTenant, team_id: str, enterprise_id: str | None, expected: str
) -> None:
    configure(tenant, _auth(team_id, enterprise_id))

    result = HostTenantVerifier().verified_tenant(WorkplaceSystem.SLACK)

    assert result.is_success
    assert result.data == expected


@pytest.mark.parametrize(
    ("tenant", "team_id", "enterprise_id"),
    [
        (SlackTenant(team_id="T0123"), "T0999", None),
        (SlackTenant(team_id="T0123", enterprise_id="E0123"), "T0123", "E0999"),
        (SlackTenant(team_id="T0123"), "T0123", "E0777"),
    ],
    ids=["team-mismatch", "enterprise-mismatch", "unnamed-enterprise-org"],
)
def test_a_mismatch_is_unauthorized_naming_the_expected_and_received_ids(
    configure: Callable[..., _FakeClient], tenant: SlackTenant, team_id: str, enterprise_id: str | None
) -> None:
    configure(tenant, _auth(team_id, enterprise_id))

    with capture_logs() as logs:
        result = HostTenantVerifier().verified_tenant(WorkplaceSystem.SLACK)

    assert result.status is OperationStatus.UNAUTHORIZED
    assert result.error_code == ErrorCode.TENANT_MISMATCH
    message = result.message or ""
    assert f"expected team_id={tenant.team_id} enterprise_id={tenant.enterprise_id}" in message
    assert f"received team_id={team_id} enterprise_id={enterprise_id}" in message
    assert [entry["log_level"] for entry in logs if entry["event"] == "tenant_verification_mismatch"] == ["warning"]


@pytest.mark.parametrize("blank", ["", "  ", 42])
def test_blank_or_non_string_ids_from_auth_test_count_as_absent(configure: Callable[..., _FakeClient], blank: object) -> None:
    configure(SlackTenant(team_id="T0123"), _response({"ok": True, "team_id": "T0123", "enterprise_id": blank}))

    result = HostTenantVerifier().verified_tenant(WorkplaceSystem.SLACK)

    assert result.data == "T0123"


@pytest.mark.parametrize(
    ("error", "status", "retry_after"),
    [
        (_slack_error("invalid_auth"), OperationStatus.UNAUTHORIZED, None),
        (_slack_error("ratelimited", headers={"Retry-After": "7"}, status_code=429), OperationStatus.TRANSIENT_ERROR, 7),
        (_slack_error("channel_not_found"), OperationStatus.NOT_FOUND, None),
        (_slack_error("something_new"), OperationStatus.PERMANENT_ERROR, None),
        (RuntimeError(f"socket closed while sending {TOKEN}"), OperationStatus.PERMANENT_ERROR, None),
    ],
    ids=["unauthorized", "rate-limited", "not-found", "unclassified-slack-code", "unclassified-exception"],
)
def test_a_failed_auth_test_returns_the_classified_status_without_the_token(
    configure: Callable[..., _FakeClient], error: Exception, status: OperationStatus, retry_after: int | None
) -> None:
    configure(SlackTenant(team_id="T0123"), error)

    with capture_logs() as logs:
        result = HostTenantVerifier().verified_tenant(WorkplaceSystem.SLACK)

    assert result.status is status
    assert result.error_code == ErrorCode.TENANT_CHECK_FAILED
    assert result.retry_after == retry_after
    assert TOKEN not in (result.message or "")
    assert TOKEN not in repr(logs)


def test_no_slack_tenant_entry_is_not_configured_and_makes_no_call(configure: Callable[..., _FakeClient]) -> None:
    client = configure(None, _auth("T0123", None))

    result = HostTenantVerifier().verified_tenant(WorkplaceSystem.SLACK)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.CONFIG_NOT_CONFIGURED
    assert client.calls == 0


def test_google_is_unsupported_and_makes_no_call(configure: Callable[..., _FakeClient]) -> None:
    client = configure(SlackTenant(team_id="T0123"), _auth("T0123", None))

    result = HostTenantVerifier().verified_tenant(WorkplaceSystem.GOOGLE)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.UNSUPPORTED_OPERATION
    assert client.calls == 0

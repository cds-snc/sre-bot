"""Behavior tests for ``classify_slack_error``.

Each expected Slack Web API error family is mapped onto the closed
``OperationStatus`` set using the code catalogues and the transient retry hint
from ``integrations.slack.settings``; anything unexpected propagates
unchanged. Errors are real ``SlackApiError`` objects carrying real
``SlackResponse`` payloads and headers, as slack_sdk raises them. Overrides
go through environment variables plus the autouse provider cache clear, so
the tests prove settings are read at classification time.
"""

import pytest
from slack_sdk.errors import SlackApiError
from slack_sdk.web.slack_response import SlackResponse

from contracts.operations.status import OperationStatus
from integrations.slack.client import classify_slack_error

pytestmark = pytest.mark.unit


def _slack_error(code: str, *, headers: dict[str, str] | None = None, status_code: int = 200) -> SlackApiError:
    response = SlackResponse(
        client=None,
        http_verb="POST",
        api_url="https://slack.com/api/usergroups.users.update",
        req_args={},
        data={"ok": False, "error": code},
        headers=headers or {},
        status_code=status_code,
    )
    return SlackApiError(f"The request to the Slack API failed. (error: {code})", response)


class TestMappedFamilies:
    """Expected Slack error codes map to a status, the code and a retry hint."""

    @pytest.mark.parametrize("code", ["not_authed", "invalid_auth", "token_revoked", "missing_scope", "not_allowed_token_type"])
    def test_unauthorized_codes(self, code: str) -> None:
        assert classify_slack_error(_slack_error(code)) == (OperationStatus.UNAUTHORIZED, code, None)

    @pytest.mark.parametrize("code", ["channel_not_found", "user_not_found", "users_not_found", "no_such_subteam"])
    def test_not_found_codes(self, code: str) -> None:
        assert classify_slack_error(_slack_error(code)) == (OperationStatus.NOT_FOUND, code, None)

    @pytest.mark.parametrize("code", ["internal_error", "fatal_error", "service_unavailable", "request_timeout"])
    def test_transient_codes_carry_the_default_retry_hint(self, code: str) -> None:
        assert classify_slack_error(_slack_error(code)) == (OperationStatus.TRANSIENT_ERROR, code, 30)

    def test_rate_limit_honours_the_retry_after_header(self) -> None:
        error = _slack_error("ratelimited", headers={"Retry-After": "7"}, status_code=429)

        assert classify_slack_error(error) == (OperationStatus.TRANSIENT_ERROR, "ratelimited", 7)

    def test_retry_after_header_name_is_case_insensitive(self) -> None:
        error = _slack_error("ratelimited", headers={"retry-after": "12"}, status_code=429)

        assert classify_slack_error(error) == (OperationStatus.TRANSIENT_ERROR, "ratelimited", 12)

    def test_unparseable_retry_after_falls_back_to_the_default_hint(self) -> None:
        error = _slack_error("ratelimited", headers={"Retry-After": "soon"}, status_code=429)

        assert classify_slack_error(error) == (OperationStatus.TRANSIENT_ERROR, "ratelimited", 30)


class TestSettingsOverrides:
    """Catalogues and the default retry hint are read from settings at call time."""

    def test_catalogue_override_reclassifies_a_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_NOT_FOUND_ERRORS", '["invalid_users"]')

        assert classify_slack_error(_slack_error("invalid_users")) == (OperationStatus.NOT_FOUND, "invalid_users", None)

    def test_default_retry_hint_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_TRANSIENT_RETRY_AFTER_SECONDS", "90")

        assert classify_slack_error(_slack_error("internal_error")) == (OperationStatus.TRANSIENT_ERROR, "internal_error", 90)


class TestPropagation:
    """Anything the catalogues do not name is re-raised unchanged."""

    def test_unmapped_slack_error_code_propagates(self) -> None:
        error = _slack_error("invalid_arguments")

        with pytest.raises(SlackApiError) as excinfo:
            classify_slack_error(error)

        assert excinfo.value is error

    def test_non_slack_exception_propagates(self) -> None:
        error = KeyError("usergroup")

        with pytest.raises(KeyError) as excinfo:
            classify_slack_error(error)

        assert excinfo.value is error

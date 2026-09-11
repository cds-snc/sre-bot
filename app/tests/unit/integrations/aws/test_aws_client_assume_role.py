"""Behavior tests for eager AssumeRole in the AWS client factory.

The STS exchange is verified with ``botocore.stub.Stubber`` on a real STS
client, which validates the request against the service model and replays a
canned ``assume_role`` response. The factory wiring is verified with a
recording subclass of ``boto3.session.Session`` (real sessions, no network) so
the test can observe, through public APIs only, that the returned client is
built from a session holding the assumed credentials and that the role was
assumed before the client was handed back.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from integrations.aws import client as aws_client

pytestmark = pytest.mark.unit

_ROLE_ARN = "arn:aws:iam::123456789012:role/sre-bot-org"
_ASSUMED = {
    "AccessKeyId": "ASIAASSUMEDKEY",
    "SecretAccessKey": "assumed-secret",
    "SessionToken": "assumed-token",
    "Expiration": datetime(2030, 1, 1, tzinfo=UTC),
}


def _sts_client() -> Any:
    return boto3.client(
        "sts",
        region_name="ca-central-1",
        aws_access_key_id="static-key",
        aws_secret_access_key="static-secret",
    )


class TestAssumeRoleCredentials:
    """The STS helper exchanges a role ARN for temporary credentials through the public API."""

    def test_returns_the_credentials_from_assume_role(self) -> None:
        sts = _sts_client()
        with Stubber(sts) as stub:
            stub.add_response(
                "assume_role",
                {"Credentials": _ASSUMED},
                expected_params={"RoleArn": _ROLE_ARN, "RoleSessionName": "sre-bot"},
            )

            credentials = aws_client._assume_role_credentials(sts, _ROLE_ARN, "sre-bot")

            stub.assert_no_pending_responses()
        assert credentials["AccessKeyId"] == "ASIAASSUMEDKEY"
        assert credentials["SecretAccessKey"] == "assumed-secret"
        assert credentials["SessionToken"] == "assumed-token"

    def test_forwards_a_custom_session_name(self) -> None:
        sts = _sts_client()
        with Stubber(sts) as stub:
            stub.add_response(
                "assume_role",
                {"Credentials": _ASSUMED},
                expected_params={"RoleArn": _ROLE_ARN, "RoleSessionName": "access-sync"},
            )

            aws_client._assume_role_credentials(sts, _ROLE_ARN, "access-sync")

            stub.assert_no_pending_responses()

    def test_assume_role_failures_propagate_as_sdk_errors(self) -> None:
        sts = _sts_client()
        with Stubber(sts) as stub:
            stub.add_client_error("assume_role", service_error_code="AccessDenied", http_status_code=403)

            with pytest.raises(ClientError) as excinfo:
                aws_client._assume_role_credentials(sts, _ROLE_ARN, "sre-bot")

        assert excinfo.value.response["Error"]["Code"] == "AccessDenied"


class TestFactoryWiring:
    """``get_aws_client`` assumes the role eagerly and builds the client on the assumed session."""

    @pytest.fixture
    def recorded_sessions(self, monkeypatch: pytest.MonkeyPatch) -> list[boto3.session.Session]:
        sessions: list[boto3.session.Session] = []
        real_session_cls = boto3.session.Session

        class RecordingSession(real_session_cls):  # type: ignore[misc,valid-type]
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                sessions.append(self)

        monkeypatch.setattr(aws_client.boto3, "Session", RecordingSession)
        return sessions

    @pytest.fixture
    def assume_role_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, str, str]]:
        calls: list[tuple[Any, str, str]] = []

        def fake_assume(sts: Any, role_arn: str, session_name: str) -> dict[str, Any]:
            calls.append((sts, role_arn, session_name))
            return dict(_ASSUMED)

        monkeypatch.setattr(aws_client, "_assume_role_credentials", fake_assume)
        return calls

    def test_client_is_built_on_a_session_holding_the_assumed_credentials(
        self,
        recorded_sessions: list[boto3.session.Session],
        assume_role_calls: list[tuple[Any, str, str]],
    ) -> None:
        client = aws_client.get_aws_client("identitystore", role_arn=_ROLE_ARN)

        assert client.meta.service_model.service_name == "identitystore"
        assert len(assume_role_calls) == 1
        assumed_session = recorded_sessions[-1]
        credentials = assumed_session.get_credentials()
        assert credentials is not None
        assert type(credentials).__name__ == "Credentials"
        assert credentials.access_key == "ASIAASSUMEDKEY"
        assert credentials.secret_key == "assumed-secret"
        assert credentials.token == "assumed-token"
        assert assumed_session.region_name == "ca-central-1"

    def test_role_is_assumed_with_the_default_session_name_through_a_configured_sts_client(
        self,
        recorded_sessions: list[boto3.session.Session],
        assume_role_calls: list[tuple[Any, str, str]],
    ) -> None:
        aws_client.get_aws_client("identitystore", role_arn=_ROLE_ARN)

        sts, role_arn, session_name = assume_role_calls[0]
        assert sts.meta.service_model.service_name == "sts"
        assert sts.meta.config.retries == {"mode": "standard", "total_max_attempts": 4}
        assert sts.meta.config.connect_timeout == 10
        assert role_arn == _ROLE_ARN
        assert session_name == "sre-bot"

    def test_custom_session_name_is_forwarded(
        self,
        recorded_sessions: list[boto3.session.Session],
        assume_role_calls: list[tuple[Any, str, str]],
    ) -> None:
        aws_client.get_aws_client("identitystore", role_arn=_ROLE_ARN, session_name="access-sync")

        assert assume_role_calls[0][2] == "access-sync"

    def test_no_role_means_no_assume_role_and_the_ambient_session(
        self,
        recorded_sessions: list[boto3.session.Session],
        assume_role_calls: list[tuple[Any, str, str]],
    ) -> None:
        client = aws_client.get_aws_client("identitystore")

        assert client.meta.service_model.service_name == "identitystore"
        assert assume_role_calls == []
        assert len(recorded_sessions) == 1

    def test_private_credential_injection_is_gone_from_the_module(self) -> None:
        """The refreshable-credential hook that reached into botocore internals is no longer imported."""
        assert not hasattr(aws_client, "DeferredRefreshableCredentials")
        assert not hasattr(aws_client, "create_assume_role_refresher")

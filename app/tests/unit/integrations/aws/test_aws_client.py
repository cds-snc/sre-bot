"""Unit tests for the AWS client factory and error classifier contract.

These tests define the expected behavior for the shared integrations AWS
factory/classifier primitives used by storage and other adapters.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from infrastructure.operations.status import OperationStatus
from integrations.aws import client as aws_client


def _client_error(code: str, message: str = "boom") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": message}},
        operation_name="TestOperation",
    )


@pytest.mark.unit
def test_get_aws_client_applies_native_retry_timeouts_and_endpoint_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeSession:
        def __init__(self, **kwargs):
            captured["session_kwargs"] = kwargs

        def client(self, service_name: str, **kwargs):
            captured["service_name"] = service_name
            captured["client_kwargs"] = kwargs
            return SimpleNamespace(name=service_name)

    class FakeBoto3:
        Session = FakeSession

    settings = SimpleNamespace(
        AWS_REGION="ca-central-1",
        RETRY_MODE="standard",
        RETRY_MAX_ATTEMPTS=4,
        CONNECT_TIMEOUT_SECONDS=2,
        READ_TIMEOUT_SECONDS=7,
    )

    monkeypatch.setattr(aws_client, "boto3", FakeBoto3(), raising=False)
    monkeypatch.setattr(aws_client, "settings", settings, raising=False)
    monkeypatch.setattr(aws_client, "app_settings", SimpleNamespace(ENVIRONMENT="dev"), raising=False)
    monkeypatch.setattr(aws_client, "get_aws_settings", lambda: settings, raising=False)
    monkeypatch.setattr(aws_client, "get_app_settings", lambda: SimpleNamespace(ENVIRONMENT="dev"), raising=False)

    aws_client.get_aws_client("dynamodb")

    assert captured["service_name"] == "dynamodb"
    client_kwargs = captured["client_kwargs"]
    assert isinstance(client_kwargs, dict)
    assert client_kwargs["region_name"] == "ca-central-1"
    assert client_kwargs["endpoint_url"] == "http://dynamodb-local:8000"

    config = client_kwargs["config"]
    assert config.retries == {"max_attempts": 4, "mode": "standard"}
    assert config.connect_timeout == 2
    assert config.read_timeout == 7


@pytest.mark.unit
def test_get_aws_client_does_not_force_local_endpoint_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeSession:
        def __init__(self, **kwargs):
            captured["session_kwargs"] = kwargs

        def client(self, service_name: str, **kwargs):
            captured["service_name"] = service_name
            captured["client_kwargs"] = kwargs
            return SimpleNamespace(name=service_name)

    class FakeBoto3:
        Session = FakeSession

    settings = SimpleNamespace(
        AWS_REGION="ca-central-1",
        RETRY_MODE="standard",
        RETRY_MAX_ATTEMPTS=3,
        CONNECT_TIMEOUT_SECONDS=10,
        READ_TIMEOUT_SECONDS=10,
    )

    monkeypatch.setattr(aws_client, "boto3", FakeBoto3(), raising=False)
    monkeypatch.setattr(aws_client, "settings", settings, raising=False)
    monkeypatch.setattr(aws_client, "app_settings", SimpleNamespace(ENVIRONMENT="production"), raising=False)
    monkeypatch.setattr(aws_client, "get_aws_settings", lambda: settings, raising=False)
    monkeypatch.setattr(aws_client, "get_app_settings", lambda: SimpleNamespace(ENVIRONMENT="production"), raising=False)

    aws_client.get_aws_client("dynamodb")

    client_kwargs = captured["client_kwargs"]
    assert isinstance(client_kwargs, dict)
    assert client_kwargs.get("endpoint_url") is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("error_code", "expected_status", "expected_retry_after"),
    [
        ("ResourceNotFoundException", OperationStatus.NOT_FOUND, None),
        ("AccessDeniedException", OperationStatus.UNAUTHORIZED, None),
        ("UnauthorizedException", OperationStatus.UNAUTHORIZED, None),
        ("Throttling", OperationStatus.TRANSIENT_ERROR, 60),
        ("RequestLimitExceeded", OperationStatus.TRANSIENT_ERROR, 60),
        ("ProvisionedThroughputExceededException", OperationStatus.TRANSIENT_ERROR, 60),
        ("ConditionalCheckFailedException", OperationStatus.PERMANENT_ERROR, None),
    ],
)
def test_classify_aws_error_expected_mappings(
    error_code: str,
    expected_status: OperationStatus,
    expected_retry_after: int | None,
) -> None:
    status, mapped_code, retry_after = aws_client.classify_aws_error(_client_error(error_code))

    assert status is expected_status
    assert mapped_code == error_code
    assert retry_after == expected_retry_after


@pytest.mark.unit
def test_classify_aws_error_propagates_unmapped_exception() -> None:
    with pytest.raises(KeyError):
        aws_client.classify_aws_error(KeyError("unmapped"))

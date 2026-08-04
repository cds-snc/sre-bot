"""Behavior tests for ENVIRONMENT-gated DynamoDB local endpoints."""

import importlib
from types import SimpleNamespace

import pytest

from infrastructure.configuration.app import AppSettings
from integrations.aws import client_next
from integrations.aws import dynamodb as dynamodb_module
from modules.aws import aws_access_requests


@pytest.mark.unit
@pytest.mark.parametrize(
    ("environment", "expected_url"),
    [
        ("local", "http://dynamodb-local:8000"),
        ("dev", "http://dynamodb-local:8000"),
        ("ci", "http://dynamodb-local:8000"),
        ("staging", None),
        ("production", None),
    ],
)
def test_integrations_aws_dynamodb_endpoint_matrix(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    expected_url: str | None,
) -> None:
    """integrations.aws.dynamodb should gate local endpoint by ENVIRONMENT."""

    monkeypatch.setattr(
        "infrastructure.configuration.app.get_app_settings",
        lambda: AppSettings(ENVIRONMENT=environment),
    )
    monkeypatch.setattr(
        "infrastructure.configuration.integrations.aws.get_aws_settings",
        lambda: SimpleNamespace(AWS_REGION="ca-central-1"),
    )

    reloaded = importlib.reload(dynamodb_module)

    assert reloaded.client_config.get("endpoint_url") == expected_url


@pytest.mark.unit
@pytest.mark.parametrize(
    ("environment", "expected_url"),
    [
        ("local", "http://dynamodb-local:8000"),
        ("dev", "http://dynamodb-local:8000"),
        ("ci", "http://dynamodb-local:8000"),
        ("staging", None),
        ("production", None),
    ],
)
def test_integrations_aws_client_next_dynamodb_endpoint_matrix(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    expected_url: str | None,
) -> None:
    """integrations.aws.client_next.get_aws_client should gate by ENVIRONMENT."""

    captured: dict[str, object] = {}

    class FakeSession:
        def __init__(self, **kwargs):
            captured["session_kwargs"] = kwargs

        def client(self, service_name, **client_config):
            captured["service_name"] = service_name
            captured["client_config"] = client_config
            return SimpleNamespace()

    class FakeBoto3:
        Session = FakeSession

    monkeypatch.setattr(client_next, "boto3", FakeBoto3())
    monkeypatch.setattr(
        client_next,
        "app_settings",
        SimpleNamespace(ENVIRONMENT=environment),
        raising=False,
    )
    monkeypatch.setattr(client_next, "settings", SimpleNamespace(PREFIX=""))

    client_next.get_aws_client("dynamodb")

    client_config = captured.get("client_config", {})
    assert isinstance(client_config, dict)
    assert client_config.get("endpoint_url") == expected_url


@pytest.mark.unit
@pytest.mark.parametrize(
    ("environment", "expected_url"),
    [
        ("local", "http://dynamodb-local:8000"),
        ("dev", "http://dynamodb-local:8000"),
        ("ci", "http://dynamodb-local:8000"),
        ("staging", None),
        ("production", None),
    ],
)
def test_modules_aws_access_requests_dynamodb_endpoint_matrix(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    expected_url: str | None,
) -> None:
    """modules.aws.aws_access_requests._get_dynamodb_client should gate by ENVIRONMENT."""

    captured: dict[str, object] = {}

    def fake_client(service_name: str, **kwargs):
        captured["service_name"] = service_name
        captured["kwargs"] = kwargs
        return SimpleNamespace()

    monkeypatch.setattr(aws_access_requests.boto3, "client", fake_client)
    monkeypatch.setattr(
        aws_access_requests,
        "get_app_settings",
        lambda: SimpleNamespace(ENVIRONMENT=environment, PREFIX=""),
    )

    aws_access_requests._get_dynamodb_client()

    kwargs = captured.get("kwargs", {})
    assert isinstance(kwargs, dict)
    assert kwargs.get("endpoint_url") == expected_url

"""Behavior tests for ENVIRONMENT-gated DynamoDB local endpoints."""

import importlib
from types import SimpleNamespace

import pytest

from infrastructure.configuration.app import AppSettings
from integrations.aws import dynamodb as dynamodb_module


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

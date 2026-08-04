"""Fixtures for DynamoDBStorageService integration tests."""

from collections.abc import Iterator
from typing import Any

import pytest

from infrastructure.storage.service import DynamoDBStorageService
from integrations.aws import client as aws_client
from integrations.aws.client import AWS_REGION

STORAGE_TEST_TABLE_NAME = "test-sre-bot-storage-service"


def _set_moto_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy AWS credentials so moto never touches real AWS."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", AWS_REGION)
    monkeypatch.setattr(aws_client.app_settings, "ENVIRONMENT", "test")


def _create_storage_table(client: Any) -> None:
    client.create_table(
        TableName=STORAGE_TEST_TABLE_NAME,
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def storage_service(monkeypatch: pytest.MonkeyPatch) -> Iterator[DynamoDBStorageService]:
    moto = pytest.importorskip("moto")
    boto3 = pytest.importorskip("boto3")
    _set_moto_aws_credentials(monkeypatch)

    with moto.mock_aws():
        client = boto3.client("dynamodb", region_name=AWS_REGION)
        _create_storage_table(client)
        yield DynamoDBStorageService(dynamodb=client)

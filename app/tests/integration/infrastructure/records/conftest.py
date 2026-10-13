"""Fixtures for DynamoDBRecordStore integration tests."""

from collections.abc import Iterator
from typing import Any

import pytest

from infrastructure.records.service import DynamoDBRecordStore
from integrations.aws import client as aws_client
from integrations.aws.settings import get_aws_settings

RECORDS_TEST_TABLE_NAME = "test-sre-bot-record-store"


def _set_moto_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy AWS credentials so moto never touches real AWS."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", get_aws_settings().AWS_REGION)
    monkeypatch.delenv("AWS_ENDPOINT_URL_DYNAMODB", raising=False)
    aws_client.get_aws_settings.cache_clear()


def _create_records_table(client: Any) -> None:
    client.create_table(
        TableName=RECORDS_TEST_TABLE_NAME,
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
def record_store(monkeypatch: pytest.MonkeyPatch) -> Iterator[DynamoDBRecordStore]:
    moto = pytest.importorskip("moto")
    boto3 = pytest.importorskip("boto3")
    _set_moto_aws_credentials(monkeypatch)

    with moto.mock_aws():
        client = boto3.client("dynamodb", region_name=get_aws_settings().AWS_REGION)
        _create_records_table(client)
        yield DynamoDBRecordStore(dynamodb=client)

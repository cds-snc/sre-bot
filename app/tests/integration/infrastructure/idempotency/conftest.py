"""Fixtures for idempotency integration tests."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from infrastructure.idempotency.in_memory import InMemoryIdempotencyStore
from infrastructure.idempotency.settings import IdempotencySettings

from infrastructure.idempotency.dynamodb import DynamoDBIdempotencyStore

STORE_TEST_TABLE_NAME = "test-sre-bot-idempotency-store"


@pytest.fixture
def mock_settings():
    """Create mock IdempotencySettings for idempotency integration tests."""
    mock = MagicMock(spec=IdempotencySettings)
    mock.IDEMPOTENCY_TTL_SECONDS = 3600
    return mock


def _set_moto_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy AWS credentials so moto never touches real AWS."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


def _create_store_table(client: Any) -> None:
    client.create_table(
        TableName=STORE_TEST_TABLE_NAME,
        KeySchema=[{"AttributeName": "idempotency_key", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "idempotency_key", "AttributeType": "S"}
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def idempotency_store_settings() -> IdempotencySettings:
    """Narrow IdempotencySettings slice for IdempotencyStore Protocol implementations."""
    return IdempotencySettings(
        IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300
    )


@pytest.fixture
def expiring_idempotency_store_settings() -> IdempotencySettings:
    """Settings with an already-elapsed in-progress TTL.

    Used to simulate a crashed-claimant takeover deterministically, without any
    real sleep: any claim made under this fixture immediately looks expired to
    a subsequent claim.
    """
    return IdempotencySettings(
        IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=-1
    )


@pytest.fixture
def in_memory_idempotency_store(idempotency_store_settings: IdempotencySettings) -> Any:
    return InMemoryIdempotencyStore(idempotency_settings=idempotency_store_settings)


@pytest.fixture
def expiring_in_memory_idempotency_store(
    expiring_idempotency_store_settings: IdempotencySettings,
) -> Any:
    return InMemoryIdempotencyStore(
        idempotency_settings=expiring_idempotency_store_settings
    )


@pytest.fixture
def dynamodb_idempotency_store(
    idempotency_store_settings: IdempotencySettings, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    moto = pytest.importorskip("moto")
    boto3 = pytest.importorskip("boto3")
    _set_moto_aws_credentials(monkeypatch)

    with moto.mock_aws():
        _create_store_table(boto3.client("dynamodb", region_name="us-east-1"))

        yield DynamoDBIdempotencyStore(
            idempotency_settings=idempotency_store_settings,
            table_name=STORE_TEST_TABLE_NAME,
        )


@pytest.fixture
def expiring_dynamodb_idempotency_store(
    expiring_idempotency_store_settings: IdempotencySettings,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Any]:
    moto = pytest.importorskip("moto")
    boto3 = pytest.importorskip("boto3")
    _set_moto_aws_credentials(monkeypatch)

    with moto.mock_aws():
        _create_store_table(boto3.client("dynamodb", region_name="us-east-1"))

        yield DynamoDBIdempotencyStore(
            idempotency_settings=expiring_idempotency_store_settings,
            table_name=STORE_TEST_TABLE_NAME,
        )


@pytest.fixture(params=["in_memory", "dynamodb_moto"])
def idempotency_store(request: pytest.FixtureRequest) -> Any:
    """Parametrized IdempotencyStore: runs conformance tests against every implementation."""
    if request.param == "in_memory":
        return request.getfixturevalue("in_memory_idempotency_store")
    return request.getfixturevalue("dynamodb_idempotency_store")


@pytest.fixture(params=["in_memory", "dynamodb_moto"])
def expiring_idempotency_store(request: pytest.FixtureRequest) -> Any:
    """Parametrized IdempotencyStore whose in-progress TTL has already elapsed."""
    if request.param == "in_memory":
        return request.getfixturevalue("expiring_in_memory_idempotency_store")
    return request.getfixturevalue("expiring_dynamodb_idempotency_store")

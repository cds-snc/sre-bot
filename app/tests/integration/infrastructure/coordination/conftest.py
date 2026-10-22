"""Fixtures for conditional-write store integration tests."""

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.coordination import ConditionalWriteStore
from infrastructure.coordination.dynamodb import DynamoDBConditionalWriteStore
from infrastructure.coordination.in_memory import InMemoryConditionalWriteStore
from infrastructure.coordination.settings import ConditionalWriteSettings
from integrations.aws import client as aws_client
from integrations.aws.client import get_aws_client
from integrations.aws.settings import get_aws_settings

STORE_TEST_TABLE_NAME = "test-sre-bot-idempotency-store"


@pytest.fixture
def mock_settings():
    """Create mock ConditionalWriteSettings for conditional-write store integration tests."""
    mock = MagicMock(spec=ConditionalWriteSettings)
    mock.idempotency_ttl_seconds = 3600
    return mock


def _set_moto_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy AWS credentials so moto never touches real AWS."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", get_aws_settings().aws_region)
    monkeypatch.delenv("AWS_ENDPOINT_URL_DYNAMODB", raising=False)
    aws_client.get_aws_settings.cache_clear()


def _create_store_table(client: Any) -> None:
    client.create_table(
        TableName=STORE_TEST_TABLE_NAME,
        KeySchema=[{"AttributeName": "idempotency_key", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "idempotency_key", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def conditional_write_store_settings() -> ConditionalWriteSettings:
    """Narrow ConditionalWriteSettings slice for ConditionalWriteStore Protocol implementations."""
    return ConditionalWriteSettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=300)


@pytest.fixture
def expiring_conditional_write_store_settings() -> ConditionalWriteSettings:
    """Settings with an already-elapsed in-progress TTL.

    Used to simulate a crashed-claimant takeover deterministically, without any
    real sleep: any claim made under this fixture immediately looks expired to
    a subsequent claim.
    """
    return ConditionalWriteSettings(IDEMPOTENCY_TTL_SECONDS=3600, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=-1)


@pytest.fixture
def in_memory_conditional_write_store(conditional_write_store_settings: ConditionalWriteSettings) -> Any:
    return InMemoryConditionalWriteStore(settings=conditional_write_store_settings)


@pytest.fixture
def expiring_in_memory_conditional_write_store(
    expiring_conditional_write_store_settings: ConditionalWriteSettings,
) -> Any:
    return InMemoryConditionalWriteStore(settings=expiring_conditional_write_store_settings)


@pytest.fixture
def dynamodb_conditional_write_store(
    conditional_write_store_settings: ConditionalWriteSettings, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Any]:
    moto = pytest.importorskip("moto")
    _set_moto_aws_credentials(monkeypatch)

    with moto.mock_aws():
        dynamodb = get_aws_client("dynamodb")
        _create_store_table(dynamodb)

        yield DynamoDBConditionalWriteStore(
            dynamodb,
            settings=conditional_write_store_settings,
            table_name=STORE_TEST_TABLE_NAME,
        )


@pytest.fixture
def expiring_dynamodb_conditional_write_store(
    expiring_conditional_write_store_settings: ConditionalWriteSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Any]:
    moto = pytest.importorskip("moto")
    _set_moto_aws_credentials(monkeypatch)

    with moto.mock_aws():
        dynamodb = get_aws_client("dynamodb")
        _create_store_table(dynamodb)

        yield DynamoDBConditionalWriteStore(
            dynamodb,
            settings=expiring_conditional_write_store_settings,
            table_name=STORE_TEST_TABLE_NAME,
        )


# Implementation -> (fixture, expiring-TTL fixture) the conformance fixtures resolve.
CONDITIONAL_WRITE_STORE_FIXTURES: dict[type[ConditionalWriteStore], tuple[str, str]] = {
    InMemoryConditionalWriteStore: ("in_memory_conditional_write_store", "expiring_in_memory_conditional_write_store"),
    DynamoDBConditionalWriteStore: ("dynamodb_conditional_write_store", "expiring_dynamodb_conditional_write_store"),
}
CONDITIONAL_WRITE_STORE_IDS = ["in_memory", "dynamodb_moto"]


@pytest.fixture
def conditional_write_store_implementations() -> frozenset[type[ConditionalWriteStore]]:
    """The implementations the conformance fixtures run against, for the enrollment test."""
    return frozenset(CONDITIONAL_WRITE_STORE_FIXTURES)


@pytest.fixture(params=list(CONDITIONAL_WRITE_STORE_FIXTURES), ids=CONDITIONAL_WRITE_STORE_IDS)
def conditional_write_store(request: pytest.FixtureRequest) -> Any:
    """Parametrized ConditionalWriteStore: runs conformance tests against every implementation."""
    return request.getfixturevalue(CONDITIONAL_WRITE_STORE_FIXTURES[request.param][0])


@pytest.fixture(params=list(CONDITIONAL_WRITE_STORE_FIXTURES), ids=CONDITIONAL_WRITE_STORE_IDS)
def expiring_conditional_write_store(request: pytest.FixtureRequest) -> Any:
    """Parametrized ConditionalWriteStore whose in-progress TTL has already elapsed."""
    return request.getfixturevalue(CONDITIONAL_WRITE_STORE_FIXTURES[request.param][1])

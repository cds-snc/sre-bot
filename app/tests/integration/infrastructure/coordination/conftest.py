"""Fixtures for conditional-write store integration tests."""

from collections.abc import Iterator
from typing import Any

import pytest

from contracts.coordination import ConditionalWriteStore
from infrastructure.coordination.dynamodb import DynamoDBConditionalWriteStore
from infrastructure.coordination.in_memory import InMemoryConditionalWriteStore
from integrations.aws import client as aws_client
from integrations.aws.client import get_aws_client

_REGION = "ca-central-1"

STORE_TEST_TABLE_NAME = "test-sre-bot-idempotency-store"


def _set_moto_aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set dummy AWS credentials so moto never touches real AWS."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", _REGION)
    monkeypatch.delenv("AWS_ENDPOINT_URL_DYNAMODB", raising=False)
    aws_client.get_aws_settings.cache_clear()


def _create_store_table(client: Any) -> None:
    client.create_table(
        TableName=STORE_TEST_TABLE_NAME,
        KeySchema=[{"AttributeName": "idempotency_key", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "idempotency_key", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


# An in-progress TTL already elapsed simulates a crashed-claimant takeover deterministically,
# without any real sleep: any claim made with it immediately looks expired to the next claim.
RECORD_TTL_SECONDS = 3600
IN_PROGRESS_TTL_SECONDS = 300
EXPIRED_IN_PROGRESS_TTL_SECONDS = -1


@pytest.fixture
def in_memory_conditional_write_store() -> Any:
    return InMemoryConditionalWriteStore(
        record_ttl_seconds=RECORD_TTL_SECONDS, in_progress_ttl_seconds=IN_PROGRESS_TTL_SECONDS
    )


@pytest.fixture
def expiring_in_memory_conditional_write_store() -> Any:
    return InMemoryConditionalWriteStore(
        record_ttl_seconds=RECORD_TTL_SECONDS, in_progress_ttl_seconds=EXPIRED_IN_PROGRESS_TTL_SECONDS
    )


def _dynamodb_store(monkeypatch: pytest.MonkeyPatch, in_progress_ttl_seconds: int) -> Iterator[Any]:
    moto = pytest.importorskip("moto")
    _set_moto_aws_credentials(monkeypatch)

    with moto.mock_aws():
        dynamodb = get_aws_client("dynamodb")
        _create_store_table(dynamodb)

        yield DynamoDBConditionalWriteStore(
            dynamodb,
            table_name=STORE_TEST_TABLE_NAME,
            record_ttl_seconds=RECORD_TTL_SECONDS,
            in_progress_ttl_seconds=in_progress_ttl_seconds,
        )


@pytest.fixture
def dynamodb_conditional_write_store(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    yield from _dynamodb_store(monkeypatch, IN_PROGRESS_TTL_SECONDS)


@pytest.fixture
def expiring_dynamodb_conditional_write_store(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    yield from _dynamodb_store(monkeypatch, EXPIRED_IN_PROGRESS_TTL_SECONDS)


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

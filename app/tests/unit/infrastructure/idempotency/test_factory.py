"""Unit tests for idempotency cache factory."""

from unittest.mock import MagicMock

import pytest

from infrastructure import idempotency
from infrastructure.idempotency.dynamodb import DynamoDBIdempotencyStore
from infrastructure.idempotency.factory import get_idempotency_store, reset_idempotency_store
from infrastructure.idempotency.settings import IdempotencySettings

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_get_aws_client(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    import infrastructure.idempotency.factory as factory_module

    dynamodb_client = MagicMock(spec=["put_item", "get_item", "delete_item"])
    get_aws_client = MagicMock(return_value=dynamodb_client)
    monkeypatch.setattr(factory_module, "get_aws_client", get_aws_client, raising=False)
    return get_aws_client, dynamodb_client


@pytest.mark.usefixtures("mock_get_aws_client")
class TestIdempotencyStoreFactory:
    """Tests for get_idempotency_store()/reset_idempotency_store().

    Verifies deterministic singleton behavior for the store provider.
    """

    def teardown_method(self):
        reset_idempotency_store()

    def test_get_idempotency_store_returns_dynamodb_backed_store(self):
        store = get_idempotency_store()

        assert isinstance(store, DynamoDBIdempotencyStore)

    def test_get_idempotency_store_constructs_and_injects_dynamodb_client(self, mock_get_aws_client):
        get_aws_client, dynamodb_client = mock_get_aws_client

        store = get_idempotency_store()

        get_aws_client.assert_called_once_with("dynamodb")
        assert store._dynamodb is dynamodb_client

    def test_get_idempotency_store_returns_singleton(self):
        store1 = get_idempotency_store()
        store2 = get_idempotency_store()

        assert store1 is store2

    def test_reset_idempotency_store_clears_singleton(self):
        store1 = get_idempotency_store()
        reset_idempotency_store()
        store2 = get_idempotency_store()

        assert store1 is not store2


@pytest.mark.usefixtures("mock_get_aws_client")
def test_build_idempotency_store_overrides_in_progress_ttl_only(monkeypatch: pytest.MonkeyPatch):
    """Builder should allow lock-specific in-progress TTL without changing record TTL."""
    build_idempotency_store = getattr(idempotency, "build_idempotency_store", None)
    assert callable(build_idempotency_store), "infrastructure.idempotency.build_idempotency_store must be exported"

    base = IdempotencySettings(IDEMPOTENCY_TTL_SECONDS=900, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=30)

    monkeypatch.setattr("infrastructure.idempotency.factory.get_idempotency_settings", lambda: base)
    store = build_idempotency_store(in_progress_ttl_seconds=14400)

    assert isinstance(store, DynamoDBIdempotencyStore)
    assert store.record_ttl_seconds == 900
    assert store.in_progress_ttl_seconds == 14400

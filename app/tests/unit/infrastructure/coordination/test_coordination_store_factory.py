"""Unit tests for the conditional-write store factory."""

from unittest.mock import MagicMock

import pytest

import infrastructure.coordination.factory as factory_module
from infrastructure import coordination
from infrastructure.coordination.dynamodb import DynamoDBConditionalWriteStore
from infrastructure.coordination.factory import get_conditional_write_store, reset_conditional_write_store
from infrastructure.coordination.settings import ConditionalWriteSettings

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_get_aws_client(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    dynamodb_client = MagicMock(spec=["put_item", "get_item", "delete_item"])
    get_aws_client = MagicMock(return_value=dynamodb_client)
    monkeypatch.setattr(factory_module, "get_aws_client", get_aws_client, raising=False)
    return get_aws_client, dynamodb_client


@pytest.mark.usefixtures("mock_get_aws_client")
class TestConditionalWriteStoreFactory:
    """Tests for get_conditional_write_store()/reset_conditional_write_store().

    Verifies deterministic singleton behavior for the store provider.
    """

    def teardown_method(self):
        reset_conditional_write_store()

    def test_get_conditional_write_store_returns_dynamodb_backed_store(self):
        store = get_conditional_write_store()

        assert isinstance(store, DynamoDBConditionalWriteStore)

    def test_get_conditional_write_store_constructs_and_injects_dynamodb_client(self, mock_get_aws_client):
        get_aws_client, dynamodb_client = mock_get_aws_client

        store = get_conditional_write_store()

        get_aws_client.assert_called_once_with("dynamodb")
        assert store._dynamodb is dynamodb_client

    def test_get_conditional_write_store_returns_singleton(self):
        store1 = get_conditional_write_store()
        store2 = get_conditional_write_store()

        assert store1 is store2

    def test_reset_conditional_write_store_clears_singleton(self):
        store1 = get_conditional_write_store()
        reset_conditional_write_store()
        store2 = get_conditional_write_store()

        assert store1 is not store2


@pytest.mark.usefixtures("mock_get_aws_client")
def test_build_conditional_write_store_overrides_in_progress_ttl_only(monkeypatch: pytest.MonkeyPatch):
    """Builder should allow lock-specific in-progress TTL without changing record TTL."""
    build_conditional_write_store = getattr(coordination, "build_conditional_write_store", None)
    assert callable(build_conditional_write_store), "infrastructure.coordination.build_conditional_write_store must be exported"

    base = ConditionalWriteSettings(IDEMPOTENCY_TTL_SECONDS=900, IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS=30)

    monkeypatch.setattr("infrastructure.coordination.factory.get_conditional_write_settings", lambda: base)
    store = build_conditional_write_store(in_progress_ttl_seconds=14400)

    assert isinstance(store, DynamoDBConditionalWriteStore)
    assert store.record_ttl_seconds == 900
    assert store.in_progress_ttl_seconds == 14400

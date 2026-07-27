"""Unit tests for idempotency cache factory."""

import pytest

from infrastructure import idempotency
from infrastructure.idempotency import get_cache, reset_cache
from infrastructure.idempotency.dynamodb import DynamoDBCache, DynamoDBIdempotencyStore
from infrastructure.idempotency.factory import get_idempotency_store, reset_idempotency_store
from infrastructure.idempotency.settings import IdempotencySettings

pytestmark = pytest.mark.unit


class TestCacheFactory:
    """Tests for cache factory."""

    def test_get_cache_returns_dynamodb(self, mock_settings):
        """Factory returns DynamoDB cache."""
        cache = get_cache(mock_settings)
        assert isinstance(cache, DynamoDBCache)

    def test_get_cache_singleton(self, mock_settings):
        """get_cache returns singleton instance."""
        cache1 = get_cache(mock_settings)
        cache2 = get_cache(mock_settings)
        assert cache1 is cache2

    def test_reset_cache_clears_singleton(self, mock_settings):
        """reset_cache clears the singleton for testing."""
        cache1 = get_cache(mock_settings)
        reset_cache()
        cache2 = get_cache(mock_settings)
        assert cache1 is not cache2

    def test_get_cache_after_reset_returns_new_instance(self, mock_settings):
        """get_cache after reset returns new instance."""
        cache1 = get_cache(mock_settings)
        reset_cache()
        cache2 = get_cache(mock_settings)

        assert isinstance(cache2, DynamoDBCache)
        assert cache1 is not cache2

    def test_multiple_get_cache_calls_same_instance(self, mock_settings):
        """Multiple get_cache calls return same instance."""
        cache1 = get_cache(mock_settings)
        cache2 = get_cache(mock_settings)
        cache3 = get_cache(mock_settings)

        assert cache1 is cache2
        assert cache2 is cache3


class TestIdempotencyStoreFactory:
    """Tests for get_idempotency_store()/reset_idempotency_store().

    Verifies singleton behavior mirrors get_cache()/reset_cache().
    """

    def teardown_method(self):
        reset_idempotency_store()

    def test_get_idempotency_store_returns_dynamodb_backed_store(self):
        store = get_idempotency_store()

        assert isinstance(store, DynamoDBIdempotencyStore)

    def test_get_idempotency_store_returns_singleton(self):
        store1 = get_idempotency_store()
        store2 = get_idempotency_store()

        assert store1 is store2

    def test_reset_idempotency_store_clears_singleton(self):
        store1 = get_idempotency_store()
        reset_idempotency_store()
        store2 = get_idempotency_store()

        assert store1 is not store2


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

"""Unit tests for idempotency cache factory."""

import pytest

from infrastructure.idempotency import get_cache, reset_cache
from infrastructure.idempotency.dynamodb import DynamoDBCache, DynamoDBIdempotencyStore
from infrastructure.idempotency.factory import (
    get_idempotency_store,
    reset_idempotency_store,
)

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
    """Tests for the new get_idempotency_store()/reset_idempotency_store() provider (AC#8).

    TASK-5.2/TASK-5.3 depend on being able to obtain a concrete
    IdempotencyStore from this factory, mirroring the existing
    get_cache()/reset_cache() singleton pattern.
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

"""Unit tests for idempotency cache factory."""

import pytest
from infrastructure.idempotency import get_cache, reset_cache
from infrastructure.idempotency.dynamodb import DynamoDBCache

pytestmark = pytest.mark.unit


class TestCacheFactory:
    """Tests for cache factory."""

    def test_get_cache_returns_dynamodb(self):
        """Factory returns DynamoDB cache."""
        cache = get_cache()
        assert isinstance(cache, DynamoDBCache)

    def test_get_cache_singleton(self):
        """get_cache returns singleton instance."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

    def test_reset_cache_clears_singleton(self):
        """reset_cache clears the singleton for testing."""
        cache1 = get_cache()
        reset_cache()
        cache2 = get_cache()
        assert cache1 is not cache2

    def test_get_cache_after_reset_returns_new_instance(self):
        """get_cache after reset returns new instance."""
        cache1 = get_cache()
        reset_cache()
        cache2 = get_cache()

        assert isinstance(cache2, DynamoDBCache)
        assert cache1 is not cache2

    def test_multiple_get_cache_calls_same_instance(self):
        """Multiple get_cache calls return same instance."""
        cache1 = get_cache()
        cache2 = get_cache()
        cache3 = get_cache()

        assert cache1 is cache2
        assert cache2 is cache3

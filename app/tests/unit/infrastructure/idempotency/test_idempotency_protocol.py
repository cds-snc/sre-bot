"""Tests for IdempotencyService Protocol.

Validates that the Protocol contract is properly defined and that
implementations conform to the runtime-checkable interface.
"""

from typing import Any

from infrastructure.idempotency.cache import IdempotencyCache
from infrastructure.idempotency.protocol import IdempotencyService
from infrastructure.idempotency.service import DynamoDBIdempotencyService


class FakeIdempotencyCache(IdempotencyCache):
    """In-memory fake implementation of IdempotencyCache for testing."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def get(self, key: str) -> dict[str, Any] | None:
        return self._store.get(key)

    def set(self, key: str, response: dict[str, Any], ttl_seconds: int) -> None:
        self._store[key] = response

    def clear(self) -> None:
        self._store.clear()

    def get_stats(self) -> dict[str, Any]:
        return {"size": len(self._store)}


class FakeIdempotencyService:
    """In-memory fake implementation of IdempotencyService for testing."""

    def __init__(self, cache: IdempotencyCache) -> None:
        self._cache = cache

    def get(self, key: str) -> dict[str, Any] | None:
        return self._cache.get(key)

    def set(self, key: str, response: dict[str, Any], ttl_seconds: int) -> None:
        self._cache.set(key, response, ttl_seconds)

    def clear(self) -> None:
        self._cache.clear()

    def get_stats(self) -> dict[str, Any]:
        return self._cache.get_stats()

    @property
    def cache(self) -> IdempotencyCache:
        return self._cache


class TestIdempotencyProtocol:
    """Test suite for IdempotencyService Protocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Verify that IdempotencyService Protocol has @runtime_checkable."""
        # The Protocol must be importable and checkable at runtime
        assert IdempotencyService is not None
        # If it's runtime checkable, isinstance checks should work
        fake_service = FakeIdempotencyService(FakeIdempotencyCache())
        assert isinstance(fake_service, IdempotencyService)

    def test_dynamodb_idempotency_satisfies_protocol(self) -> None:
        """Verify that DynamoDBIdempotencyService satisfies the Protocol."""
        fake_cache = FakeIdempotencyCache()
        service = DynamoDBIdempotencyService(cache=fake_cache)
        assert isinstance(service, IdempotencyService)

    def test_fake_idempotency_satisfies_protocol(self) -> None:
        """Verify that a minimal fake implementation satisfies the Protocol."""
        fake_cache = FakeIdempotencyCache()
        fake = FakeIdempotencyService(cache=fake_cache)
        assert isinstance(fake, IdempotencyService)

    def test_protocol_get_method_signature(self) -> None:
        """Verify that Protocol includes get method with correct signature."""
        # Create a minimal service that implements the Protocol
        cache = FakeIdempotencyCache()
        cache.set("test_key", {"result": "data"}, ttl_seconds=3600)

        service = DynamoDBIdempotencyService(cache=cache)

        # Call get method
        result = service.get("test_key")
        assert result == {"result": "data"}

        # Call get with missing key
        result = service.get("nonexistent")
        assert result is None

    def test_protocol_set_method_signature(self) -> None:
        """Verify that Protocol includes set method with correct signature."""
        cache = FakeIdempotencyCache()
        service = DynamoDBIdempotencyService(cache=cache)

        # Call set method
        response_data = {"status": "success", "id": 123}
        service.set("request_key", response_data, ttl_seconds=3600)

        # Verify the data was cached
        cached = service.get("request_key")
        assert cached == response_data

    def test_protocol_clear_method_signature(self) -> None:
        """Verify that Protocol includes clear method with correct signature."""
        cache = FakeIdempotencyCache()
        service = DynamoDBIdempotencyService(cache=cache)

        # Set and verify
        service.set("key1", {"data": "value"}, ttl_seconds=3600)
        assert service.get("key1") is not None

        # Clear
        service.clear()

        # Verify cleared
        assert service.get("key1") is None

    def test_protocol_get_stats_method_signature(self) -> None:
        """Verify that Protocol includes get_stats method with correct signature."""
        cache = FakeIdempotencyCache()
        service = DynamoDBIdempotencyService(cache=cache)

        # Call get_stats method
        stats = service.get_stats()
        assert isinstance(stats, dict)

    def test_protocol_cache_property_signature(self) -> None:
        """Verify that Protocol includes cache property with correct return type."""
        cache = FakeIdempotencyCache()
        service = DynamoDBIdempotencyService(cache=cache)

        # Access cache property
        returned_cache = service.cache
        assert returned_cache is cache

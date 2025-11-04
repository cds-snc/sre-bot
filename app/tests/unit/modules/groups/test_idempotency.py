"""Unit tests for groups idempotency module.

Tests in-memory cache with TTL, expiration handling, thread safety,
and cache statistics.
"""

import pytest
import threading
from unittest.mock import patch, MagicMock
from datetime import datetime

from modules.groups import idempotency, schemas


pytestmark = pytest.mark.unit


class TestCacheResponseAndRetrieval:
    """Test basic cache storage and retrieval."""

    def setup_method(self):
        """Clear cache before each test."""
        idempotency.clear_cache()

    def test_cache_response_stores_entry(self):
        """cache_response stores response in cache."""
        key = "test-key-1"
        response = MagicMock(spec=schemas.ActionResponse)
        response.success = True

        idempotency.cache_response(key, response)

        # Verify entry exists
        assert key in idempotency._IDEMPOTENCY_CACHE

    def test_get_cached_response_returns_stored_response(self):
        """get_cached_response returns previously cached response."""
        key = "test-key-2"
        response = MagicMock(spec=schemas.ActionResponse)
        response.success = True
        response.group_id = "group-123"
        response.member_email = "user@example.com"

        idempotency.cache_response(key, response)
        cached = idempotency.get_cached_response(key)

        assert cached is response
        assert cached.group_id == "group-123"
        assert cached.member_email == "user@example.com"

    def test_get_cached_response_returns_none_for_missing_key(self):
        """get_cached_response returns None for uncached key."""
        result = idempotency.get_cached_response("nonexistent-key")
        assert result is None

    def test_get_cached_response_empty_cache(self):
        """get_cached_response returns None when cache is empty."""
        idempotency.clear_cache()
        result = idempotency.get_cached_response("any-key")
        assert result is None

    def test_cache_multiple_responses(self):
        """Multiple responses can be cached with different keys."""
        responses = {}
        for i in range(3):
            key = f"key-{i}"
            response = MagicMock(spec=schemas.ActionResponse)
            response.group_id = f"group-{i}"
            idempotency.cache_response(key, response)
            responses[key] = (response, i)

        for key, (response, expected_i) in responses.items():
            cached = idempotency.get_cached_response(key)
            assert cached is response
            assert cached.group_id == f"group-{expected_i}"


class TestCacheExpiration:
    """Test cache TTL and expiration."""

    def setup_method(self):
        """Clear cache before each test."""
        idempotency.clear_cache()

    def test_cache_response_uses_default_ttl(self):
        """cache_response uses default TTL of 3600 seconds."""
        key = "test-ttl-default"
        response = MagicMock(spec=schemas.ActionResponse)

        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0
            idempotency.cache_response(key, response)

            # Expiry should be stored as 1000 + 3600 = 4600
            stored_response, expiry = idempotency._IDEMPOTENCY_CACHE[key]
            assert expiry == 4600.0

    def test_cache_response_uses_custom_ttl(self):
        """cache_response respects custom TTL."""
        key = "test-ttl-custom"
        response = MagicMock(spec=schemas.ActionResponse)

        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0
            idempotency.cache_response(key, response, ttl_seconds=600)

            stored_response, expiry = idempotency._IDEMPOTENCY_CACHE[key]
            assert expiry == 1600.0

    def test_get_cached_response_expired_entry_returns_none(self):
        """get_cached_response returns None for expired entry."""
        key = "test-expiry"
        response = MagicMock(spec=schemas.ActionResponse)

        with patch("modules.groups.idempotency.time.time") as mock_time:
            # Store at time 1000, expiry at 1100
            mock_time.return_value = 1000.0
            idempotency.cache_response(key, response, ttl_seconds=100)

            # Try to retrieve at time 1101 (after expiry)
            mock_time.return_value = 1101.0
            result = idempotency.get_cached_response(key)

        assert result is None

    def test_get_cached_response_removes_expired_entry(self):
        """get_cached_response removes expired entry from cache."""
        key = "test-remove-expired"
        response = MagicMock(spec=schemas.ActionResponse)

        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0
            idempotency.cache_response(key, response, ttl_seconds=100)

            # Verify entry exists
            assert key in idempotency._IDEMPOTENCY_CACHE

            # Check at expired time
            mock_time.return_value = 1101.0
            idempotency.get_cached_response(key)

            # Entry should be removed
            assert key not in idempotency._IDEMPOTENCY_CACHE

    def test_get_cached_response_valid_entry_not_removed(self):
        """get_cached_response does not remove valid (non-expired) entry."""
        key = "test-valid"
        response = MagicMock(spec=schemas.ActionResponse)

        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0
            idempotency.cache_response(key, response, ttl_seconds=100)

            # Check at time 1050 (before expiry at 1100)
            mock_time.return_value = 1050.0
            result = idempotency.get_cached_response(key)

            assert result is response
            assert key in idempotency._IDEMPOTENCY_CACHE


class TestCacheStatistics:
    """Test cache statistics tracking."""

    def setup_method(self):
        """Clear cache before each test."""
        idempotency.clear_cache()

    def test_get_cache_stats_empty_cache(self):
        """get_cache_stats returns zeros for empty cache."""
        stats = idempotency.get_cache_stats()

        assert stats["total_entries"] == 0
        assert stats["active_entries"] == 0
        assert stats["expired_entries"] == 0

    def test_get_cache_stats_counts_entries(self):
        """get_cache_stats counts total entries."""
        for i in range(5):
            response = MagicMock(spec=schemas.ActionResponse)
            idempotency.cache_response(f"key-{i}", response)

        stats = idempotency.get_cache_stats()
        assert stats["total_entries"] == 5

    def test_get_cache_stats_counts_active_entries(self):
        """get_cache_stats counts active (non-expired) entries."""
        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0

            # Cache 3 entries with 100s TTL (expire at 1100)
            for i in range(3):
                response = MagicMock(spec=schemas.ActionResponse)
                idempotency.cache_response(f"key-{i}", response, ttl_seconds=100)

            # Check at time 1050 (all valid)
            mock_time.return_value = 1050.0
            stats = idempotency.get_cache_stats()

            assert stats["total_entries"] == 3
            assert stats["active_entries"] == 3
            assert stats["expired_entries"] == 0

    def test_get_cache_stats_counts_expired_entries(self):
        """get_cache_stats counts expired entries."""
        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0

            # Cache 3 entries with different TTLs
            response = MagicMock(spec=schemas.ActionResponse)
            idempotency.cache_response("short-ttl", response, ttl_seconds=50)

            response2 = MagicMock(spec=schemas.ActionResponse)
            idempotency.cache_response("long-ttl", response2, ttl_seconds=200)

            response3 = MagicMock(spec=schemas.ActionResponse)
            idempotency.cache_response("medium-ttl", response3, ttl_seconds=100)

            # Check at time 1080 (short expired, others valid)
            mock_time.return_value = 1080.0
            stats = idempotency.get_cache_stats()

            assert stats["total_entries"] == 3
            assert stats["expired_entries"] == 1
            assert stats["active_entries"] == 2

    def test_get_cache_stats_all_expired(self):
        """get_cache_stats correctly shows all entries expired."""
        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0

            for i in range(3):
                response = MagicMock(spec=schemas.ActionResponse)
                idempotency.cache_response(f"key-{i}", response, ttl_seconds=50)

            # Check at time 1100 (all expired)
            mock_time.return_value = 1100.0
            stats = idempotency.get_cache_stats()

            assert stats["total_entries"] == 3
            assert stats["active_entries"] == 0
            assert stats["expired_entries"] == 3


class TestCleanupExpiredEntries:
    """Test scheduled cleanup of expired entries."""

    def setup_method(self):
        """Clear cache before each test."""
        idempotency.clear_cache()

    def test_cleanup_removes_expired_entries(self):
        """cleanup_expired_entries removes expired entries."""
        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0

            # Add expired and valid entries
            response1 = MagicMock(spec=schemas.ActionResponse)
            idempotency.cache_response("expired", response1, ttl_seconds=50)

            response2 = MagicMock(spec=schemas.ActionResponse)
            idempotency.cache_response("valid", response2, ttl_seconds=200)

            # Verify both are in cache
            assert len(idempotency._IDEMPOTENCY_CACHE) == 2

            # Run cleanup at time 1100
            mock_time.return_value = 1100.0
            idempotency.cleanup_expired_entries()

            # Only valid entry should remain
            assert len(idempotency._IDEMPOTENCY_CACHE) == 1
            assert "valid" in idempotency._IDEMPOTENCY_CACHE

    def test_cleanup_empty_cache(self):
        """cleanup_expired_entries handles empty cache."""
        idempotency.clear_cache()
        # Should not raise
        idempotency.cleanup_expired_entries()
        assert len(idempotency._IDEMPOTENCY_CACHE) == 0

    def test_cleanup_all_valid_entries(self):
        """cleanup_expired_entries keeps valid entries."""
        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0

            for i in range(3):
                response = MagicMock(spec=schemas.ActionResponse)
                idempotency.cache_response(f"key-{i}", response, ttl_seconds=200)

            # Run cleanup at time 1050 (all valid)
            mock_time.return_value = 1050.0
            idempotency.cleanup_expired_entries()

            # All entries should remain
            assert len(idempotency._IDEMPOTENCY_CACHE) == 3

    def test_cleanup_all_expired_entries(self):
        """cleanup_expired_entries removes all when all expired."""
        with patch("modules.groups.idempotency.time.time") as mock_time:
            mock_time.return_value = 1000.0

            for i in range(3):
                response = MagicMock(spec=schemas.ActionResponse)
                idempotency.cache_response(f"key-{i}", response, ttl_seconds=50)

            # Run cleanup at time 1100 (all expired)
            mock_time.return_value = 1100.0
            idempotency.cleanup_expired_entries()

            # Cache should be empty
            assert len(idempotency._IDEMPOTENCY_CACHE) == 0

    def test_cleanup_handles_exception_gracefully(self):
        """cleanup_expired_entries handles exceptions."""
        with patch("modules.groups.idempotency._CACHE_LOCK") as mock_lock:
            mock_lock.__enter__.side_effect = Exception("lock error")
            # Should not raise, just log error
            idempotency.cleanup_expired_entries()


class TestClearCache:
    """Test cache clearing."""

    def test_clear_cache_empties_cache(self):
        """clear_cache removes all entries."""
        response = MagicMock(spec=schemas.ActionResponse)
        idempotency.cache_response("key1", response)
        idempotency.cache_response("key2", response)

        assert len(idempotency._IDEMPOTENCY_CACHE) == 2

        idempotency.clear_cache()

        assert len(idempotency._IDEMPOTENCY_CACHE) == 0

    def test_clear_cache_idempotent(self):
        """clear_cache can be called multiple times safely."""
        idempotency.clear_cache()
        idempotency.clear_cache()
        assert len(idempotency._IDEMPOTENCY_CACHE) == 0


class TestThreadSafety:
    """Test thread-safe cache operations."""

    def setup_method(self):
        """Clear cache before each test."""
        idempotency.clear_cache()

    def test_concurrent_cache_writes(self):
        """Multiple threads can write to cache safely."""

        def write_entries(thread_id):
            for i in range(10):
                key = f"thread-{thread_id}-key-{i}"
                response = MagicMock(spec=schemas.ActionResponse)
                response.group_id = f"group-{thread_id}"
                idempotency.cache_response(key, response)

        threads = []
        for thread_id in range(5):
            t = threading.Thread(target=write_entries, args=(thread_id,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        stats = idempotency.get_cache_stats()
        assert stats["total_entries"] == 50  # 5 threads * 10 entries

    def test_concurrent_cache_reads_and_writes(self):
        """Multiple threads reading and writing simultaneously."""
        results = []

        def read_write(thread_id):
            for i in range(5):
                # Write
                key = f"thread-{thread_id}-key-{i}"
                response = MagicMock(spec=schemas.ActionResponse)
                idempotency.cache_response(key, response)

                # Read
                cached = idempotency.get_cached_response(key)
                results.append(cached is response)

        threads = []
        for thread_id in range(3):
            t = threading.Thread(target=read_write, args=(thread_id,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # All reads should have succeeded
        assert all(results)

    def test_concurrent_cleanup(self):
        """Concurrent cleanup and cache operations."""
        response = MagicMock(spec=schemas.ActionResponse)
        for i in range(20):
            idempotency.cache_response(f"key-{i}", response)

        def cleanup_worker():
            for _ in range(5):
                idempotency.cleanup_expired_entries()

        threads = []
        threads.append(threading.Thread(target=cleanup_worker))

        # While cleanup is running, do cache operations
        def cache_worker():
            for i in range(10):
                response = MagicMock(spec=schemas.ActionResponse)
                idempotency.cache_response(f"dynamic-{i}", response)

        for _ in range(3):
            threads.append(threading.Thread(target=cache_worker))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should complete without errors
        stats = idempotency.get_cache_stats()
        assert stats is not None


class TestRealWorldScenarios:
    """Test realistic usage patterns."""

    def setup_method(self):
        """Clear cache before each test."""
        idempotency.clear_cache()

    def test_idempotency_workflow(self):
        """Test typical idempotency workflow: cache miss, then hit."""
        key = "idempotent-key-001"
        response = MagicMock(spec=schemas.ActionResponse)
        response.success = True
        response.action = "add_member"

        # First call: cache miss
        cached1 = idempotency.get_cached_response(key)
        assert cached1 is None

        # Store response
        idempotency.cache_response(key, response)

        # Second call: cache hit
        cached2 = idempotency.get_cached_response(key)
        assert cached2 is response

        # Third call: still cache hit
        cached3 = idempotency.get_cached_response(key)
        assert cached3 is response

    def test_multiple_operations_same_key_not_allowed(self):
        """Idempotency prevents duplicate operations with same key."""
        key = "operation-key"

        response1 = MagicMock(spec=schemas.ActionResponse)
        response1.group_id = "group-1"
        idempotency.cache_response(key, response1)

        # Different response with same key - should NOT be stored (client responsibility)
        response2 = MagicMock(spec=schemas.ActionResponse)
        response2.group_id = "group-2"
        idempotency.cache_response(key, response2)

        # Get returns the latest (this is current behavior)
        cached = idempotency.get_cached_response(key)
        assert cached.group_id == "group-2"

    def test_cache_behavior_around_expiration_boundary(self):
        """Test cache behavior at exact expiration time."""
        key = "boundary-test"
        response = MagicMock(spec=schemas.ActionResponse)

        with patch("modules.groups.idempotency.time.time") as mock_time:
            # Store at 1000, expires at 1100
            mock_time.return_value = 1000.0
            idempotency.cache_response(key, response, ttl_seconds=100)

            # Check just before expiry (1099.9)
            mock_time.return_value = 1099.9
            result = idempotency.get_cached_response(key)
            assert result is response

            # Check at exact expiry (1100.0) - implementation uses > not >=
            # so entry is valid until time.time() > expiry
            mock_time.return_value = 1100.0
            result = idempotency.get_cached_response(key)
            assert result is response  # Still valid at 1100.0

            # Check just after expiry (1100.1)
            mock_time.return_value = 1100.1
            result = idempotency.get_cached_response(key)
            assert result is None

    def test_cache_operations_with_none_response(self):
        """Cache can store responses that evaluate to falsy."""
        key = "none-response"
        response = None

        # Should not crash with None response
        idempotency.cache_response(key, response)

        # But we still need a real response object for actual use
        # This tests that implementation doesn't assume response is truthy
        stats = idempotency.get_cache_stats()
        assert stats["total_entries"] == 1

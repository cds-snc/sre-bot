"""Tests for idempotency cache module and service layer integration."""

import time
from datetime import datetime
from unittest.mock import patch, MagicMock

from modules.groups import idempotency, schemas, service


class TestIdempotencyCacheModule:
    """Test the idempotency cache module functions."""

    def test_cache_response_and_get_cached_response(self):
        """Test storing and retrieving a cached response."""
        idempotency.clear_cache()

        key = "test-key-1"
        response = schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.ADD_MEMBER,
            group_id="group-123",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            details={},
            timestamp=datetime.utcnow(),
        )

        # Cache should be empty initially
        assert idempotency.get_cached_response(key) is None

        # Store response
        idempotency.cache_response(key, response)

        # Should retrieve cached response
        cached = idempotency.get_cached_response(key)
        assert cached is not None
        assert cached.success is True
        assert cached.group_id == "group-123"
        assert cached.member_email == "user@example.com"

    def test_cache_expiration(self):
        """Test that cached responses expire after TTL."""
        idempotency.clear_cache()

        key = "test-key-expiry"
        response = schemas.ActionResponse(
            success=True,
            action=schemas.OperationType.REMOVE_MEMBER,
            group_id="group-456",
            member_email="user2@example.com",
            provider=schemas.ProviderType.GOOGLE,
            details={},
            timestamp=datetime.utcnow(),
        )

        # Cache with 1-second TTL for testing
        idempotency.cache_response(key, response, ttl_seconds=1)

        # Should be available immediately
        assert idempotency.get_cached_response(key) is not None

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired now
        assert idempotency.get_cached_response(key) is None

    def test_get_cache_stats(self):
        """Test cache statistics reporting."""
        idempotency.clear_cache()

        # Add multiple responses
        for i in range(3):
            key = f"test-key-{i}"
            response = schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.ADD_MEMBER,
                group_id=f"group-{i}",
                member_email=f"user{i}@example.com",
                provider=schemas.ProviderType.GOOGLE,
                details={},
                timestamp=datetime.utcnow(),
            )
            idempotency.cache_response(key, response)

        stats = idempotency.get_cache_stats()
        assert stats["total_entries"] == 3
        assert stats["active_entries"] == 3
        assert stats["expired_entries"] == 0

    def test_cleanup_expired_entries(self):
        """Test cleanup of expired cache entries."""
        idempotency.clear_cache()

        # Add entries with different TTLs
        for i in range(2):
            key = f"expire-soon-{i}"
            response = schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.ADD_MEMBER,
                group_id=f"group-{i}",
                member_email=f"user{i}@example.com",
                provider=schemas.ProviderType.GOOGLE,
                details={},
                timestamp=datetime.utcnow(),
            )
            # Short TTL - will expire
            idempotency.cache_response(key, response, ttl_seconds=1)

        # Add entries with longer TTL
        for i in range(2, 4):
            key = f"expire-later-{i}"
            response = schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.ADD_MEMBER,
                group_id=f"group-{i}",
                member_email=f"user{i}@example.com",
                provider=schemas.ProviderType.GOOGLE,
                details={},
                timestamp=datetime.utcnow(),
            )
            # Long TTL - should remain
            idempotency.cache_response(key, response, ttl_seconds=3600)

        stats_before = idempotency.get_cache_stats()
        assert stats_before["total_entries"] == 4

        # Wait for first batch to expire
        time.sleep(1.1)

        # Cleanup should remove expired entries
        idempotency.cleanup_expired_entries()

        stats_after = idempotency.get_cache_stats()
        assert stats_after["total_entries"] == 2
        assert stats_after["active_entries"] == 2

    def test_cache_thread_safety(self):
        """Test that cache operations are thread-safe."""
        import threading

        idempotency.clear_cache()

        def cache_entries(thread_id):
            for i in range(10):
                key = f"thread-{thread_id}-key-{i}"
                response = schemas.ActionResponse(
                    success=True,
                    action=schemas.OperationType.ADD_MEMBER,
                    group_id=f"group-{thread_id}",
                    member_email=f"user{thread_id}@example.com",
                    provider=schemas.ProviderType.GOOGLE,
                    details={},
                    timestamp=datetime.utcnow(),
                )
                idempotency.cache_response(key, response)

        # Run multiple threads
        threads = []
        for thread_id in range(5):
            t = threading.Thread(target=cache_entries, args=(thread_id,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        stats = idempotency.get_cache_stats()
        assert stats["total_entries"] == 50  # 5 threads * 10 entries each


class TestServiceLayerIdempotency:
    """Test idempotency integration in service layer."""

    @patch("modules.groups.service.idempotency.get_cached_response")
    @patch("modules.groups.service.idempotency.cache_response")
    @patch("modules.groups.service.orchestration.add_member_to_group")
    @patch("modules.groups.service.event_system.dispatch_background")
    def test_add_member_cache_integration(
        self, mock_dispatch, mock_orch, mock_cache, mock_get_cache
    ):
        """Test that add_member integrates with cache at the service layer."""
        # Simulate cache miss on first call
        mock_get_cache.return_value = None

        request = schemas.AddMemberRequest(
            group_id="group-123",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Needed for project X",
            requestor="admin@example.com",
            idempotency_key="test-key-1",
        )

        # Create successful response
        mock_orch.return_value = {
            "primary": MagicMock(success=True),
            "action": "add_member",
            "group_id": "group-123",
            "member_email": "user@example.com",
            "success": True,
        }

        service.add_member(request)

        # Verify cache was checked
        mock_get_cache.assert_called_once_with("test-key-1")

        # Verify orchestration was called
        assert mock_orch.called

    @patch("modules.groups.service.orchestration.add_member_to_group")
    @patch("modules.groups.service.event_system.dispatch_background")
    def test_add_member_different_keys_not_cached(self, mock_dispatch, mock_orch):
        """Test that different idempotency keys result in separate executions."""
        idempotency.clear_cache()

        # Mock orchestration
        mock_orch.return_value = {
            "primary": MagicMock(success=True),
            "action": "add_member",
            "group_id": "group-123",
            "member_email": "user@example.com",
        }

        # First request with key 1
        request1 = schemas.AddMemberRequest(
            group_id="group-123",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Needed for project X",  # At least 10 chars
            requestor="admin@example.com",
            idempotency_key="key-1",
        )
        service.add_member(request1)

        # Second request with different key
        request2 = schemas.AddMemberRequest(
            group_id="group-123",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Needed for project Y",  # At least 10 chars
            requestor="admin@example.com",
            idempotency_key="key-2",
        )
        service.add_member(request2)

        # Orchestration should have been called twice
        assert mock_orch.call_count == 2

    @patch("modules.groups.service.idempotency.get_cached_response")
    @patch("modules.groups.service.idempotency.cache_response")
    @patch("modules.groups.service.orchestration.remove_member_from_group")
    @patch("modules.groups.service.event_system.dispatch_background")
    def test_remove_member_cache_integration(
        self, mock_dispatch, mock_orch, mock_cache, mock_get_cache
    ):
        """Test that remove_member integrates with cache at the service layer."""
        # Simulate cache miss on first call
        mock_get_cache.return_value = None

        request = schemas.RemoveMemberRequest(
            group_id="group-456",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Offboarding personnel",
            idempotency_key="test-key-2",
        )

        # Create successful response
        mock_orch.return_value = {
            "primary": MagicMock(success=True),
            "action": "remove_member",
            "group_id": "group-456",
            "member_email": "user@example.com",
            "success": True,
        }

        service.remove_member(request)

        # Verify cache was checked
        mock_get_cache.assert_called_once_with("test-key-2")

        # Verify orchestration was called
        assert mock_orch.called

    @patch("modules.groups.service.orchestration.add_member_to_group")
    @patch("modules.groups.service.event_system.dispatch_background")
    def test_add_member_failure_not_cached(self, mock_dispatch, mock_orch):
        """Test that failed operations are not cached."""
        idempotency.clear_cache()

        # Mock orchestration to return failure
        mock_orch.return_value = {
            "primary": MagicMock(success=False),
            "action": "add_member",
            "group_id": "group-123",
            "member_email": "user@example.com",
            "success": False,
        }

        idempotency_key = "test-failure-key"
        request = schemas.AddMemberRequest(
            group_id="group-123",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Needed for project X",  # At least 10 chars
            requestor="admin@example.com",
            idempotency_key=idempotency_key,
        )

        # Call service first time (should fail)
        response1 = service.add_member(request)
        assert response1.success is False

        # Verify orchestration was called
        first_call_count = mock_orch.call_count

        # Call service second time (should NOT be cached)
        response2 = service.add_member(request)

        # Verify orchestration was called again (cache miss due to failure)
        assert mock_orch.call_count == first_call_count + 1
        assert response2.success is False

    def test_idempotency_key_auto_generation(self):
        """Test that idempotency_key is auto-generated with UUID."""
        request = schemas.AddMemberRequest(
            group_id="group-123",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Test",
            requestor="admin@example.com",
            # idempotency_key not provided - should be auto-generated
        )

        assert request.idempotency_key is not None
        assert len(request.idempotency_key) == 36  # UUID string length

    def test_idempotency_key_explicit_override(self):
        """Test that explicit idempotency_key overrides auto-generation."""
        explicit_key = "custom-key-12345"
        request = schemas.AddMemberRequest(
            group_id="group-123",
            member_email="user@example.com",
            provider=schemas.ProviderType.GOOGLE,
            justification="Test",
            requestor="admin@example.com",
            idempotency_key=explicit_key,
        )

        assert request.idempotency_key == explicit_key


class TestScheduledCleanup:
    """Test scheduled cleanup integration."""

    def test_cleanup_can_be_called_by_scheduler(self):
        """Test that cleanup_expired_entries can be called as a scheduled job."""
        idempotency.clear_cache()

        # Add some entries
        for i in range(3):
            key = f"cleanup-test-{i}"
            response = schemas.ActionResponse(
                success=True,
                action=schemas.OperationType.ADD_MEMBER,
                group_id=f"group-{i}",
                member_email=f"user{i}@example.com",
                provider=schemas.ProviderType.GOOGLE,
                details={},
                timestamp=datetime.utcnow(),
            )
            idempotency.cache_response(key, response, ttl_seconds=1)

        # Wait for expiration
        time.sleep(1.1)

        # Cleanup should not raise
        idempotency.cleanup_expired_entries()

        stats = idempotency.get_cache_stats()
        assert stats["total_entries"] == 0

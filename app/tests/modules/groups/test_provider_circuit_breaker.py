"""Tests for circuit breaker integration with providers."""

from unittest.mock import patch

from modules.groups.providers.base import (
    GroupProvider,
    OperationResult,
    OperationStatus,
)
from modules.groups.models import NormalizedMember
from modules.groups.circuit_breaker import CircuitState


class MockProvider(GroupProvider):
    """Mock provider for testing circuit breaker integration."""

    def __init__(self, failure_threshold=None):
        """Initialize mock provider."""
        super().__init__()
        self.call_count = 0
        self.should_fail = False
        # Override circuit breaker threshold if provided
        if failure_threshold is not None and self._circuit_breaker:
            self._circuit_breaker.failure_threshold = failure_threshold

    @property
    def capabilities(self):
        """Return mock capabilities."""
        from modules.groups.providers.base import ProviderCapabilities

        return ProviderCapabilities(supports_member_management=True)

    def _add_member_impl(self, group_key, member_data):
        """Mock add member implementation."""
        self.call_count += 1
        if self.should_fail:
            raise Exception("Simulated failure")
        return OperationResult.success(data={"added": True})

    def _remove_member_impl(self, group_key, member_data):
        """Mock remove member implementation."""
        self.call_count += 1
        if self.should_fail:
            raise Exception("Simulated failure")
        return OperationResult.success(data={"removed": True})

    def _get_group_members_impl(self, group_key, **kwargs):
        """Mock get group members implementation."""
        self.call_count += 1
        if self.should_fail:
            raise Exception("Simulated failure")
        return OperationResult.success(data=[])

    def _list_groups_impl(self, **kwargs):
        """Mock list groups implementation."""
        self.call_count += 1
        if self.should_fail:
            raise Exception("Simulated failure")
        return OperationResult.success(data=[])

    def _list_groups_with_members_impl(self, **kwargs):
        """Mock list groups with members implementation."""
        self.call_count += 1
        if self.should_fail:
            raise Exception("Simulated failure")
        return OperationResult.success(data=[])


class TestProviderCircuitBreakerIntegration:
    """Test circuit breaker integration with providers."""

    def test_provider_circuit_breaker_initialization(self):
        """Test that provider initializes with circuit breaker."""
        provider = MockProvider()

        # Should have circuit breaker
        assert provider._circuit_breaker is not None
        assert provider._circuit_breaker.state == CircuitState.CLOSED

    def test_provider_passes_successful_requests(self):
        """Test that successful requests pass through circuit breaker."""
        provider = MockProvider()
        provider._circuit_breaker.reset()  # Start fresh

        # Should pass through successfully
        member = NormalizedMember(
            email="test@example.com",
            id="user-1",
            role="member",
            provider_member_id="provider-user-1",
        )
        result = provider.add_member("group-1", member)

        assert isinstance(result, OperationResult)
        assert result.status == OperationStatus.SUCCESS
        assert provider._circuit_breaker.state == CircuitState.CLOSED

    def test_provider_opens_circuit_after_threshold_failures(self):
        """Test that circuit opens after failure threshold is reached."""
        provider = MockProvider(failure_threshold=2)
        provider._circuit_breaker.reset()
        provider.should_fail = True

        member = NormalizedMember(
            email="test@example.com",
            id="user-1",
            role="member",
            provider_member_id="provider-user-1",
        )

        # Simulate exactly 2 failures to open circuit (threshold is 2)
        for _ in range(2):
            try:
                provider.remove_member("group-1", member)
            except Exception:
                pass  # Expect exceptions from the underlying impl

        # Circuit should now be OPEN
        assert provider._circuit_breaker.state == CircuitState.OPEN

    def test_provider_rejects_when_circuit_open(self):
        """Test that provider rejects requests when circuit is open."""
        provider = MockProvider(failure_threshold=2)
        provider._circuit_breaker.reset()
        provider.should_fail = True

        member = NormalizedMember(
            email="test@example.com",
            id="user-1",
            role="member",
            provider_member_id="provider-user-1",
        )

        # Trip the circuit with 2 failures
        for i in range(2):
            try:
                provider.add_member("test-group", member)
            except Exception:
                pass  # Expected from underlying impl

        # Circuit should be open
        assert provider._circuit_breaker.state == CircuitState.OPEN

        # Reset should_fail but circuit stays open
        provider.should_fail = False

        # Request should still be rejected with circuit breaker open error
        result = provider.add_member("test-group", member)
        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CIRCUIT_BREAKER_OPEN"

        # Provider method should not have been called
        initial_count = provider.call_count
        result = provider.add_member("test-group", member)
        assert provider.call_count == initial_count  # No additional calls

    def test_provider_circuit_breaker_stats(self):
        """Test that provider exposes circuit breaker stats."""
        provider = MockProvider()

        stats = provider.get_circuit_breaker_stats()

        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert "name" in stats

    def test_provider_manual_reset(self):
        """Test manual reset of provider circuit breaker."""
        provider = MockProvider(failure_threshold=1)
        provider._circuit_breaker.reset()
        provider.should_fail = True

        member = NormalizedMember(
            email="test@example.com",
            id="user-1",
            role="member",
            provider_member_id="provider-user-1",
        )

        # Trip the circuit with 1 failure
        try:
            provider.add_member("test-group", member)
        except Exception:
            pass  # Expected from underlying impl

        assert provider._circuit_breaker.state == CircuitState.OPEN

        # Reset
        provider.reset_circuit_breaker()

        assert provider._circuit_breaker.state == CircuitState.CLOSED

        # Should now work
        provider.should_fail = False
        result = provider.add_member("test-group", member)
        assert result.status == OperationStatus.SUCCESS

    def test_circuit_breaker_disabled_by_config(self):
        """Test that circuit breaker can be disabled via config."""
        with patch("modules.groups.providers.base.settings") as mock_settings:
            mock_settings.groups.circuit_breaker_enabled = False

            provider = MockProvider()

            # Circuit breaker should be None
            assert provider._circuit_breaker is None

    def test_provider_wraps_all_methods(self):
        """Test that all provider methods are wrapped by circuit breaker."""
        provider = MockProvider()

        member = NormalizedMember(
            email="test@example.com",
            id="user-1",
            role="member",
            provider_member_id="provider-user-1",
        )

        # All these methods should trigger the wrapper
        methods = [
            ("add_member", "test-group", member),
            ("remove_member", "test-group", member),
            ("get_group_members", "test-group"),
            ("list_groups",),
            ("list_groups_with_members",),
        ]

        for method_args in methods:
            method_name = method_args[0]
            args = method_args[1:]

            method = getattr(provider, method_name)
            result = method(*args)

            # Should return OperationResult
            assert isinstance(result, OperationResult)
            assert result.status in [
                OperationStatus.SUCCESS,
                OperationStatus.TRANSIENT_ERROR,
            ]

    def test_circuit_breaker_tracks_failures_correctly(self):
        """Test that circuit breaker tracks failures accurately."""
        with patch("core.config.settings") as mock_settings:
            mock_settings.groups.circuit_breaker_enabled = True
            mock_settings.groups.circuit_breaker_failure_threshold = 5
            mock_settings.groups.circuit_breaker_timeout_seconds = 60
            mock_settings.groups.circuit_breaker_half_open_max_calls = 3

            provider = MockProvider()
            provider._circuit_breaker.reset()
            member = NormalizedMember(
                email="test@example.com",
                id="user-1",
                role="member",
                provider_member_id="provider-user-1",
            )

            # Make provider fail
            provider.should_fail = True

            # Fail 3 times
            for i in range(3):
                try:
                    provider.add_member("test-group", member)
                except Exception:
                    pass  # Expected from underlying impl

            stats = provider.get_circuit_breaker_stats()
            assert stats["failure_count"] == 3

            # Succeed once
            provider.should_fail = False
            result = provider.add_member("test-group", member)
            assert result.status == OperationStatus.SUCCESS

            # Failure count should reset on success
            stats = provider.get_circuit_breaker_stats()
            assert stats["failure_count"] == 0

    def test_circuit_breaker_error_code_on_open(self):
        """Test that circuit breaker error code is set correctly."""
        provider = MockProvider(failure_threshold=1)
        provider._circuit_breaker.reset()
        provider.should_fail = True

        member = NormalizedMember(
            email="test@example.com",
            id="user-1",
            role="member",
            provider_member_id="provider-user-1",
        )

        # Trip the circuit
        try:
            provider.add_member("test-group", member)
        except Exception:
            pass  # Expected from underlying impl

        # Now request should be rejected with specific error code
        result = provider.add_member("test-group", member)
        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "CIRCUIT_BREAKER_OPEN"
        assert "OPEN" in result.message

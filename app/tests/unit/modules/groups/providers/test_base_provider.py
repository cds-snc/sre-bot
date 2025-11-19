"""Unit tests for Phase 1 changes to base provider module.

Tests cover:
- validate_member_email() shared function
- Email-based method signatures (add_member, remove_member)
- HealthCheckResult typed return
- CircuitBreakerStats typed return
- Circuit breaker integration with email-based operations
"""

import pytest
from unittest.mock import patch
from modules.groups.providers.base import (
    validate_member_email,
    GroupProvider,
)
from modules.groups.providers.contracts import (
    HealthCheckResult,
    CircuitBreakerStats,
    OperationResult,
    OperationStatus,
)


# ============================================================================
# validate_member_email() Tests
# ============================================================================


@pytest.mark.unit
class TestValidateMemberEmailFunction:
    """Test the shared validate_member_email function."""

    def test_validate_email_valid_standard(self):
        """Test validation of standard email address."""
        result = validate_member_email("user@example.com")
        assert result == "user@example.com"

    def test_validate_email_normalizes_domain_case(self):
        """Test that domain is normalized to lowercase."""
        result = validate_member_email("User@EXAMPLE.COM")
        # email-validator preserves local part case but normalizes domain
        assert result == "User@example.com"

    def test_validate_email_valid_with_dots_in_local(self):
        """Test email with dots in local part."""
        result = validate_member_email("john.doe@example.com")
        assert result == "john.doe@example.com"

    def test_validate_email_valid_with_plus(self):
        """Test email with plus sign in local part."""
        result = validate_member_email("user+tag@example.com")
        assert result == "user+tag@example.com"

    def test_validate_email_valid_subdomain(self):
        """Test email with subdomain."""
        result = validate_member_email("user@mail.example.co.uk")
        assert result == "user@mail.example.co.uk"

    def test_validate_email_empty_string_raises(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Email must be a non-empty string"):
            validate_member_email("")

    def test_validate_email_whitespace_only_raises(self):
        """Test that whitespace-only string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_member_email("   ")

    def test_validate_email_none_raises(self):
        """Test that None raises ValueError."""
        with pytest.raises(ValueError, match="Email must be a non-empty string"):
            validate_member_email(None)

    def test_validate_email_missing_at_raises(self):
        """Test that email without @ raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_member_email("invalidemail")

    def test_validate_email_multiple_at_raises(self):
        """Test that email with multiple @ signs raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_member_email("user@domain@example.com")

    def test_validate_email_empty_local_raises(self):
        """Test that email with empty local part raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_member_email("@example.com")

    def test_validate_email_empty_domain_raises(self):
        """Test that email with empty domain raises ValueError."""
        with pytest.raises(ValueError, match="Invalid email format"):
            validate_member_email("user@")

    def test_validate_email_not_string_raises(self):
        """Test that non-string input raises ValueError."""
        with pytest.raises(ValueError, match="Email must be a non-empty string"):
            validate_member_email(123)

    def test_validate_email_dict_raises(self):
        """Test that dict input raises ValueError."""
        with pytest.raises(ValueError, match="Email must be a non-empty string"):
            validate_member_email({"email": "user@example.com"})


# ============================================================================
# HealthCheckResult Tests
# ============================================================================


@pytest.mark.unit
class TestHealthCheckResult:
    """Test HealthCheckResult dataclass."""

    def test_health_check_result_healthy(self):
        """Test construction of healthy result."""
        result = HealthCheckResult(
            healthy=True,
            status="healthy",
        )
        assert result.healthy is True
        assert result.status == "healthy"
        assert result.details is None
        assert result.timestamp is None

    def test_health_check_result_unhealthy(self):
        """Test construction of unhealthy result."""
        result = HealthCheckResult(
            healthy=False,
            status="unhealthy",
            details={"error": "Connection failed"},
        )
        assert result.healthy is False
        assert result.status == "unhealthy"
        assert result.details == {"error": "Connection failed"}

    def test_health_check_result_degraded(self):
        """Test construction of degraded result."""
        result = HealthCheckResult(
            healthy=False,
            status="degraded",
            details={"latency_ms": 2000},
        )
        assert result.healthy is False
        assert result.status == "degraded"

    def test_health_check_result_with_timestamp(self):
        """Test construction with timestamp."""
        result = HealthCheckResult(
            healthy=True,
            status="healthy",
            timestamp="2025-11-11T12:00:00Z",
        )
        assert result.timestamp == "2025-11-11T12:00:00Z"

    def test_health_check_result_with_all_fields(self):
        """Test construction with all fields."""
        details = {"domain": "example.com", "authenticated": True}
        result = HealthCheckResult(
            healthy=True,
            status="healthy",
            details=details,
            timestamp="2025-11-11T12:00:00Z",
        )
        assert result.healthy is True
        assert result.status == "healthy"
        assert result.details == details
        assert result.timestamp == "2025-11-11T12:00:00Z"


# ============================================================================
# CircuitBreakerStats Tests
# ============================================================================


@pytest.mark.unit
class TestCircuitBreakerStats:
    """Test CircuitBreakerStats dataclass."""

    def test_circuit_breaker_stats_disabled(self):
        """Test stats for disabled circuit breaker."""
        stats = CircuitBreakerStats(
            enabled=False,
            state="CLOSED",
        )
        assert stats.enabled is False
        assert stats.state == "CLOSED"
        assert stats.failure_count == 0
        assert stats.success_count == 0
        assert stats.last_failure_time is None
        assert stats.message is None

    def test_circuit_breaker_stats_closed(self):
        """Test stats for closed circuit breaker."""
        stats = CircuitBreakerStats(
            enabled=True,
            state="CLOSED",
            failure_count=0,
            success_count=5,
        )
        assert stats.enabled is True
        assert stats.state == "CLOSED"
        assert stats.failure_count == 0
        assert stats.success_count == 5

    def test_circuit_breaker_stats_open(self):
        """Test stats for open circuit breaker."""
        stats = CircuitBreakerStats(
            enabled=True,
            state="OPEN",
            failure_count=5,
            success_count=0,
            last_failure_time=1699701600.0,
            message="Too many failures, circuit open",
        )
        assert stats.enabled is True
        assert stats.state == "OPEN"
        assert stats.failure_count == 5
        assert stats.success_count == 0
        assert stats.last_failure_time == 1699701600.0
        assert stats.message == "Too many failures, circuit open"

    def test_circuit_breaker_stats_half_open(self):
        """Test stats for half-open circuit breaker."""
        stats = CircuitBreakerStats(
            enabled=True,
            state="HALF_OPEN",
            failure_count=5,
            success_count=1,
            message="Testing recovery",
        )
        assert stats.state == "HALF_OPEN"
        assert stats.failure_count == 5
        assert stats.success_count == 1


# ============================================================================
# Email-Based Method Signatures Tests
# ============================================================================


@pytest.mark.unit
class TestEmailBasedMethodSignatures:
    """Test that provider methods use email-based signatures."""

    def test_add_member_accepts_email_string(self):
        """Test that add_member method accepts member_email as string."""

        # Create a concrete implementation for testing
        class TestProvider(GroupProvider):
            @property
            def capabilities(self):
                from modules.groups.providers.contracts import ProviderCapabilities

                return ProviderCapabilities()

            def _add_member_impl(self, group_key: str, member_email: str):
                return OperationResult.success()

            def _remove_member_impl(self, group_key: str, member_email: str):
                return OperationResult.success()

            def _get_group_members_impl(self, group_key: str, **kwargs):
                return OperationResult.success()

            def _list_groups_impl(self, **kwargs):
                return OperationResult.success()

            def _list_groups_with_members_impl(self, **kwargs):
                return OperationResult.success()

            def _health_check_impl(self):
                return HealthCheckResult(healthy=True, status="healthy")

        provider = TestProvider()
        result = provider.add_member("group-123", "user@example.com")
        assert result.status == OperationStatus.SUCCESS

    def test_remove_member_accepts_email_string(self):
        """Test that remove_member method accepts member_email as string."""

        class TestProvider(GroupProvider):
            @property
            def capabilities(self):
                from modules.groups.providers.contracts import ProviderCapabilities

                return ProviderCapabilities()

            def _add_member_impl(self, group_key: str, member_email: str):
                return OperationResult.success()

            def _remove_member_impl(self, group_key: str, member_email: str):
                return OperationResult.success()

            def _get_group_members_impl(self, group_key: str, **kwargs):
                return OperationResult.success()

            def _list_groups_impl(self, **kwargs):
                return OperationResult.success()

            def _list_groups_with_members_impl(self, **kwargs):
                return OperationResult.success()

            def _health_check_impl(self):
                return HealthCheckResult(healthy=True, status="healthy")

        provider = TestProvider()
        result = provider.remove_member("group-123", "user@example.com")
        assert result.status == OperationStatus.SUCCESS


# ============================================================================
# Circuit Breaker Integration Tests
# ============================================================================


@pytest.mark.unit
class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with email-based operations."""

    @patch("modules.groups.providers.base.settings")
    def test_circuit_breaker_wraps_add_member_with_email(self, mock_settings):
        """Test circuit breaker wraps add_member correctly with email string."""
        mock_settings.groups.circuit_breaker_enabled = True
        mock_settings.groups.circuit_breaker_failure_threshold = 5
        mock_settings.groups.circuit_breaker_timeout_seconds = 60
        mock_settings.groups.circuit_breaker_half_open_max_calls = 1

        class TestProvider(GroupProvider):
            @property
            def capabilities(self):
                from modules.groups.providers.contracts import ProviderCapabilities

                return ProviderCapabilities()

            def _add_member_impl(self, group_key: str, member_email: str):
                # Validate email is string
                assert isinstance(member_email, str)
                assert "@" in member_email
                return OperationResult.success(data={"email": member_email})

            def _remove_member_impl(self, group_key: str, member_email: str):
                return OperationResult.success()

            def _get_group_members_impl(self, group_key: str, **kwargs):
                return OperationResult.success()

            def _list_groups_impl(self, **kwargs):
                return OperationResult.success()

            def _list_groups_with_members_impl(self, **kwargs):
                return OperationResult.success()

            def _health_check_impl(self):
                return HealthCheckResult(healthy=True, status="healthy")

        provider = TestProvider()
        result = provider.add_member("group-123", "user@example.com")
        assert result.status == OperationStatus.SUCCESS
        assert result.data == {"email": "user@example.com"}

    @patch("modules.groups.providers.base.settings")
    def test_circuit_breaker_stats_available_with_email_operations(self, mock_settings):
        """Test that circuit breaker stats are available after email operations."""
        mock_settings.groups.circuit_breaker_enabled = True
        mock_settings.groups.circuit_breaker_failure_threshold = 5
        mock_settings.groups.circuit_breaker_timeout_seconds = 60
        mock_settings.groups.circuit_breaker_half_open_max_calls = 1

        class TestProvider(GroupProvider):
            @property
            def capabilities(self):
                from modules.groups.providers.contracts import ProviderCapabilities

                return ProviderCapabilities()

            def _add_member_impl(self, group_key: str, member_email: str):
                return OperationResult.success()

            def _remove_member_impl(self, group_key: str, member_email: str):
                return OperationResult.success()

            def _get_group_members_impl(self, group_key: str, **kwargs):
                return OperationResult.success()

            def _list_groups_impl(self, **kwargs):
                return OperationResult.success()

            def _list_groups_with_members_impl(self, **kwargs):
                return OperationResult.success()

            def _health_check_impl(self):
                return HealthCheckResult(healthy=True, status="healthy")

        provider = TestProvider()

        # Perform an operation
        provider.add_member("group-123", "user@example.com")

        # Check stats are available
        stats = provider.get_circuit_breaker_stats()
        assert isinstance(stats, CircuitBreakerStats)
        assert stats.enabled is True
        assert stats.state.lower() == "closed"  # Stats state may be lowercase

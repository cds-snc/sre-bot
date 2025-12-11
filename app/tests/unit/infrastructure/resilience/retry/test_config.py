"""Unit tests for retry configuration."""

import pytest

from infrastructure.resilience.retry.config import RetryConfig


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_create_config_with_defaults(self):
        """Test creating RetryConfig with default values."""
        config = RetryConfig()

        assert config.max_attempts == 5
        assert config.base_delay_seconds == 60
        assert config.max_delay_seconds == 3600
        assert config.batch_size == 10
        assert config.claim_lease_seconds == 300

    def test_create_config_with_custom_values(self, retry_config_factory):
        """Test creating RetryConfig with custom values."""
        config = retry_config_factory(
            max_attempts=3,
            base_delay_seconds=30,
            max_delay_seconds=1800,
            batch_size=5,
            claim_lease_seconds=600,
        )

        assert config.max_attempts == 3
        assert config.base_delay_seconds == 30
        assert config.max_delay_seconds == 1800
        assert config.batch_size == 5
        assert config.claim_lease_seconds == 600

    def test_config_validates_max_attempts(self):
        """Test that max_attempts must be at least 1."""
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=0)

        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryConfig(max_attempts=-1)

    def test_config_validates_base_delay_seconds(self):
        """Test that base_delay_seconds must be at least 1."""
        with pytest.raises(ValueError, match="base_delay_seconds must be at least 1"):
            RetryConfig(base_delay_seconds=0)

        with pytest.raises(ValueError, match="base_delay_seconds must be at least 1"):
            RetryConfig(base_delay_seconds=-1)

    def test_config_validates_max_delay_seconds(self):
        """Test that max_delay_seconds must be >= base_delay_seconds."""
        with pytest.raises(
            ValueError, match="max_delay_seconds must be >= base_delay_seconds"
        ):
            RetryConfig(base_delay_seconds=100, max_delay_seconds=50)

    def test_config_allows_equal_base_and_max_delay(self):
        """Test that base and max delay can be equal."""
        config = RetryConfig(base_delay_seconds=60, max_delay_seconds=60)
        assert config.base_delay_seconds == 60
        assert config.max_delay_seconds == 60

    def test_config_validates_batch_size(self):
        """Test that batch_size must be at least 1."""
        with pytest.raises(ValueError, match="batch_size must be at least 1"):
            RetryConfig(batch_size=0)

        with pytest.raises(ValueError, match="batch_size must be at least 1"):
            RetryConfig(batch_size=-5)

    def test_config_validates_claim_lease_seconds(self):
        """Test that claim_lease_seconds must be at least 1."""
        with pytest.raises(ValueError, match="claim_lease_seconds must be at least 1"):
            RetryConfig(claim_lease_seconds=0)

        with pytest.raises(ValueError, match="claim_lease_seconds must be at least 1"):
            RetryConfig(claim_lease_seconds=-10)

    def test_config_allows_minimal_values(self):
        """Test that config allows all minimum valid values."""
        config = RetryConfig(
            max_attempts=1,
            base_delay_seconds=1,
            max_delay_seconds=1,
            batch_size=1,
            claim_lease_seconds=1,
        )

        assert config.max_attempts == 1
        assert config.base_delay_seconds == 1
        assert config.max_delay_seconds == 1
        assert config.batch_size == 1
        assert config.claim_lease_seconds == 1

    def test_config_allows_large_values(self):
        """Test that config allows large values."""
        config = RetryConfig(
            max_attempts=100,
            base_delay_seconds=300,
            max_delay_seconds=86400,  # 1 day
            batch_size=1000,
            claim_lease_seconds=3600,  # 1 hour
        )

        assert config.max_attempts == 100
        assert config.base_delay_seconds == 300
        assert config.max_delay_seconds == 86400
        assert config.batch_size == 1000
        assert config.claim_lease_seconds == 3600

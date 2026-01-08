"""Unit tests for retry store factory."""

import pytest

from infrastructure.resilience.retry import (
    InMemoryRetryStore,
    create_retry_store,
)
from infrastructure.resilience.retry.dynamodb_store import DynamoDBRetryStore


class TestCreateRetryStore:
    """Tests for create_retry_store factory function."""

    def test_create_memory_store_by_default(self, retry_config_factory, mock_settings):
        """Test that memory store is created by default."""
        config = retry_config_factory()

        store = create_retry_store(config, mock_settings)

        assert isinstance(store, InMemoryRetryStore)
        assert store.config == config

    def test_create_memory_store_explicit(
        self, retry_config_factory, mock_settings_with_dynamodb
    ):
        """Test explicit memory store creation overrides settings."""
        config = retry_config_factory()

        store = create_retry_store(
            config, mock_settings_with_dynamodb, backend="memory"
        )

        assert isinstance(store, InMemoryRetryStore)

    def test_create_dynamodb_store_from_settings(
        self,
        retry_config_factory,
        mock_settings_with_dynamodb,
        mock_dynamodb_next,
        monkeypatch,
    ):
        """Test DynamoDB store creation from settings."""
        monkeypatch.setattr(
            "infrastructure.resilience.retry.dynamodb_store.dynamodb_next",
            mock_dynamodb_next,
        )

        config = retry_config_factory()

        store = create_retry_store(config, mock_settings_with_dynamodb)

        assert isinstance(store, DynamoDBRetryStore)
        assert store.table_name == "test-retry-records"
        assert store.ttl_days == 30

    def test_create_dynamodb_store_explicit(
        self,
        retry_config_factory,
        mock_settings,
        mock_dynamodb_next,
        monkeypatch,
    ):
        """Test explicit DynamoDB store creation."""
        config = retry_config_factory()

        # Update settings for DynamoDB
        mock_settings.retry.backend = "dynamodb"
        mock_settings.retry.dynamodb_table_name = "explicit-table"

        monkeypatch.setattr(
            "infrastructure.resilience.retry.dynamodb_store.dynamodb_next",
            mock_dynamodb_next,
        )

        store = create_retry_store(config, mock_settings, backend="dynamodb")

        assert isinstance(store, DynamoDBRetryStore)

    def test_create_store_unknown_backend_raises_error(
        self, retry_config_factory, mock_settings
    ):
        """Test that unknown backend raises ValueError."""
        config = retry_config_factory()

        with pytest.raises(ValueError, match="Unknown retry backend: redis"):
            create_retry_store(config, mock_settings, backend="redis")

    def test_create_memory_store_uses_config(self, retry_config_factory, mock_settings):
        """Test that created memory store uses provided config."""
        config = retry_config_factory(
            max_attempts=10,
            base_delay_seconds=30,
            batch_size=20,
        )

        store = create_retry_store(config, mock_settings)
        assert store.config.batch_size == 20

    def test_create_dynamodb_store_uses_config(
        self,
        retry_config_factory,
        mock_settings_with_dynamodb,
        mock_dynamodb_next,
        monkeypatch,
    ):
        """Test that created DynamoDB store uses provided config."""
        monkeypatch.setattr(
            "infrastructure.resilience.retry.dynamodb_store.dynamodb_next",
            mock_dynamodb_next,
        )

        config = retry_config_factory(
            max_attempts=7,
            base_delay_seconds=45,
        )

        store = create_retry_store(config, mock_settings_with_dynamodb)

        assert store.config.max_attempts == 7
        assert store.config.base_delay_seconds == 45

    def test_factory_respects_backend_parameter_over_settings(
        self, retry_config_factory, mock_settings_with_dynamodb
    ):
        """Test that backend parameter overrides settings."""
        config = retry_config_factory()

        # Settings say dynamodb, but we explicitly request memory
        store = create_retry_store(
            config, mock_settings_with_dynamodb, backend="memory"
        )

        assert isinstance(store, InMemoryRetryStore)
        assert not isinstance(store, DynamoDBRetryStore)

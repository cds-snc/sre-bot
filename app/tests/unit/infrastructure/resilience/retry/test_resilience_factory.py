"""Unit tests for retry store factory."""

import importlib
from types import SimpleNamespace

import pytest

from infrastructure.resilience.retry import (
    InMemoryRetryStore,
    create_retry_store,
)
from infrastructure.resilience.retry.dynamodb_store import DynamoDBRetryStore
from infrastructure.services.providers import get_settings


class TestCreateRetryStore:
    """Tests for create_retry_store factory function."""

    def test_create_memory_store_by_default(
        self, retry_config_factory, mock_settings_memory_backend
    ):
        """Test that memory store is created by default."""
        config = retry_config_factory()

        store = create_retry_store(config)

        assert isinstance(store, InMemoryRetryStore)
        assert store.config == config

    def test_create_memory_store_explicit(
        self, retry_config_factory, mock_settings_dynamodb_backend
    ):
        """Test explicit memory store creation overrides settings."""
        config = retry_config_factory()

        store = create_retry_store(config, backend="memory")

        assert isinstance(store, InMemoryRetryStore)

    def test_create_dynamodb_store_from_settings(
        self,
        retry_config_factory,
        mock_settings_dynamodb_backend,
        mock_dynamodb_next,
        monkeypatch,
    ):
        """Test DynamoDB store creation from settings."""
        monkeypatch.setattr(
            "infrastructure.resilience.retry.dynamodb_store.dynamodb_next",
            mock_dynamodb_next,
        )

        config = retry_config_factory()
        store = create_retry_store(config)

        assert isinstance(store, DynamoDBRetryStore)
        assert store.table_name == "test-retry-records"
        assert store.ttl_days == 30

    def test_create_dynamodb_store_explicit(
        self,
        retry_config_factory,
        mock_settings_memory_backend,
        mock_dynamodb_next,
        monkeypatch,
    ):
        """Test explicit DynamoDB store creation."""
        config = retry_config_factory()

        # Update settings for DynamoDB
        mock_settings_memory_backend.backend = "dynamodb"
        mock_settings_memory_backend.dynamodb_table_name = "explicit-table"

        monkeypatch.setattr(
            "infrastructure.resilience.retry.dynamodb_store.dynamodb_next",
            mock_dynamodb_next,
        )

        store = create_retry_store(config, backend="dynamodb")

        assert isinstance(store, DynamoDBRetryStore)

    def test_create_store_unknown_backend_raises_error(
        self, retry_config_factory, mock_settings_memory_backend
    ):
        """Test that unknown backend raises ValueError."""
        config = retry_config_factory()

        with pytest.raises(ValueError, match="Unknown retry backend: redis"):
            create_retry_store(config, backend="redis")

    def test_create_memory_store_uses_config(self, retry_config_factory, monkeypatch):
        """Test that created memory store uses provided config."""

        # Clear the lru_cache on get_settings before mocking
        get_settings.cache_clear()

        mock_retry_settings = SimpleNamespace(backend="memory")
        mock_settings = SimpleNamespace(retry=mock_retry_settings)

        monkeypatch.setattr(
            "infrastructure.services.providers.get_settings",
            lambda: mock_settings,
        )

        # Re-import factory module so it picks up the mocked get_settings
        import infrastructure.resilience.retry.factory

        importlib.reload(infrastructure.resilience.retry.factory)

        config = retry_config_factory(
            max_attempts=10,
            base_delay_seconds=30,
            batch_size=20,
        )

        store = infrastructure.resilience.retry.factory.create_retry_store(config)
        assert store.config.batch_size == 20

    def test_create_dynamodb_store_uses_config(
        self,
        retry_config_factory,
        mock_settings_dynamodb_backend,
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

        store = create_retry_store(config)

        assert store.config.max_attempts == 7
        assert store.config.base_delay_seconds == 45

    def test_factory_respects_backend_parameter_over_settings(
        self, retry_config_factory, mock_settings_dynamodb_backend
    ):
        """Test that backend parameter overrides settings."""
        config = retry_config_factory()

        # Settings say dynamodb, but we explicitly request memory
        store = create_retry_store(config, backend="memory")

        assert isinstance(store, InMemoryRetryStore)
        assert not isinstance(store, DynamoDBRetryStore)

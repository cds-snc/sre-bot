"""Unit tests for retry store factory."""

from unittest.mock import MagicMock

import pytest

from infrastructure.resilience.retry import (
    InMemoryRetryStore,
    create_retry_store,
)
from infrastructure.resilience.retry import factory as retry_factory
from infrastructure.resilience.retry.dynamodb_store import DynamoDBRetryStore


class TestCreateRetryStore:
    """Tests for create_retry_store factory function."""

    def test_create_memory_store_by_default(self, retry_config_factory, mock_settings):
        """Test that memory store is created by default."""
        config = retry_config_factory()

        store = create_retry_store(config, mock_settings)

        assert isinstance(store, InMemoryRetryStore)
        assert store.config == config

    def test_create_memory_store_explicit(self, retry_config_factory, mock_settings_with_dynamodb):
        """Test explicit memory store creation overrides settings."""
        config = retry_config_factory()

        store = create_retry_store(config, mock_settings_with_dynamodb, backend="memory")

        assert isinstance(store, InMemoryRetryStore)

    def test_create_dynamodb_store_from_settings(
        self,
        retry_config_factory,
        mock_settings_with_dynamodb,
        mock_dynamodb_client,
        monkeypatch,
    ):
        """Test DynamoDB store creation from settings."""
        monkeypatch.setattr(
            retry_factory,
            "get_aws_client",
            lambda *args, **kwargs: mock_dynamodb_client,
            raising=False,
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
        mock_dynamodb_client,
        monkeypatch,
    ):
        """Test explicit DynamoDB store creation."""
        config = retry_config_factory()

        # Update settings for DynamoDB
        mock_settings.backend = "dynamodb"
        mock_settings.dynamodb_table_name = "explicit-table"

        monkeypatch.setattr(
            retry_factory,
            "get_aws_client",
            lambda *args, **kwargs: mock_dynamodb_client,
            raising=False,
        )

        store = create_retry_store(config, mock_settings, backend="dynamodb")

        assert isinstance(store, DynamoDBRetryStore)

    def test_create_store_unknown_backend_raises_error(self, retry_config_factory, mock_settings):
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
        mock_dynamodb_client,
        monkeypatch,
    ):
        """Test that created DynamoDB store uses provided config."""
        monkeypatch.setattr(
            retry_factory,
            "get_aws_client",
            lambda *args, **kwargs: mock_dynamodb_client,
            raising=False,
        )

        config = retry_config_factory(
            max_attempts=7,
            base_delay_seconds=45,
        )

        store = create_retry_store(config, mock_settings_with_dynamodb)

        assert store.config.max_attempts == 7
        assert store.config.base_delay_seconds == 45

    def test_create_dynamodb_store_injects_client(
        self,
        retry_config_factory,
        mock_settings_with_dynamodb,
        monkeypatch,
    ):
        """The DynamoDB backend obtains one shared client and injects it into the store."""
        dynamodb_client = MagicMock()
        get_aws_client = MagicMock(return_value=dynamodb_client)
        monkeypatch.setattr(retry_factory, "get_aws_client", get_aws_client, raising=False)

        store = create_retry_store(retry_config_factory(), mock_settings_with_dynamodb)

        get_aws_client.assert_called_once_with("dynamodb")
        assert store._dynamodb is dynamodb_client

    def test_factory_respects_backend_parameter_over_settings(self, retry_config_factory, mock_settings_with_dynamodb):
        """Test that backend parameter overrides settings."""
        config = retry_config_factory()

        # Settings say dynamodb, but we explicitly request memory
        store = create_retry_store(config, mock_settings_with_dynamodb, backend="memory")

        assert isinstance(store, InMemoryRetryStore)
        assert not isinstance(store, DynamoDBRetryStore)

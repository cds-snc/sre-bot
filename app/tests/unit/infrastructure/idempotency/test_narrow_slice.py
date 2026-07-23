"""Tests for PR-11: IdempotencyService and DynamoDBCache narrow-slice dissolution."""

from unittest.mock import MagicMock

import pytest

from infrastructure.configuration.infrastructure.idempotency import IdempotencySettings
from infrastructure.idempotency.cache import IdempotencyCache
from infrastructure.idempotency.dynamodb import DynamoDBCache
from infrastructure.idempotency.service import DynamoDBIdempotencyService

pytestmark = pytest.mark.unit


class TestDynamoDBCacheAcceptsInjectedSettings:
    """DynamoDBCache accepts only narrow IdempotencySettings (no full Settings)."""

    def test_dynamodb_cache_constructs_with_idempotency_settings(self):
        """DynamoDBCache constructs with narrow IdempotencySettings slice."""
        mock_settings = MagicMock(spec=IdempotencySettings)
        mock_settings.IDEMPOTENCY_TTL_SECONDS = 3600
        cache = DynamoDBCache(idempotency_settings=mock_settings)
        assert cache is not None

    def test_dynamodb_cache_reads_ttl_from_idempotency_settings(self):
        """DynamoDBCache reads TTL from the narrow settings slice."""
        mock_settings = MagicMock(spec=IdempotencySettings)
        mock_settings.IDEMPOTENCY_TTL_SECONDS = 7200
        cache = DynamoDBCache(idempotency_settings=mock_settings)
        assert cache.ttl_seconds == 7200

    def test_dynamodb_cache_rejects_full_settings_kwarg(self):
        """DynamoDBCache does not accept a 'settings' kwarg."""
        with pytest.raises(TypeError):
            DynamoDBCache(settings=MagicMock())


class TestIdempotencyServiceReceivesConstructedCache:
    """DynamoDBIdempotencyService accepts only a pre-built cache (composition root in providers.py)."""

    def test_service_constructs_with_pre_built_cache(self):
        """DynamoDBIdempotencyService constructs with an injected cache."""
        mock_cache = MagicMock(spec=IdempotencyCache)
        service = DynamoDBIdempotencyService(cache=mock_cache)
        assert service is not None

    def test_service_delegates_get_to_cache(self):
        """DynamoDBIdempotencyService.get() delegates to the injected cache."""
        mock_cache = MagicMock(spec=IdempotencyCache)
        mock_cache.get.return_value = {"status": "ok"}
        service = DynamoDBIdempotencyService(cache=mock_cache)
        result = service.get("some-key")
        mock_cache.get.assert_called_once_with("some-key")
        assert result == {"status": "ok"}

    def test_service_delegates_set_to_cache(self):
        """DynamoDBIdempotencyService.set() delegates to the injected cache."""
        mock_cache = MagicMock(spec=IdempotencyCache)
        service = DynamoDBIdempotencyService(cache=mock_cache)
        service.set("key", {"data": 1}, ttl_seconds=3600)
        mock_cache.set.assert_called_once_with("key", {"data": 1}, 3600)

    def test_service_no_idempotency_settings_parameter(self):
        """DynamoDBIdempotencyService no longer accepts idempotency_settings (moved to providers)."""
        mock_cache = MagicMock(spec=IdempotencyCache)
        with pytest.raises(TypeError):
            DynamoDBIdempotencyService(idempotency_settings=MagicMock(), cache=mock_cache)

"""
Unit tests for dependency injection providers.

Tests cover:
- get_settings() caching behavior
- SettingsDep type alias with FastAPI dependency injection
- Dependency override pattern for testing
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from infrastructure.services.providers import get_settings
from infrastructure.services.dependencies import SettingsDep
from infrastructure.configuration import Settings


class TestGetSettings:
    """Tests for get_settings() provider function."""

    def test_get_settings_returns_settings_instance(self):
        """get_settings() returns a Settings instance."""
        result = get_settings()
        assert isinstance(result, Settings)

    def test_get_settings_returns_cached_instance(self):
        """get_settings() returns the same instance (caching)."""
        result1 = get_settings()
        result2 = get_settings()
        assert result1 is result2

    def test_get_settings_cache_can_be_cleared(self):
        """get_settings() cache can be cleared for testing."""
        instance1 = get_settings()
        get_settings.cache_clear()
        instance2 = get_settings()
        assert instance1 is not instance2


class TestDependencyOverridePattern:
    """Tests for FastAPI dependency override pattern."""

    def test_settings_dep_with_dependency_override(self):
        """SettingsDep can be overridden in FastAPI app."""
        app = FastAPI()

        @app.get("/config")
        def get_config(settings: SettingsDep) -> dict:
            return {
                "has_settings": True,
                "is_settings_instance": isinstance(settings, Settings),
            }

        # Create mock settings
        mock_settings = MagicMock(spec=Settings)

        # Override the dependency
        app.dependency_overrides[get_settings] = lambda: mock_settings

        # Test with client
        with TestClient(app) as client:
            response = client.get("/config")

        assert response.status_code == 200
        assert response.json()["has_settings"] is True

        # Cleanup
        app.dependency_overrides.clear()


class TestDependencyOverrideCleanup:
    """Tests for proper cleanup of dependency overrides."""

    def test_override_cleanup_restores_original(self):
        """Clearing overrides restores original provider behavior."""
        app = FastAPI()

        @app.get("/original")
        def original(settings: SettingsDep) -> dict:
            return {"is_real_settings": isinstance(settings, Settings)}

        # Test original behavior (before any overrides)
        with TestClient(app) as client:
            original_response = client.get("/original").json()
            assert original_response["is_real_settings"] is True

        # Override and test
        mock_settings = MagicMock(spec=Settings)
        app.dependency_overrides[get_settings] = lambda: mock_settings

        with TestClient(app) as client:
            overridden_response = client.get("/original")
            # Mock object doesn't have dict() method, so response should work differently
            assert overridden_response.status_code == 200

        # Clear and test restored behavior
        app.dependency_overrides.clear()
        get_settings.cache_clear()

        with TestClient(app) as client:
            restored_response = client.get("/original").json()
            assert restored_response["is_real_settings"] is True

    @pytest.fixture(autouse=True)
    def cleanup_provider_cache(self):
        """Clear provider caches after each test."""
        yield
        get_settings.cache_clear()

    @pytest.fixture(autouse=True)
    def cleanup_dependency_overrides(self):
        """Clear dependency overrides after each test."""
        yield
        # Note: Can't clear app-level overrides here without app reference
        # Each test should clean up its own app.dependency_overrides

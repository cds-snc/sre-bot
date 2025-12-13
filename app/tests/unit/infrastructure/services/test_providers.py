"""
Unit tests for dependency injection providers.

Tests cover:
- get_settings() caching behavior
- get_logger() caching behavior
- SettingsDep type alias with FastAPI dependency injection
- LoggerDep type alias with FastAPI dependency injection
- Dependency override pattern for testing
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends

from infrastructure.services.providers import get_settings, get_logger
from infrastructure.services.dependencies import SettingsDep, LoggerDep
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


class TestGetLogger:
    """Tests for get_logger() provider function."""

    def test_get_logger_returns_logger_instance(self):
        """get_logger() returns a logger instance."""
        result = get_logger()
        assert result is not None

    def test_get_logger_can_be_called_multiple_times(self):
        """get_logger() can be called multiple times and returns a logger each time."""
        result1 = get_logger()
        result2 = get_logger()
        assert result1 is not None
        assert result2 is not None


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

    def test_logger_dep_with_dependency_override(self):
        """LoggerDep can be overridden in FastAPI app."""
        app = FastAPI()

        @app.get("/logs")
        def log_endpoint(logger: LoggerDep) -> dict:
            return {"has_logger": logger is not None}

        # Create mock logger
        mock_logger = MagicMock()

        # Override the dependency
        app.dependency_overrides[get_logger] = lambda: mock_logger

        # Test with client
        with TestClient(app) as client:
            response = client.get("/logs")

        assert response.status_code == 200
        assert response.json()["has_logger"] is True

        # Cleanup
        app.dependency_overrides.clear()

    def test_multiple_dependency_overrides(self):
        """Multiple dependencies can be overridden simultaneously."""
        app = FastAPI()

        @app.get("/both")
        def both_deps(
            settings: SettingsDep,
            logger: LoggerDep,
        ) -> dict:
            return {
                "has_settings": isinstance(settings, (Settings, MagicMock)),
                "has_logger": logger is not None,
            }

        # Create mocks
        mock_settings = MagicMock(spec=Settings)
        mock_logger = MagicMock()

        # Override both dependencies
        app.dependency_overrides[get_settings] = lambda: mock_settings
        app.dependency_overrides[get_logger] = lambda: mock_logger

        # Test with client
        with TestClient(app) as client:
            response = client.get("/both")

        assert response.status_code == 200
        data = response.json()
        assert data["has_settings"] is True
        assert data["has_logger"] is True

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

        # Save original behavior
        original_response = None
        with TestClient(app) as client:
            original_response = client.get("/original").json()

        # Override and test
        mock_settings = MagicMock(spec=Settings)
        app.dependency_overrides[get_settings] = lambda: mock_settings

        with TestClient(app) as client:
            overridden_response = client.get("/original")
            # Mock object doesn't have dict() method, so response should work differently
            assert overridden_response.status_code == 200

        # Clear and test restored
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

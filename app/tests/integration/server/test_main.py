"""Integration tests for main module."""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.mark.integration
def test_main_app_can_be_used_with_test_client():
    """Test that main.app can be used with FastAPI TestClient."""
    # Assert - should not raise
    assert client is not None


@pytest.mark.integration
def test_main_app_handles_http_requests():
    """Test that the app exported from main can handle HTTP requests."""
    # Act
    response = client.get("/test-unmapped-route")

    # Assert - Should get 404 for unmapped route
    assert response.status_code == 404

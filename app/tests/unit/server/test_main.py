"""Unit tests for main module."""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.mark.unit
def test_main_app_handles_unmapped_routes():
    """Test that the app returns 404 for unmapped routes."""
    # Act
    response = client.get("/test-unmapped-route")

    # Assert
    assert response.status_code == 404

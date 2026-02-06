"""Test fixtures for geolocate integration tests."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create FastAPI app with geolocate router."""
    from packages.geolocate.routes import router

    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    with TestClient(app) as client:
        yield client

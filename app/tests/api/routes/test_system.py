from unittest.mock import patch
from fastapi.testclient import TestClient
from api.routes import system
from utils.tests import create_test_app

test_app = create_test_app(system.router)


def test_get_version_unkown():
    with TestClient(test_app) as client:
        response = client.get("/version")
        assert response.status_code == 200
        assert response.json() == {"version": "Unknown"}


@patch("core.config.settings.GIT_SHA", "foo")
def test_get_version_known():
    with TestClient(test_app) as client:
        response = client.get("/version")
        assert response.status_code == 200
        assert response.json() == {"version": "foo"}


def test_health():
    with TestClient(test_app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

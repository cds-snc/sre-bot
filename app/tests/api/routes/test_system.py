from fastapi.testclient import TestClient

from api.routes import system
from contracts.configuration import HostInfo, install_host_info
from utils.tests import create_test_app

test_app = create_test_app(system.router)


def test_get_version_unkown():
    install_host_info(HostInfo(environment="ci", git_sha="Unknown", public_base_url="http://127.0.0.1:8000"))
    with TestClient(test_app) as client:
        response = client.get("/version")
        assert response.status_code == 200
        assert response.json() == {"version": "Unknown"}


def test_get_version_known():
    install_host_info(HostInfo(environment="ci", git_sha="foo", public_base_url="http://127.0.0.1:8000"))
    with TestClient(test_app) as client:
        response = client.get("/version")
        assert response.status_code == 200
        assert response.json() == {"version": "foo"}


def test_health():
    with TestClient(test_app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

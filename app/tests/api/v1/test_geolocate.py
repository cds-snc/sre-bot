from unittest.mock import patch
from fastapi.testclient import TestClient
from api.v1.routes import geolocate
from utils.tests import create_test_app

test_app = create_test_app(geolocate.router)
client = TestClient(test_app)


@patch("api.v1.routes.geolocate.maxmind.geolocate")
def test_geolocate_success(mock_geolocate):
    mock_geolocate.return_value = "country", "city", "latitude", "longitude"
    response = client.get("/geolocate/111.111.111.111")
    assert response.status_code == 200
    assert response.json() == {
        "country": "country",
        "city": "city",
        "latitude": "latitude",
        "longitude": "longitude",
    }


@patch("api.v1.routes.geolocate.maxmind.geolocate")
def test_geolocate_failure(mock_geolocate):
    mock_geolocate.return_value = "error"
    response = client.get("/geolocate/111")
    assert response.status_code == 404
    assert response.json() == {"detail": "error"}

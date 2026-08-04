from unittest.mock import patch

from fastapi.testclient import TestClient

from api.v1.routes import geolocate
from utils.tests import create_test_app

test_app = create_test_app(geolocate.router)


@patch("api.v1.routes.geolocate.maxmind.geolocate")
def test_geolocate_success(mock_geolocate):
    mock_geolocate.return_value = "country", "city", 0, 0
    with TestClient(test_app) as client:
        response = client.get("/geolocate/111.111.111.111")
        assert response.status_code == 200
        assert response.json() == {
            "country": "country",
            "city": "city",
            "latitude": 0,
            "longitude": 0,
            "map_links": {
                "openstreetmap": "https://www.openstreetmap.org/?mlat=0&mlon=0#map=12/0/0",
                "opentopomap": "https://opentopomap.org/#map=12/0/0",
            },
        }


@patch("api.v1.routes.geolocate.maxmind.geolocate")
def test_geolocate_failure(mock_geolocate):
    mock_geolocate.return_value = "error"
    with TestClient(test_app) as client:
        response = client.get("/geolocate/111")
        assert response.status_code == 404
        assert response.json() == {"detail": "error"}

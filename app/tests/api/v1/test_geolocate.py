from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from api.v1.routes import geolocate
from infrastructure.operations import OperationResult, OperationStatus
from utils.tests import create_test_app

test_app = create_test_app(geolocate.router)


def _client_returning(result: OperationResult) -> Mock:
    """Build a MaxMind client double whose geolocate returns the given OperationResult."""
    client = Mock()
    client.geolocate.return_value = result
    return client


@patch("api.v1.routes.geolocate.maxmind.get_maxmind_client")
def test_geolocate_success(mock_get_client):
    mock_get_client.return_value = _client_returning(
        OperationResult.success(
            data={
                "country_code": "country",
                "city": "city",
                "latitude": 0,
                "longitude": 0,
                "postal_code": "postal",
                "time_zone": "tz",
            },
            message="IP geolocated successfully",
        )
    )
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


@patch("api.v1.routes.geolocate.maxmind.get_maxmind_client")
def test_geolocate_not_found_returns_404(mock_get_client):
    mock_get_client.return_value = _client_returning(
        OperationResult(
            status=OperationStatus.NOT_FOUND,
            message="IP address not found in database: 111.111.111.111",
            error_code="IP_NOT_FOUND",
        )
    )
    with TestClient(test_app) as client:
        response = client.get("/geolocate/111.111.111.111")
        assert response.status_code == 404
        assert response.json() == {"detail": "IP address not found in database: 111.111.111.111"}


@patch("api.v1.routes.geolocate.maxmind.get_maxmind_client")
def test_geolocate_invalid_ip_returns_400(mock_get_client):
    mock_get_client.return_value = _client_returning(
        OperationResult.permanent_error(
            message="Invalid IP address format: 111",
            error_code="INVALID_IP_FORMAT",
        )
    )
    with TestClient(test_app) as client:
        response = client.get("/geolocate/111")
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid IP address format: 111"}


@patch("api.v1.routes.geolocate.maxmind.get_maxmind_client")
def test_geolocate_transient_error_returns_503(mock_get_client):
    mock_get_client.return_value = _client_returning(
        OperationResult.transient_error(
            message="GeoIP2 database error: db down",
            error_code="GEOIP2_ERROR",
        )
    )
    with TestClient(test_app) as client:
        response = client.get("/geolocate/111.111.111.111")
        assert response.status_code == 503
        assert response.json() == {"detail": "GeoIP2 database error: db down"}


@patch("api.v1.routes.geolocate.maxmind.get_maxmind_client")
def test_geolocate_does_not_use_legacy_tuple_api(mock_get_client):
    """The route consumes the OperationResult client, not the legacy module-level function."""
    mock_get_client.return_value = _client_returning(
        OperationResult.success(
            data={"country_code": "CA", "city": "Ottawa", "latitude": 45.0, "longitude": -75.0},
            message="IP geolocated successfully",
        )
    )
    with TestClient(test_app) as client:
        client.get("/geolocate/111.111.111.111")

    mock_get_client.assert_called_once_with()
    mock_get_client.return_value.geolocate.assert_called_once_with(ip_address="111.111.111.111")
    assert not hasattr(geolocate.maxmind, "geolocate")

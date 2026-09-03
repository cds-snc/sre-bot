"""Integration tests for get_federal_holidays' outbound HTTP call after relocation."""

from datetime import datetime
from unittest.mock import patch

from packages.incident.scheduling import availability


def test_get_federal_holidays(requests_mock):
    requests_mock.DEFAULT_TIMEOUT = 10

    current_year = datetime.now().year
    mocked_response = {
        "holidays": [
            {"observedDate": "2024-01-01"},
            {"observedDate": "2024-07-01"},
            {"observedDate": "2024-12-25"},
        ]
    }
    requests_mock.get(  # nosec
        "https://canada-holidays.ca/api/v1/holidays?federal=true&year=" + str(current_year),
        json=mocked_response,
    )

    holidays = availability.get_federal_holidays()

    assert holidays == ["2024-01-01", "2024-07-01", "2024-12-25"]


def test_get_federal_holidays_with_different_year(requests_mock):
    requests_mock.DEFAULT_TIMEOUT = 10
    requests_mock.get(  # nosec
        "https://canada-holidays.ca/api/v1/holidays?federal=true&year=2025",
        json={"holidays": []},
    )

    with patch("packages.incident.scheduling.availability.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2025, 1, 1)

        holidays = availability.get_federal_holidays()

        assert holidays == []


def test_api_returns_empty_list(requests_mock):
    requests_mock.DEFAULT_TIMEOUT = 10

    current_year = datetime.now().year
    requests_mock.get(  # nosec
        "https://canada-holidays.ca/api/v1/holidays?federal=true&year=" + str(current_year),
        json={"holidays": []},
    )

    holidays = availability.get_federal_holidays()

    assert holidays == [], "Expected an empty list when there are no holidays"


def test_get_federal_holidays_server_error(requests_mock):
    """Test that server errors are handled gracefully and return empty list."""
    requests_mock.DEFAULT_TIMEOUT = 10

    current_year = datetime.now().year
    requests_mock.get(  # nosec
        f"https://canada-holidays.ca/api/v1/holidays?federal=true&year={current_year}",
        status_code=500,
        text="Internal Server Error",
    )

    holidays = availability.get_federal_holidays()

    assert holidays == [], "Expected an empty list when server returns error"


def test_leap_year_handling(requests_mock):
    requests_mock.DEFAULT_TIMEOUT = 10

    with patch("packages.incident.scheduling.availability.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2024, 6, 15)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        requests_mock.get(  # nosec
            "https://canada-holidays.ca/api/v1/holidays?federal=true&year=2024",
            json={"holidays": [{"observedDate": "2024-02-29"}]},
        )

        holidays = availability.get_federal_holidays()

        assert "2024-02-29" in holidays, "Leap year date should be included in the holidays"

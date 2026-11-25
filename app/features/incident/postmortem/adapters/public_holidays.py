"""Public-holiday lookup of the incident postmortem: Canadian federal holidays from canada-holidays.ca.

The legacy retro flow's lookup; ``CanadaHolidaysCalendar`` (adapters/canada_holidays.py)
is the ``HolidayCalendar`` the schedule service uses.

TODO(TASK-145.10.4): delete with the legacy retro flow.
"""

from datetime import datetime

import requests
import structlog

logger = structlog.get_logger()


def get_federal_holidays():
    # Get the public holidays for the current year
    # Uses Paul Craig's Public holidays api to retrieve the federal holidays (https://canada-holidays.ca/api)
    holidays = []

    # get today's year
    year = datetime.now().year

    # call the api to get the public holidays
    url = f"https://canada-holidays.ca/api/v1/holidays?federal=true&year={year}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        for holiday in response.json().get("holidays", []):
            holidays.append(holiday["observedDate"])
    except requests.exceptions.RequestException as e:
        logger.error(
            "federal_holidays_request_failed",
            error=str(e),
            year=year,
        )
    return holidays

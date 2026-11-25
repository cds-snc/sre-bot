"""Canada Holidays vendor package: the client factory, its error classifier and the settings slice."""

from .client import build_canada_holidays_client, classify_canada_holidays_error
from .settings import CanadaHolidaysSettings, CanadaHolidaysTenant, get_canada_holidays_settings

__all__ = [
    "CanadaHolidaysSettings",
    "CanadaHolidaysTenant",
    "build_canada_holidays_client",
    "classify_canada_holidays_error",
    "get_canada_holidays_settings",
]

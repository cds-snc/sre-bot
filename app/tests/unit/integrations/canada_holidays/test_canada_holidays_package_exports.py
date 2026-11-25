"""The Canada Holidays vendor package exports only its client factory, its classifier and its settings.

Read from the package's ``__all__``: the holiday lookup itself lives with its consumer
(decisions/outbound-clients.md), never in ``integrations.canada_holidays``.
"""

import pytest

from integrations import canada_holidays

pytestmark = pytest.mark.unit


def test_the_package_exports_the_factory_the_classifier_and_the_settings() -> None:
    assert sorted(canada_holidays.__all__) == [
        "CanadaHolidaysSettings",
        "CanadaHolidaysTenant",
        "build_canada_holidays_client",
        "classify_canada_holidays_error",
        "get_canada_holidays_settings",
    ]

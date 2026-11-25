"""Interfaces of the incident postmortem subdomain.

``HolidayCalendar`` reads the observed federal holidays the postmortem meeting
search skips; ``adapters/canada_holidays.py`` is the Canada Holidays API one and
``adapters/in_memory.py`` the fake.
"""

from collections.abc import Collection
from datetime import date
from typing import Protocol, runtime_checkable

from contracts.operations.result import OperationResult


@runtime_checkable
class HolidayCalendar(Protocol):
    """Interface reading observed federal holidays; it holds no policy on what a failure means.

    Async; platform failures are classified results, never exceptions, and never an
    empty set standing in for "unknown": whether a search goes on without holidays is
    the caller's decision.
    """

    async def observed_federal_holidays(self, years: Collection[int]) -> OperationResult[frozenset[date]]:
        """Return the observed dates of the federal holidays of every year in ``years``.

        A search window may cross a year end, so the caller names each year it spans.
        No year is an empty set.
        """
        ...

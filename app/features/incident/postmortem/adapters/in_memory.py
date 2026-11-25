"""In-memory incident postmortem adapters with the real implementations' observable rules.

``InMemoryHolidayCalendar``: the ``CanadaHolidaysCalendar`` rules (only the asked
years' dates, no year an empty set, a failure a result and never an empty set).
"""

from collections.abc import Collection
from datetime import date

from contracts.operations.result import OperationResult
from features.incident.postmortem.interfaces import HolidayCalendar


class InMemoryHolidayCalendar(HolidayCalendar):
    """Answer from the observed holiday dates it is built with; ``asked`` records each request's years.

    ``fail_with`` makes every read return that error result instead.
    """

    def __init__(self, holidays: Collection[date] = (), *, fail_with: OperationResult[frozenset[date]] | None = None) -> None:
        self._holidays = frozenset(holidays)
        self.fail_with = fail_with
        self.asked: list[frozenset[int]] = []

    async def observed_federal_holidays(self, years: Collection[int]) -> OperationResult[frozenset[date]]:
        """Return the stored dates falling in the asked years, or the configured failure."""
        asked = frozenset(years)
        self.asked.append(asked)
        if self.fail_with is not None and asked:
            return self.fail_with
        return OperationResult.success(frozenset(day for day in self._holidays if day.year in asked))

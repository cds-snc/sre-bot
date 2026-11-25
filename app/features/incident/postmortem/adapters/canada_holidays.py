"""Canada Holidays adapter of the incident postmortem: the ``HolidayCalendar`` over canada-holidays.ca.

One GET per year (``holidays?federal=true&year=Y``) through the vendor client
(integrations/canada_holidays), reading each holiday's ``observedDate``: the
day off when a holiday falls on a weekend. Failures and answers of the wrong
shape are classified results.
"""

from collections.abc import Callable, Collection, Mapping
from datetime import date

import httpx
import structlog

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from features.incident.postmortem.interfaces import HolidayCalendar
from integrations.canada_holidays.client import build_canada_holidays_client, classify_canada_holidays_error
from integrations.canada_holidays.settings import get_canada_holidays_settings

logger = structlog.get_logger()


class _InvalidAnswer(Exception):
    """The API answered with a body of the wrong shape."""


def _observed_dates(payload: object) -> set[date]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("holidays"), list):
        raise _InvalidAnswer("an answer without a holidays list")
    dates: set[date] = set()
    for holiday in payload["holidays"]:
        observed = holiday.get("observedDate") if isinstance(holiday, Mapping) else None
        if not isinstance(observed, str):
            raise _InvalidAnswer("a holiday without an observed date")
        try:
            dates.add(date.fromisoformat(observed))
        except ValueError as exc:
            raise _InvalidAnswer("a holiday whose observed date is not an ISO date") from exc
    return dates


class CanadaHolidaysCalendar(HolidayCalendar):
    """``HolidayCalendar`` on the Canada Holidays API; ``client_factory`` defaults to the configured vendor client."""

    def __init__(self, *, client_factory: Callable[[], httpx.AsyncClient] | None = None) -> None:
        self._client_factory = client_factory

    def _client(self) -> httpx.AsyncClient | None:
        if self._client_factory is not None:
            return self._client_factory()
        settings = get_canada_holidays_settings()
        return build_canada_holidays_client(settings) if settings.tenant is not None else None

    async def observed_federal_holidays(self, years: Collection[int]) -> OperationResult[frozenset[date]]:
        """Return every asked year's observed federal holidays, or a classified error."""
        asked = sorted(set(years))
        if not asked:
            return OperationResult.success(frozenset())
        client = self._client()
        if client is None:
            return OperationResult.permanent_error("[canada_holidays.tenant] is not configured", ErrorCode.CONFIG_NOT_CONFIGURED)
        holidays: set[date] = set()
        try:
            async with client:
                for year in asked:
                    response = await client.get("holidays", params={"federal": "true", "year": str(year)})
                    response.raise_for_status()
                    holidays |= _observed_dates(response.json())
        except _InvalidAnswer as exc:
            logger.warning("incident_holiday_lookup_failed", reason=str(exc))
            return OperationResult.permanent_error(f"Canada Holidays answered with {exc}", ErrorCode.INVALID_RESPONSE)
        except Exception as exc:  # noqa: BLE001 -- the vendor classifier re-raises what it does not know
            status, error_code, retry_after = classify_canada_holidays_error(exc)
            logger.warning("incident_holiday_lookup_failed", status=status.value, error_code=error_code, retry_after=retry_after)
            return OperationResult.error(status=status, message=str(exc), error_code=error_code, retry_after=retry_after)
        return OperationResult.success(frozenset(holidays))

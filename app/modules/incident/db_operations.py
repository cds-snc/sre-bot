from typing import TYPE_CHECKING, Any

from botocore.exceptions import ClientError
from structlog import get_logger

from contracts.operations import OperationResult, OperationStatus
from packages.aws_platform.adapters.dynamodb import build_dynamodb_adapter

if TYPE_CHECKING:
    from types_boto3_dynamodb.literals import SelectType

logger = get_logger()

INCIDENT_STORE_UNAVAILABLE_MESSAGE = (
    "The incidents database is temporarily unavailable. Please try again later.\n"
    "La base de données des incidents est temporairement indisponible. Veuillez réessayer plus tard."
)


class IncidentStoreUnavailableError(Exception):
    """Raised when the incidents table cannot be read or updated.

    Carries the adapter's classification so callers can log or message
    accordingly; the message stays generic and never includes provider error text.
    """

    def __init__(self, status: OperationStatus, error_code: str | None = None, retry_after: float | None = None) -> None:
        super().__init__("incidents store unavailable")
        self.status = status
        self.error_code = error_code
        self.retry_after = retry_after


def _unavailable(result: OperationResult[Any]) -> IncidentStoreUnavailableError:
    """Build the store-unavailable error from a non-success adapter result."""
    return IncidentStoreUnavailableError(result.status, error_code=result.error_code, retry_after=result.retry_after)


def _failure_fields(result: OperationResult[Any]) -> dict[str, Any]:
    """Return the structured log fields describing a non-success adapter result."""
    return {"status": result.status.value, "error_code": result.error_code, "error": result.message}


def _unclassified_fields(exc: ClientError) -> dict[str, Any]:
    """Return the structured log fields for a ClientError the adapter did not classify."""
    error = exc.response.get("Error", {})
    return {"status": "unclassified", "error_code": error.get("Code"), "error": error.get("Message")}


def list_incidents(select: SelectType = "ALL_ATTRIBUTES", **kwargs: Any) -> list[dict[str, Any]]:
    """List all incidents in the incidents table."""
    log = logger.bind(operation="list_incidents")
    log.info("listing_incidents", select=select, filters=kwargs)
    adapter = build_dynamodb_adapter()
    try:
        result = adapter.scan(TableName="incidents", Select=select, **kwargs)
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        log.error("incident_list_failed", **fields)
        raise IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
    if not result.is_success:
        log.error("incident_list_failed", **_failure_fields(result))
        raise _unavailable(result)
    return result.data or []

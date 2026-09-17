import datetime
from typing import Any

from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError
from structlog import get_logger
from types_boto3_dynamodb.literals import SelectType

from infrastructure.operations import OperationResult, OperationStatus
from models.incidents import Incident
from packages.aws_platform.adapters.dynamodb import build_dynamodb_adapter

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

    def __init__(self, status: OperationStatus, error_code: str | None = None, retry_after: int | None = None) -> None:
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


def create_incident(incident_data: dict[str, Any]) -> str | None:
    """Create an incident in the incidents table.

    Args:
        incident_data (dict): The incident data.

    Returns:
        str: The incident ID.
    """

    log = logger.bind(operation="create_incident")
    try:
        incident = Incident(**incident_data)
    except ValueError as e:
        log.error(
            "incident_creation_failed",
            error=str(e),
        )
        message = f"Invalid incident data: {e}"
        raise ValueError(message) from e

    existing_incident = get_incident_by_channel_id(incident.channel_id)
    if existing_incident:
        existing_id: str = existing_incident["id"]["S"]
        return existing_id

    serializer = TypeSerializer()
    serialized_data = {k: serializer.serialize(v) for k, v in incident.model_dump().items()}

    adapter = build_dynamodb_adapter()
    try:
        result = adapter.put_item(TableName="incidents", Item=serialized_data)
    except ClientError as exc:
        log.error("incident_creation_failed", **_unclassified_fields(exc))
        return None

    if not result.is_success:
        log.error("incident_creation_failed", **_failure_fields(result))
        return None

    message = f"User `{incident.user_id}` created incident `{incident.name}` in channel `{incident.channel_id}`"
    log_activity(incident.id, message)
    log = log.bind(
        channel_id=incident.channel_id,
        incident_id=incident.id,
        user_id=incident.user_id,
    )
    log.info("incident_creation_success")
    return incident.id


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


def update_incident_field(id: str, field: str, value: Any, user_id: str, type: str = "S") -> None:
    """Update an attribute in an incident item.

    Default type is string, but it can be changed to other types like N for numbers, SS for string sets, etc.

    Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.update_item
    """
    log = logger.bind(operation="update_incident_field", incident_id=id, field=field)
    protected_fields = ["id", "created_at", "channel_id", "logs"]
    if field in protected_fields:
        log.warning(
            "incident_update_protected_field",
            field=field,
            incident_id=id,
            user_id=user_id,
        )
        return None
    expression_attribute_names = {f"#{field}": field}
    attribute_value: dict[str, Any] = {type: value}
    expression_attribute_values: dict[str, Any] = {f":{field}": attribute_value}

    adapter = build_dynamodb_adapter()
    try:
        result = adapter.update_item(
            TableName="incidents",
            Key={"id": {"S": id}},
            UpdateExpression=f"SET #{field} = :{field}",
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )
    except ClientError as exc:
        log.error("incident_update_failed", **_unclassified_fields(exc))
        return None

    if not result.is_success:
        log.error("incident_update_failed", **_failure_fields(result))
        return None

    message = f"field `{field}` updated to `{value}` by user: {user_id}"
    log_activity(id, message)
    return None


def log_activity(incident_id: str, message: str) -> bool:
    """Log an activity in an incident."""
    log = logger.bind(operation="log_activity", incident_id=incident_id)
    adapter = build_dynamodb_adapter()
    try:
        result = adapter.update_item(
            retries=False,
            TableName="incidents",
            Key={"id": {"S": incident_id}},
            UpdateExpression="SET logs = list_append(if_not_exists(logs, :empty_list), :logs)",
            ExpressionAttributeValues={
                ":logs": {
                    "L": [
                        {
                            "M": {
                                "timestamp": {"S": str(datetime.datetime.now().timestamp())},
                                "message": {"S": message},
                            }
                        }
                    ]
                },
                ":empty_list": {"L": []},
            },
            ReturnValues="UPDATED_NEW",
        )
    except ClientError as exc:
        log.error("activity_log_failed", **_unclassified_fields(exc))
        return False

    if not result.is_success:
        log.error("activity_log_failed", **_failure_fields(result))
        return False

    log.info("activity_logged", message=message)
    return True


def get_incident_by_channel_id(channel_id: str) -> dict[str, Any] | None:
    """Get an incident by its channel ID.

    Args:
        channel_id (str): The channel ID.

    Returns:
        dict: The incident item. None if not found.
    """
    incidents = lookup_incident("channel_id", channel_id)
    if len(incidents) > 0:
        return incidents[0]
    return None


def lookup_incident(field: str, value: str) -> list[dict[str, Any]]:
    """Lookup incidents by a specific field value."""
    log = logger.bind(operation="lookup_incident")
    adapter = build_dynamodb_adapter()
    try:
        result = adapter.scan(
            TableName="incidents",
            FilterExpression=f"{field} = :{field}",
            ExpressionAttributeValues={f":{field}": {"S": value}},
        )
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        log.error("incident_lookup_failed", field=field, **fields)
        raise IncidentStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
    if not result.is_success:
        log.error("incident_lookup_failed", field=field, **_failure_fields(result))
        raise _unavailable(result)
    return result.data or []

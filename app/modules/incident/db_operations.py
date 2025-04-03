import datetime
from boto3.dynamodb.types import TypeSerializer

from models.incidents import Incident
from integrations.aws import dynamodb
from core.logging import get_module_logger

logger = get_module_logger()


def create_incident(incident_data: dict) -> str | None:
    """Create an incident in the incidents table.

    Args:
        incident_data (dict): The incident data.

    Returns:
        str: The incident ID.
    """

    try:
        incident = Incident(**incident_data)
    except ValueError as e:
        logger.error(
            "incident_creation_failed",
            error=str(e),
        )
        message = f"Invalid incident data: {e}"
        raise ValueError(message) from e

    existing_incident = get_incident_by_channel_id(incident.channel_id)
    if existing_incident:
        return existing_incident["id"]["S"]

    serializer = TypeSerializer()
    serialized_data = {
        k: serializer.serialize(v) for k, v in incident.model_dump().items()
    }

    response = dynamodb.put_item(
        TableName="incidents",
        Item=serialized_data,
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        message = f"User `{incident.user_id}` created incident `{incident.name}` in channel `{incident.channel_id}`"
        log_activity(incident.id, message)
        logger.info(
            "incident_creation_success",
            channel=incident.channel_id,
            incident_id=incident.id,
            user=incident.user_id,
        )
        return incident.id
    else:
        message = (
            f"Failed to create incident in database for channel `{incident.channel_id}`"
        )
        logger.error(
            "incident_creation_failed",
            channel=incident.channel_id,
        )

        return None


def list_incidents(select="ALL_ATTRIBUTES", **kwargs):
    """List all incidents in the incidents table."""
    return dynamodb.scan(TableName="incidents", Select=select, **kwargs)


def update_incident_field(id, field, value, user_id, type="S"):
    """Update an attribute in an incident item.

    Default type is string, but it can be changed to other types like N for numbers, SS for string sets, etc.

    Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.update_item
    """
    protected_fields = ["id", "created_at", "channel_id", "logs"]
    if field in protected_fields:
        logger.warning(
            "incident_update_protected_field",
            field=field,
            incident_id=id,
            user_id=user_id,
        )
        return None
    expression_attribute_names = {f"#{field}": field}
    expression_attribute_values = {f":{field}": {type: value}}

    response = dynamodb.update_item(
        TableName="incidents",
        Key={"id": {"S": id}},
        UpdateExpression=f"SET #{field} = :{field}",
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
    )
    if response:
        message = f"field `{field}` updated to `{value}` by user: {user_id}"
        log_activity(id, message)
        return response
    else:
        return None


def log_activity(incident_id, message):
    """Log an activity in an incident."""
    response = dynamodb.update_item(
        TableName="incidents",
        Key={"id": {"S": incident_id}},
        UpdateExpression="SET logs = list_append(if_not_exists(logs, :empty_list), :logs)",
        ExpressionAttributeValues={
            ":logs": {
                "L": [
                    {
                        "M": {
                            "timestamp": {
                                "S": str(datetime.datetime.now().timestamp())
                            },
                            "message": {"S": message},
                        }
                    }
                ]
            },
            ":empty_list": {"L": []},
        },
        ReturnValues="UPDATED_NEW",
    )

    if response:
        return True
    else:
        return False


def get_incident(id) -> dict:
    """Get an incident by its ID."""
    return dynamodb.get_item(TableName="incidents", Key={"id": {"S": id}})


def get_incident_by_channel_id(channel_id) -> dict | None:
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


def lookup_incident(field, value, field_type="S"):
    """Lookup incidents by a specific field value."""
    return dynamodb.scan(
        TableName="incidents",
        FilterExpression=f"{field} = :{field}",
        ExpressionAttributeValues={f":{field}": {f"{field_type}": value}},
    )

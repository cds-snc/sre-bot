import datetime
import uuid
import logging

from integrations.aws import dynamodb


def create_incident(
    channel_id,
    channel_name,
    name,
    user_id,
    teams,
    report_url,
    status="Open",
    meet_url=None,
    created_at=None,
    incident_commander=None,
    operations_lead=None,
    severity=None,
    start_impact_time=None,
    end_impact_time=None,
    detection_time=None,
    retrospective_url=None,
    environment="prod",
):
    incident_exists = lookup_incident("channel_id", channel_id)
    if len(incident_exists) > 0:
        return incident_exists[0]["id"]["S"]

    if not created_at:
        created_at = str(datetime.datetime.now().timestamp())
    id = str(uuid.uuid4())
    incident_data = {
        "id": {"S": id},
        "created_at": {"S": created_at},
        "channel_id": {"S": channel_id},
        "channel_name": {"S": channel_name},
        "name": {"S": name},
        "status": {"S": status},
        "user_id": {"S": user_id},
        "teams": {"SS": teams},
        "report_url": {"S": report_url},
        "meet_url": {"S": meet_url},
        "environment": {"S": environment},
        "logs": {"L": []},
        "incident_updates": {"L": []},
    }
    for key, value in [
        ("incident_commander", incident_commander),
        ("operations_lead", operations_lead),
        ("severity", severity),
        ("start_impact_time", start_impact_time),
        ("end_impact_time", end_impact_time),
        ("detection_time", detection_time),
        ("retrospective_url", retrospective_url),
    ]:
        if value:
            incident_data[key] = {"S": value}

    response = dynamodb.put_item(
        TableName="incidents",
        Item=incident_data,
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        message = f"User `{user_id}` created incident `{name}` in channel `{channel_id}`: {id}"
        log_activity(id, message)
        logging.info("Created incident %s", id)
        return id
    return None


def list_incidents(select="ALL_ATTRIBUTES", **kwargs):
    """List all incidents in the incidents table."""
    return dynamodb.scan(TableName="incidents", Select=select, **kwargs)


def update_incident_field(logger, id, field, value, user_id, type="S"):
    """Update an attribute in an incident item.

    Default type is string, but it can be changed to other types like N for numbers, SS for string sets, etc.

    Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.update_item
    """
    protected_fields = ["id", "created_at", "channel_id", "logs"]
    if field in protected_fields:
        logger.warn("Field `%s` is protected and cannot be updated", field)
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


def get_incident(id):
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

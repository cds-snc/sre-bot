from boto3.dynamodb.types import TypeDeserializer
from slack_sdk import WebClient

from modules.incident import db_operations, incident_conversation


def list_incidents(ack, logger, respond, client: WebClient, body):
    """List incidents"""
    deserializer = TypeDeserializer()
    channel_id = body.get("channel_id")
    if not channel_id:
        respond("Channel not found")
        return
    else:
        is_incident, is_dev_incident = incident_conversation.is_incident_channel(client, channel_id)
        message = f"Is this an incident channel? {is_incident}\nIs dev channel? {is_dev_incident}"
        respond(message)
    logger.info("listing_incidents_initialized")
    try:
        incidents = db_operations.list_incidents()
    except db_operations.IncidentStoreUnavailableError:
        respond(db_operations.INCIDENT_STORE_UNAVAILABLE_MESSAGE)
        return
    respond(f"Found {len(incidents)} incidents")
    if len(incidents) > 10:
        incidents = incidents[:10]
    logger.info("listing_incidents_response", payload=incidents)
    formatted_incidents = []
    for incident in incidents:
        incident = {k: deserializer.deserialize(v) for k, v in incident.items()}
        formatted_incidents.append(
            f"ID: {incident['id']}\nName: {incident['name']}\nStatus: {incident['status']}\nEnvironment: {incident['environment']}\nChannel: <#{incident['channel_id']}>\n"
        )
    message = "\n\n".join(formatted_incidents)
    respond(f"listing the 10 first incidents:\n\n{message}")
    logger.info("listing_incidents_completed", payload=formatted_incidents)

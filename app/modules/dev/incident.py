import json
import os

from slack_sdk import WebClient
from boto3.dynamodb.types import TypeDeserializer
from modules.incident import incident_folder, incident_conversation, db_operations

INCIDENT_LIST = os.getenv("INCIDENT_LIST")


def list_incidents(ack, logger, respond, client: WebClient, body):
    """List incidents"""
    logger.info(body)
    deserializer = TypeDeserializer()
    channel_id = body.get("channel_id")
    if not channel_id:
        respond("Channel not found")
        return
    else:
        is_incident, is_dev_incident = incident_conversation.is_incident_channel(
            client, logger, channel_id
        )
        message = f"Is this an incident channel? {is_incident}\nIs dev channel? {is_dev_incident}"
        respond(message)
    logger.info("Listing incidents...")
    incidents = db_operations.list_incidents()
    respond(f"Found {len(incidents)} incidents")
    if len(incidents) > 10:
        incidents = incidents[:10]
    logger.info(json.dumps(incidents, indent=2))
    formatted_incidents = []
    for incident in incidents:
        incident = {k: deserializer.deserialize(v) for k, v in incident.items()}
        formatted_incidents.append(
            f"ID: {incident['id']}\nName: {incident['name']}\nStatus: {incident['status']}\nEnvironment: {incident['environment']}\nChannel: <#{incident['channel_id']}>\n"
        )
    message = "\n\n".join(formatted_incidents)
    respond(f"listing the 10 first incidents:\n\n{message}")
    logger.info("finished processing request")


def load_incidents(ack, logger, respond, client: WebClient, body):
    """Load incidents from Google Sheet"""
    logger.info("Loading incidents...")
    incidents = incident_folder.get_incidents_from_sheet()[:30]
    logger.info(f"Loaded {len(incidents)} incidents")
    incidents = incident_folder.complete_incidents_details(client, logger, incidents)
    count = incident_folder.create_missing_incidents(logger, incidents)
    respond(f"Created {count} new incidents")
    logger.info(f"{len(incidents)} incidents")
    logger.info("Finished loading incidents")


def add_incident(ack, logger, respond, client: WebClient, body):
    """Add an incident to local DB from a channel"""
    is_incident, is_dev_incident = incident_conversation.is_incident_channel(
        client, logger, body["channel_id"]
    )
    if not (is_incident and is_dev_incident):
        respond("This is not an incident dev channel")
        return
    incident_id = db_operations.get_incident_by_channel_id(body["channel_id"])
    if incident_id:
        respond(f"This channel is already associated with incident:\n{incident_id}")
        return

    incident_info = client.conversations_info(channel=body["channel_id"])
    if not incident_info["ok"]:
        respond("Error getting channel info")
        return
    channel = incident_info["channel"]
    incident = {
        "channel_id": channel["id"],
        "channel_name": channel["name"],
        "name": channel["topic"]["value"],
        "user_id": body["user_id"],
        "teams": ["Development"],
        "created_at": channel["created"],
    }
    incident = incident_folder.get_incident_details(client, logger, incident)
    if not incident.get("report_url"):
        logger.info("Getting report url...")
        incident["report_url"] = incident_conversation.get_incident_document_id(
            client, incident["channel_id"], logger
        )
    incident_data = {
        "channel_id": incident["channel_id"],
        "channel_name": incident["channel_name"],
        "name": incident["name"],
        "user_id": incident["user_id"],
        "teams": incident["teams"],
        "report_url": incident["report_url"],
        "meet_url": incident["meet_url"],
        "created_at": incident["created_at"],
    }
    if incident_data["name"].startswith("Incident: "):
        incident_data["name"] = incident_data["name"][9:].strip()
        incident_data["name"] = incident_data["name"].rsplit("/", 1)[0].strip()

    logger.info(json.dumps(incident_data, indent=2))
    db_operations.create_incident(incident_data)

    logger.info(incident)

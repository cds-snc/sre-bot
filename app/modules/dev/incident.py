import json
import os

from slack_sdk import WebClient
from modules.incident import incident_folder

INCIDENT_LIST = os.getenv("INCIDENT_LIST")


def list_incidents(ack, logger, respond, client: WebClient, body):
    """List incidents"""
    logger.info("Listing incidents...")
    incidents = incident_folder.list_incidents()
    if len(incidents) > 10:
        incidents = incidents[:10]
    logger.info(json.dumps(incidents, indent=2))
    formatted_incidents = []
    for incident in incidents:
        formatted_incidents.append(
            f"ID: {incident['id']['S']}\nName: {incident['name']['S']}\nStatus: {incident['status']['S']}\nEnvironment: {incident['environment']['S']}\nChannel: <#{incident['channel_id']['S']}>\n"
        )
    message = "\n\n".join(formatted_incidents)
    respond(f"Found {len(incidents)} incidents:\n\n{message}")
    logger.info("finished processing request")


def load_incidents(ack, logger, respond, client: WebClient, body):
    """Load incidents from Google Sheet"""
    logger.info("Loading incidents...")
    incidents = incident_folder.get_incidents_from_sheet()
    incidents = incident_folder.complete_incidents_details(client, logger, incidents)
    count = incident_folder.create_missing_incidents(logger, incidents)
    respond(f"Loaded {count} incidents")
    logger.info(f"{len(incidents)} incidents")
    logger.info("finished loading incidents")

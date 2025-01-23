"""Testing AWS service (will be removed)"""

from datetime import datetime
import json
import logging
from dotenv import load_dotenv

from modules.incident import incident_folder

load_dotenv()

logger = logging.getLogger(__name__)


def add_incident(body, respond):
    incidents = incident_folder.list_incidents()
    num = len(incidents)
    channel_id = "C0000000" + str(num)
    channel_name = "channel_name" + str(num)
    user_id = body["user_id"]
    teams = ["team1", "team2"]
    report_url = "report_url" + str(num)
    meet_url = "meet_url" + str(num)

    try:
        logger.info("Adding incident")
        incident = incident_folder.create_incident(
            channel_id=channel_id,
            channel_name=channel_name,
            user_id=user_id,
            teams=teams,
            report_url=report_url,
            meet_url=meet_url,
            environment="dev",
        )
        respond(f"Incident added: {incident}")
    except Exception as e:
        logger.error(f"Error adding incident: {e}")
        respond(f"Error adding incident: {e}")


def print_incident(incident):
    return f"""
    Incident ID: {incident["id"]["S"]}
    Channel ID: {incident["channel_id"]["S"]}
    Channel Name: {incident["channel_name"]["S"]}
    User ID: {incident["user_id"]["S"]}
    Teams: {incident.get("team", incident.get("teams")).get("SS", "Unknown")}
    Report URL: {incident["report_url"]["S"]}
    Meet URL: {incident["meet_url"]["S"]}
    Status: {incident["status"]["S"]}
    Start Impact Time: {incident.get("start_impact_time", {}).get("S", "Unknown")}
    End Impact Time: {incident.get("end_impact_time", {}).get("S", "Unknown")}
    Environment: {incident.get("environment", {}).get("S", "Unknown")}
    Retro: {incident.get("retrospective_url", {}).get("S", "Unknown")}
    """


def switch_status(id):
    logger.info(f"Switching status for incident {id}")
    incident = incident_folder.get_incident(id)
    logger.info(f"Incident: {incident}")
    if incident:
        if incident["status"]["S"] == "Open":
            incident_folder.update_incident_field(id, "status", "Closed")
        else:
            incident_folder.update_incident_field(id, "status", "Open")
        return True
    return False


def update_start_impact_time(id):
    logger.info(f"Updating start impact time for incident {id}")
    incident = incident_folder.get_incident(id)
    logger.info(
        f"Incident: {incident}\nStart Impact Time: {incident.get('start_impact_time', {}).get('S', 'Unknown')}"
    )
    if incident:
        incident_folder.update_incident_field(
            id, "start_impact_time", str(datetime.now())
        )
        return True
    return False


def aws_dev_command(ack, client, body, respond, logger):
    ack()

    # add_incident(body, respond)

    incidents = incident_folder.list_incidents()
    logger.info(json.dumps(incidents, indent=2))

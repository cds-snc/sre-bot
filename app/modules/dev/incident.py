import requests
from slack_sdk import WebClient
from boto3.dynamodb.types import TypeDeserializer
from modules.incident import incident_folder, incident_conversation, db_operations
from api.v1.routes.webhooks import append_incident_buttons
from models.webhooks import WebhookPayload

from core.config import settings

INCIDENT_LIST = settings.google_workspace.INCIDENT_LIST
SLACK_DEV_MSG_CHANNEL = settings.dev.SLACK_DEV_MSG_CHANNEL


def list_incidents(ack, logger, respond, client: WebClient, body):
    """List incidents"""
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
    logger.info("listing_incidents_initialized")
    incidents = db_operations.list_incidents()
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


def load_incidents(ack, logger, respond, client: WebClient, body):
    """Load incidents from Google Sheet"""
    logger.info("load_incidents_received", body=body)
    incidents = incident_folder.get_incidents_from_sheet()[:30]
    logger.info(
        "get_incidents_from_sheet_completed", payload=incidents, count=len(incidents)
    )
    incidents = incident_folder.complete_incidents_details(client, incidents)
    logger.info(
        "complete_incidents_details_completed", payload=incidents, count=len(incidents)
    )
    count = incident_folder.create_missing_incidents(incidents)
    respond(f"Created {count} new incidents")
    logger.info("create_missing_incidents_completed", count=count)
    logger.info("load_incidents_completed")


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
    incident = incident_folder.get_incident_details(client, incident)
    if not incident.get("report_url"):
        logger.info("getting_report_url")
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

    logger.info("incident_data_created", payload=incident_data)
    db_operations.create_incident(incident_data)


def emit_test_incident_alert(ack, logger, respond, client: WebClient, body):
    """Emit a test incident alert by sending a payload to the Slack Test Channel Webhook."""
    webhook_url = SLACK_DEV_MSG_CHANNEL
    payload = WebhookPayload(text="This is a test incident alert", attachments=None)
    payload = append_incident_buttons(payload, "test-incident-id")

    response = requests.post(
        webhook_url, json=payload.model_dump(exclude_none=True), timeout=10
    )
    print(response.status_code)
    print(response.text)


def post_dev_test_message(ack, logger, respond, client: WebClient, body):
    """Post a test message as the bot and log channel/ts for update testing."""
    ack()
    channel_id = body.get("channel_id") or body.get("channel", {}).get("id")
    if not channel_id:
        respond("No channel_id found in body.")
        return
    result = client.chat_postMessage(
        channel=channel_id,
        text=":robot_face: Dev test message for update testing.",
        attachments=[{"color": "#439FE0", "text": "This is a test attachment."}],
    )
    ts = result["ts"]
    logger.info("dev_test_message_posted", channel=channel_id, ts=ts)
    respond(
        f"Test message posted. Channel: `{channel_id}` TS: `{ts}` `{channel_id},{ts}`"
    )


def update_dev_test_message(ack, logger, respond, client: WebClient, body, args: list):
    """Update a message given channel and ts (provide as body['text'] = 'channel_id,ts')."""
    ack()
    channel_id = None
    ts = None
    # Expecting body['text'] = 'channel_id,ts'
    try:
        channel_id, ts = [x.strip() for x in args[0].split(",")]
    except Exception:
        respond("Please provide input as 'channel_id,ts'")
        return
    logger.info("update_dev_test_invoked", channel_id=channel_id, ts=ts)
    try:
        result = client.chat_update(
            channel=channel_id,
            ts=ts,
            text=":robot_face: Updated by dev command!",
            attachments=[
                {"color": "good", "text": "This message was updated successfully!"}
            ],
        )
        logger.info(
            "dev_test_message_updated", channel=channel_id, ts=ts, result=result
        )
        respond(f"Message updated! Channel: `{channel_id}` TS: `{ts}`")
    except Exception as e:
        logger.error(
            "dev_test_message_update_failed", channel=channel_id, ts=ts, error=str(e)
        )
        respond(f"Failed to update message: {e}")

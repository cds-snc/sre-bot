import json
from boto3.dynamodb.types import TypeDeserializer
from slack_bolt import Respond
from slack_sdk import WebClient
from models.incidents import Incident
from modules.incident import db_operations


def open_incident_info_view(client: WebClient, body, respond: Respond):
    """Open the incident information view. This view displays the incident details where certain fields can be updated."""
    incident = db_operations.get_incident_by_channel_id(body["channel_id"])
    if not incident:
        respond(
            "This command is only available in incident channels. No incident records found for this channel."
        )
        return
    else:
        deserialize = TypeDeserializer()
        incident_data = {k: deserialize.deserialize(v) for k, v in incident.items()}
        view = incident_information_view(Incident(**incident_data))
        client.views_open(trigger_id=body["trigger_id"], view=view)


def incident_information_view(incident: Incident):
    """Create the view for the incident information modal.
    It should receive a valid Incident object"""
    created_at = (
        f"<!date^{int(float(incident.created_at))}^{{date}} at {{time}}|Unknown>"
    )
    impact_start_timestamp = "Unknown"
    impact_end_timestamp = "Unknown"
    detection_timestamp = "Unknown"
    if incident.detection_time != "Unknown":
        detection_timestamp = f"<!date^{int(float(incident.detection_time))}^{{date}} at {{time}}|Unknown>"
    if incident.start_impact_time != "Unknown":
        impact_start_timestamp = f"<!date^{int(float(incident.start_impact_time))}^{{date}} at {{time}}|Unknown>"
    if incident.end_impact_time != "Unknown":
        impact_end_timestamp = f"<!date^{int(float(incident.end_impact_time))}^{{date}} at {{time}}|Unknown>"

    report_string = f"<https://docs.google.com/document/d/{incident.report_url}|:memo: Incident Report>"
    meet_string = f"<{incident.meet_url}|:headphones: Google Meet>"
    incident_data = incident.model_dump()
    incident_data.pop("logs")
    private_metadata = json.dumps(incident_data)

    return {
        "type": "modal",
        "callback_id": "incident_information_view",
        "title": {"type": "plain_text", "text": "Incident Information", "emoji": True},
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "private_metadata": private_metadata,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": incident.name,
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*ID*: " + incident.id,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": report_string,
                    },
                    {
                        "type": "mrkdwn",
                        "text": meet_string,
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Status*:\n" + incident.status,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "status",
                    "action_id": "update_incident_field",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Creation Time*:\n" + created_at,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Detection Time*:\n" + detection_timestamp,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "detection_time",
                    "action_id": "update_incident_field",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Start of Impact*:\n" + impact_start_timestamp,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "start_impact_time",
                    "action_id": "update_incident_field",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*End of Impact*:\n" + impact_end_timestamp,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "end_impact_time",
                    "action_id": "update_incident_field",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "*Retro Link*:\n" + incident.retrospective_url
                        if incident.retrospective_url
                        else "*Retro Link*:\n" + "Unknown"
                    ),
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "retrospective_url",
                    "action_id": "update_incident_field",
                },
            },
        ],
    }

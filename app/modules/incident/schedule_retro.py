from datetime import datetime, timedelta

import json

from slack_sdk import WebClient
from integrations.slack import channels as slack_channels
from integrations.google_workspace.google_calendar import (
    get_freebusy,
    insert_event,
    find_first_available_slot,
    identify_unavailable_users,
)
from modules.incident import incident_conversation
from core.logging import get_module_logger
from core.config import settings

CALENDAR_ID = settings.google_resources.sre_calendar_id

logger = get_module_logger()


def schedule_event(client: WebClient, days, users, days_lookup=60):
    """Schedules the event based on the users provided and the number of days to look ahead.
    Returns the first available slot, or None if no slot is found.
    Also returns a list of unavailable users where no slot was found for the entire period to help identify possible issues.
    """
    # Define the time range for the query
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # time_min is the current time + days and time_max is the current time + 60 days + days
    time_min = (now + timedelta(days=days)).isoformat() + "Z"
    time_max = (now + timedelta(days=(days_lookup + days))).isoformat() + "Z"

    user_emails = []
    items = []
    for user in users:
        user_id = user["value"].strip()
        user_email = client.users_info(user=user_id)["user"]["profile"]["email"]
        user_emails.append(user_email)
        user["email"] = user_email
        user_emails.append(user_email)
        items.append({"id": user_email})

    # Execute the query to find all the busy times for all the participants
    freebusy_result = get_freebusy(time_min, time_max, items)
    unavailable_users_emails = identify_unavailable_users(
        freebusy_result, time_min, time_max
    )
    if set(unavailable_users_emails) == set(user_emails):
        logger.warning(
            "schedule_event_could_not_schedule",
            message="All users are unavailable for the selected time range.",
        )
    # # return the first available slot to book the event
    first_available_start, first_available_end = find_first_available_slot(
        freebusy_result, days
    )
    return {
        "first_available_start": first_available_start,
        "first_available_end": first_available_end,
        "unavailable_users": unavailable_users_emails,
    }


# Function to be triggered when the /sre incident schedule command is called. This function brings up a modal window
# that explains how the event is scheduled and allows the user to schedule a retro meeting for the incident after the
# submit button is clicked.
def open_incident_retro_modal(client: WebClient, body, ack):
    """Open the modal for scheduling a retro meeting."""
    ack()
    channel_id = body["channel_id"]
    channel_name = body["channel_name"]

    is_incident, _is_dev_incident = incident_conversation.is_incident_channel(
        client, channel_id
    )
    if not is_incident:
        return

    # get the incident document
    # get and update the incident document
    document_id = incident_conversation.get_incident_document_id(client, channel_id)

    # convert the data to string so that we can send it as private metadata
    private_metadata = json.dumps(
        {
            "name": channel_name,
            "incident_document": document_id,
            "channel_id": channel_id,
        }
    )

    # Fetch user details from all members of the channel
    users = slack_channels.fetch_user_details(client, channel_id)
    # Generate the modal view
    view = generate_retro_options_view(private_metadata, users)
    # Open the modal window
    client.views_open(
        trigger_id=body["trigger_id"],
        view=view,
    )


def generate_retro_options_view(
    private_metadata, all_users, unavailable_users: list | None = None
):
    """Create the modal for the schedule retro options. Adds a warning message if there are unavailable users."""
    blocks = [
        {
            "type": "input",
            "block_id": "number_of_days",
            "element": {
                "type": "number_input",
                "is_decimal_allowed": False,
                "min_value": "1",
                "max_value": "60",
                "action_id": "number_of_days",
            },
            "label": {
                "type": "plain_text",
                "text": "How many days from now should I start checking the calendar for availability?",
            },
        },
        {
            "type": "section",
            "block_id": "user_select_block",
            "text": {
                "type": "mrkdwn",
                "text": "Select everyone you want to include in the retro calendar invite",
            },
            "accessory": {
                "type": "multi_static_select",
                "action_id": "user_select_action",
                "options": all_users,
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*By clicking this button an event will be scheduled.* The following rules will be followed:",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "1. The event will be scheduled for the first available 30 minutes timeslot starting the after the number of days selected above between 1:00pm and 3:00pm EDT to accomodate all time differences.",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "2. A proposed event will be added to everyone's calendar that is selected, unless free time isn't found within the next 2 months.",
            },
        },
    ]

    # Add unavailable users section if there are any
    if unavailable_users and len(unavailable_users) > 0:
        unavailable_users_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_⚠️ The following users may have calendar availability issues that will prevent the successful scheduling of the event:_\n{', '.join(unavailable_users)}",
            },
        }
        # top_blocks.append(unavailable_users_block)
        blocks.append(unavailable_users_block)

    view = {
        "type": "modal",
        "callback_id": "view_save_event",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "SRE - Schedule Retro 🗓️"},
        "submit": {"type": "plain_text", "text": "Schedule"},
        "blocks": blocks,
    }
    # Return the completed modal
    return view


def generate_retro_saving_view(status=0, link=""):
    """Create the modal for the saving retro event. Shows a loading message or success message with link.
    Status 0: Loading message
    Status 1: Success message with link
    Status 2: Error message

    :param status: int: Status of the view to generate
    :param link: str: Link to the calendar event
    :return: dict: View for the modal
    """
    if status == 0:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": ":beach-ball: *Scheduling the retro...*",
                },
            }
        ]
    elif status == 1:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Successfully scheduled calender event!*",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Calendar Event",
                    },
                    "value": "view_event",
                    "url": link,
                    "action_id": "confirm_click",
                },
            },
        ]
    else:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Could not schedule event - no free time was found!*",
                },
            }
        ]

    view = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "SRE - Schedule Retro 🗓️"},
        "blocks": blocks,
    }
    return view


# Function to create the calendar event and bring up a modal that contains a link to the event. If the event could not be scheduled,
# a message is displayed to the user that the event could not be scheduled.
def handle_schedule_retro_submit(client: WebClient, ack, body, view):
    """Handle the submission of the retro event modal."""
    ack()
    saving_view = generate_retro_saving_view()
    loading_view = client.views_open(trigger_id=body["trigger_id"], view=saving_view)[
        "view"
    ]

    private_metadata = json.loads(view["private_metadata"])
    incident_name = private_metadata.get("name")
    incident_document = private_metadata.get("incident_document")
    # get the number of days data from the view and convert to an integer
    days = int(view["state"]["values"]["number_of_days"]["number_of_days"]["value"])

    # get all the users selected in the multi select block
    users = view["state"]["values"]["user_select_block"]["user_select_action"][
        "selected_options"
    ]

    # pass the data using the view["private_metadata"] to the schedule_event function
    scheduled_event_details = schedule_event(client, days, users)
    first_available_start = scheduled_event_details["first_available_start"]
    first_available_end = scheduled_event_details["first_available_end"]
    if first_available_start is None:
        saving_view = generate_retro_saving_view(status=2)
        logger.error(
            "retro_scheduling_failed",
            message="Failed to schedule retro event - no available time slots found",
            incident_name=incident_name,
            days_offset=days,
            unavailable_users=scheduled_event_details["unavailable_users"],
        )
        client.views_update(
            view_id=loading_view["id"], hash=loading_view["hash"], view=saving_view
        )
        return
    user_emails = get_users_emails_from_selected_options(client, users)
    result = save_retro_event(
        first_available_start,
        first_available_end,
        user_emails,
        incident_name,
        incident_document,
    )
    # if we could not schedule the event, display a message to the user that the event could not be scheduled
    if result is None:
        saving_view = generate_retro_saving_view(status=2)
        logger.error(
            "retro_scheduling_failed",
            message="The save_retro_event did not return a link",
            incident_name=incident_name,
            days_offset=days,
            unavailable_users=scheduled_event_details["unavailable_users"],
        )

    # if the event was scheduled successfully, display a message to the user that the event was scheduled and provide a link to the event
    else:
        channel_id = json.loads(view["private_metadata"])["channel_id"]
        event_link = result["event_link"]
        event_info = result["event_info"]
        saving_view = generate_retro_saving_view(status=1, link=event_link)
        logger.info(
            "retro_scheduling_success",
            message="Successfully scheduled retro event",
            incident_name=incident_name,
            days_offset=days,
            unavailable_users=scheduled_event_details["unavailable_users"],
            event_link=event_link,
            event_info=event_info,
        )

        # post the message in the channel
        client.chat_postMessage(channel=channel_id, text=event_info, unfurl_links=False)

    # Open the modal and log that the event was scheduled successfully
    client.views_update(
        view_id=loading_view["id"], hash=loading_view["hash"], view=saving_view
    )


def save_retro_event(
    first_available_start,
    first_available_end,
    user_emails,
    incident_name,
    incident_document,
) -> dict:
    """Save the retro event to the calendar and return the event link."""
    event_config = {
        "description": "This is a retro meeting to discuss incident: " + incident_name,
        "conferenceData": {
            "createRequest": {
                "requestId": f"{first_available_start.timestamp()}",  # Unique ID per event to avoid collisions
                "conferenceSolutionKey": {
                    "type": "hangoutsMeet"  # This automatically generates a Google Meet link
                },
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 10},
            ],
        },
    }
    return insert_event(
        first_available_start.isoformat(),
        first_available_end.isoformat(),
        user_emails,
        "Retro " + incident_name,
        calendar_id=CALENDAR_ID,
        incident_document=incident_document,
        **event_config,
    )


# We just need to handle the action here and record who clicked on it
def confirm_click(ack, body, client):
    ack()
    username = body["user"]["username"]
    logger.info(
        "user_viewed_calendar_event",
        username=username,
    )


def get_users_emails_from_selected_options(client: WebClient, selected_options):
    user_emails = []
    for user in selected_options:
        user_id = user["value"].strip()
        user_email = client.users_info(user=user_id)["user"]["profile"]["email"]
        user_emails.append(user_email)
    return user_emails


def incident_selected_users_updated(client: WebClient, body, ack):
    ack()
    view_id = body["view"]["id"]
    all_users = body["view"]["blocks"][1]["accessory"]["options"]
    private_metadata = body["view"]["private_metadata"]
    selected_options = body["actions"][0]["selected_options"]
    if len(selected_options) == 0:
        view = generate_retro_options_view(private_metadata, all_users)
    else:
        scheduled_event_data = schedule_event(client, 1, selected_options)
        unavailable_users_emails = scheduled_event_data["unavailable_users"]

        unavailable_users = []
        for user in unavailable_users_emails:
            user_data = client.users_lookupByEmail(email=user)
            details: dict = user_data.get("user", {})
            if details:
                user_id = details.get("id")
                formatted_user = f"<@{user_id}>"
                unavailable_users.append(formatted_user)
        view = generate_retro_options_view(
            private_metadata, all_users, unavailable_users
        )
    client.views_update(view_id=view_id, view=view)

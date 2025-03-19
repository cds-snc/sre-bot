import logging
from datetime import datetime, timedelta

import json

from slack_sdk import WebClient
from integrations.slack import channels as slack_channels
from integrations.google_workspace.google_calendar import (
    get_freebusy,
    insert_event,
    find_first_available_slot,
)
from integrations.google_workspace import google_docs


# Schedule a calendar event by finding the first available slot in the next 60 days that all participants are free in and book the event
def schedule_event(event_details, days, user_emails):
    # Define the time range for the query
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # time_min is the current time + days and time_max is the current time + 60 days + days
    time_min = (now + timedelta(days=days)).isoformat() + "Z"
    time_max = (now + timedelta(days=(60 + days))).isoformat() + "Z"

    # Construct the items array
    items = []
    for email in user_emails:
        email = email.strip()
        items.append({"id": email})
    incident_name = json.loads(event_details).get("name")

    # get the incident document link
    incident_document = json.loads(event_details).get("incident_document")

    # Execute the query to find all the busy times for all the participants
    freebusy_result = get_freebusy(time_min, time_max, items)

    # return the first available slot to book the event
    first_available_start, first_available_end = find_first_available_slot(
        freebusy_result, days
    )

    # If there are no available slots, return None
    if first_available_start is None and first_available_end is None:
        logging.info("No available slots found")
        return None

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

    result = insert_event(
        first_available_start.isoformat(),
        first_available_end.isoformat(),
        user_emails,
        "Retro " + incident_name,
        incident_document,
        **event_config,
    )
    return result  # Return the HTML link and event info


# Function to be triggered when the /sre incident schedule command is called. This function brings up a modal window
# that explains how the event is scheduled and allows the user to schedule a retro meeting for the incident after the
# submit button is clicked.
def open_incident_retro_modal(client: WebClient, body, ack):
    ack()
    channel_id = body["channel_id"]
    channel_name = body["channel_name"]
    user_id = body["user_id"]

    # if we are not in an incident channel, then we need to display a message to the user that they need to use this command in an incident channel
    if not channel_name.startswith("incident-"):
        try:
            response = client.chat_postEphemeral(
                text=f"Channel {channel_name} is not an incident channel. Please use this command in an incident channel.",
                channel=channel_id,
                user=user_id,
            )
        except Exception as e:
            logging.error(
                f"Could not post ephemeral message to user {user_id} due to {e}."
            )
        return

    # get all users in a channel
    users = client.conversations_members(channel=channel_id)["members"]

    # get the incident document
    # get and update the incident document
    document_id = ""
    response = client.bookmarks_list(channel_id=channel_id)
    if response["ok"]:
        for item in range(len(response["bookmarks"])):
            if response["bookmarks"][item]["title"] == "Incident report":
                document_id = google_docs.extract_google_doc_id(
                    response["bookmarks"][item]["link"]
                )
    else:
        logging.warning(
            "No bookmark link for the incident document found for channel %s",
            channel_name,
        )

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
    view = generate_retro_options_modal_view(private_metadata, users)
    # Open the modal window
    client.views_open(
        trigger_id=body["trigger_id"],
        view=view,
    )


def generate_retro_options_modal_view(
    private_metadata, all_users, unavailable_users: list | None = None
):
    """Create the modal for the schedule retro options."""
    # First part of blocks (before divider)
    top_blocks = [
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
    ]

    # Add unavailable users section above divider if there are any
    if unavailable_users and len(unavailable_users) > 0:
        unavailable_users_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"_⚠️ The following users may have calendar availability issues:_ {', '.join(unavailable_users)}",
            },
        }
        top_blocks.append(unavailable_users_block)

    # Divider and bottom part of blocks
    divider_and_rules_blocks = [
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
                "text": "1. The event will be scheduled for the first available 30 minute timeslot starting the number of days selected above.",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "2. A proposed event will be added to everyone's calendar that is selected.",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "3. The retro will be scheduled only between 1:00pm and 3:00pm EDT to accomodate all time differences.",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "4. If no free time exists for the next 2 months, the event will not be scheduled.",
            },
        },
    ]

    # Combine all blocks
    all_blocks = top_blocks + divider_and_rules_blocks
    view = {
        "type": "modal",
        "callback_id": "view_save_event",
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "SRE - Schedule Retro 🗓️"},
        "submit": {"type": "plain_text", "text": "Schedule"},
        "submit_disabled": False,
        "blocks": all_blocks,
    }
    # Return the completed modal
    return view


# Function to create the calendar event and bring up a modal that contains a link to the event. If the event could not be scheduled,
# a message is displayed to the user that the event could not be scheduled.
def save_incident_retro(client: WebClient, ack, body, view):
    ack()
    blocks = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "SRE - Schedule Retro 🗓️"},
        "blocks": (
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": ":beach-ball: *Scheduling the retro...*",
                    },
                }
            ]
        ),
    }
    loading_view = client.views_open(trigger_id=body["trigger_id"], view=blocks)["view"]

    # get the number of days data from the view and convert to an integer
    days = int(view["state"]["values"]["number_of_days"]["number_of_days"]["value"])

    # get all the users selected in the multi select block
    users = view["state"]["values"]["user_select_block"]["user_select_action"][
        "selected_options"
    ]
    user_emails = []
    for user in users:
        user_id = user["value"].strip()
        user_email = client.users_info(user=user_id)["user"]["profile"]["email"]
        user_emails.append(user_email)

    # pass the data using the view["private_metadata"] to the schedule_event function
    result = schedule_event(view["private_metadata"], days, user_emails)
    # if we could not schedule the event, display a message to the user that the event could not be scheduled
    if result is None:
        blocks = {
            "type": "modal",
            "title": {"type": "plain_text", "text": "SRE - Schedule Retro 🗓️"},
            "blocks": (
                [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Could not schedule event - no free time was found!*",
                        },
                    }
                ]
            ),
        }
        logging.info(
            "The event could not be scheduled since schedule_event returned None"
        )

    # if the event was scheduled successfully, display a message to the user that the event was scheduled and provide a link to the event
    else:
        channel_id = json.loads(view["private_metadata"])["channel_id"]
        event_link = result["event_link"]
        event_info = result["event_info"]
        blocks = {
            "type": "modal",
            "title": {"type": "plain_text", "text": "SRE - Schedule Retro 🗓️"},
            "blocks": (
                [
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
                            "url": f"{event_link}",
                            "action_id": "confirm_click",
                        },
                    },
                ]
            ),
        }
        logging.info("Event has been scheduled successfully. Link: %s", event_link)

        # post the message in the channel
        client.chat_postMessage(channel=channel_id, text=event_info, unfurl_links=False)

    # Open the modal and log that the event was scheduled successfully
    client.views_update(
        view_id=loading_view["id"], hash=loading_view["hash"], view=blocks
    )


# We just need to handle the action here and record who clicked on it
def confirm_click(ack, body, client):
    ack()
    username = body["user"]["username"]
    logging.info(f"User {username} viewed the calendar event.")

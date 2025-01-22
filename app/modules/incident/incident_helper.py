import json
import logging
import os
from slack_sdk import WebClient
from slack_bolt import Ack, Respond, App
from integrations.google_workspace import google_docs, google_drive
from integrations.slack import channels as slack_channels
from integrations.sentinel import log_to_sentinel
from . import (
    incident_folder,
    incident_roles,
    schedule_retro,
)
from modules.incident import incident_status

INCIDENT_CHANNELS_PATTERN = r"^incident-\d{4}-"
SRE_DRIVE_ID = os.environ.get("SRE_DRIVE_ID")
SRE_INCIDENT_FOLDER = os.environ.get("SRE_INCIDENT_FOLDER")
START_HEADING = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"


help_text = """
\n `/sre incident create-folder <folder_name>`
\n      - create a folder for a team in the incident drive
\n      - créer un dossier pour une équipe dans le dossier d'incidents
\n `/sre incident help`
\n      - show this help text
\n      - afficher ce texte d'aide
\n `/sre incident list-folders`
\n      - list all folders in the incident drive
\n      - lister tous les dossiers dans le dossier d'incidents
\n `/sre incident roles`
\n      - manages roles in an incident channel
\n      - gérer les rôles dans un canal d'incident
\n  `/sre incident schedule`
\n      - schedules a 30 minute meeting a week into the future in everyone's calendars for the incident post mortem process.
\n      - planifie une réunion de 30 minutes une semaine dans le futur dans les calendriers de tout le monde pour le processus de post-mortem de l'incident.
\n `/sre incident close`
\n      - close the incident, archive the channel and update the incident spreadsheet and document
\n      - clôturer l'incident, archiver le canal et mettre à jour la feuille de calcul et le document de l'incident
\n `/sre incident stale`
\n      - lists all incidents older than 14 days with no activity
\n      - lister tous les incidents plus vieux que 14 jours sans activité
\n `/sre incident status <status>`
\n      - update the status of the incident with the provided status. Supported statuses are: Open, In Progress, Ready to be Reviewed, Reviewed, Closed
\n      - mettre à jour le statut de l'incident avec le statut fourni. Les statuts pris en charge sont : Open, In Progress, Ready to be Reviewed, Reviewed, Closed
"""


def register(bot: App):
    bot.action("add_folder_metadata")(incident_folder.add_folder_metadata)
    bot.action("view_folder_metadata")(incident_folder.view_folder_metadata)
    bot.view("view_folder_metadata_modal")(incident_folder.list_folders_view)
    bot.view("add_metadata_view")(incident_folder.save_metadata)
    bot.action("delete_folder_metadata")(incident_folder.delete_folder_metadata)
    bot.action("archive_channel")(archive_channel_action)
    bot.view("view_save_incident_roles")(incident_roles.save_incident_roles)
    bot.view("view_save_event")(save_incident_retro)
    bot.action("confirm_click")(confirm_click)


def handle_incident_command(args, client: WebClient, body, respond: Respond, ack: Ack):
    if len(args) == 0:
        respond(help_text)
        return

    action, *args = args
    match action:
        case "create-folder":
            name = " ".join(args)
            folder = google_drive.create_folder(name, SRE_INCIDENT_FOLDER)
            if folder:
                respond(f"Folder `{folder['name']}` created.")
            else:
                respond(f"Failed to create folder `{name}`.")
        case "help":
            respond(help_text)
        case "list-folders":
            incident_folder.list_folders_view(client, body, ack)
        case "roles":
            incident_roles.manage_roles(client, body, ack, respond)
        case "close":
            close_incident(client, body, ack, respond)
        case "stale":
            stale_incidents(client, body, ack)
        case "schedule":
            schedule_incident_retro(client, body, ack)
        case "status":
            handle_update_status_command(client, body, respond, ack, args)
        case _:
            respond(
                f"Unknown command: {action}. Type `/sre incident help` to see a list of commands."
            )


def archive_channel_action(client: WebClient, body, ack, respond):
    ack()
    channel_id = body["channel"]["id"]
    action = body["actions"][0]["value"]
    channel_name = body["channel"]["name"]
    user = body["user"]["id"]

    # get the current chanel id and name and make up the body with those 2 values
    channel_info = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "user_id": user,
    }

    if action == "ignore":
        msg = (
            f"<@{user}> has delayed scheduling and archiving this channel for 14 days."
        )
        client.chat_update(
            channel=channel_id, text=msg, ts=body["message_ts"], attachments=[]
        )
        log_to_sentinel("incident_channel_archive_delayed", body)
    elif action == "archive":
        # Call the close_incident function to update the incident document to closed, update the spreadsheet and archive the channel
        close_incident(client, channel_info, ack, respond)
        # log the event to sentinel
        log_to_sentinel("incident_channel_archived", body)
    elif action == "schedule_retro":
        channel_info["trigger_id"] = body["trigger_id"]
        schedule_incident_retro(client, channel_info, ack)
        # log the event to sentinel
        log_to_sentinel("incident_retro_scheduled", body)


def close_incident(client: WebClient, body, ack, respond):
    ack()
    # get the current chanel id and name
    channel_id = body["channel_id"]
    channel_name = body["channel_name"]
    user_id = body["user_id"]

    # ensure the bot is actually in the channel before performing actions
    try:
        response = client.conversations_info(channel=channel_id)
        channel_info = response.get("channel", None)
        if channel_info is None or not channel_info.get("is_member", False):
            client.conversations_join(channel=channel_id)
    except Exception as e:
        logging.error(f"Failed to join the channel {channel_id}: {e}")
        return

    if not channel_name.startswith("incident-"):
        try:
            client.chat_postEphemeral(
                text=f"Channel {channel_name} is not an incident channel. Please use this command in an incident channel.",
                channel=channel_id,
                user=user_id,
            )
        except Exception as e:
            logging.error(
                f"Could not post ephemeral message to user {user_id} due to {e}.",
            )
        return

    incident_status.update_status(
        client, ack, respond, "Closed", channel_id, channel_name, user_id
    )

    # Need to post the message before the channel is archived so that the message can be delivered.
    try:
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> has archived this channel 👋",
        )
    except Exception as e:
        logging.error(
            f"Could not post message to channel {channel_name} due to error: {e}.",
        )

    # archive the channel
    try:
        client.conversations_archive(channel=channel_id)
        logging.info(
            "Channel %s has been archived by %s", channel_name, f"<@{user_id}>"
        )
        log_to_sentinel("incident_channel_archived", body)
    except Exception as e:
        error_message = (
            f"Could not archive the channel {channel_name} due to error: {e}"
        )
        logging.error(
            "Could not archive the channel %s due to error: %s", channel_name, e
        )
        respond(error_message)


def stale_incidents(client: WebClient, body, ack: Ack):
    ack()

    placeholder = {
        "type": "modal",
        "callback_id": "stale_incidents_view",
        "title": {"type": "plain_text", "text": "SRE - Stale incidents"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Loading stale incident list ...(this may take a minute)",
                },
            }
        ],
    }

    placeholder_modal = client.views_open(
        trigger_id=body["trigger_id"], view=placeholder
    )

    # stale_channels = get_stale_channels(client)
    stale_channels = slack_channels.get_stale_channels(
        client, INCIDENT_CHANNELS_PATTERN
    )

    blocks = {
        "type": "modal",
        "callback_id": "stale_incidents_view",
        "title": {"type": "plain_text", "text": "SRE - Stale incidents"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            item
            for sublist in list(map(channel_item, stale_channels))
            for item in sublist
        ],
    }

    client.views_update(view_id=placeholder_modal["view"]["id"], view=blocks)


# Function to be triggered when the /sre incident schedule command is called. This function brings up a modal window
# that explains how the event is scheduled and allows the user to schedule a retro meeting for the incident after the
# submit button is clicked.
def schedule_incident_retro(client: WebClient, body, ack):
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
    data_to_send = json.dumps(
        {
            "name": channel_name,
            "incident_document": document_id,
            "channel_id": channel_id,
        }
    )

    # Fetch user details from all members of the channel
    users = slack_channels.fetch_user_details(client, channel_id)

    blocks = {
        "type": "modal",
        "callback_id": "view_save_event",
        "private_metadata": data_to_send,
        "title": {"type": "plain_text", "text": "SRE - Schedule Retro 🗓️"},
        "submit": {"type": "plain_text", "text": "Schedule"},
        "blocks": (
            [
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
                    "type": "input",
                    "block_id": "user_select_block",
                    "label": {
                        "type": "plain_text",
                        "text": "Select everyone you want to include in the retro calendar invite",
                        "emoji": True,
                    },
                    "element": {
                        "type": "multi_static_select",
                        "action_id": "user_select_action",
                        "options": users,
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
        ),
    }
    # Open the modal window
    client.views_open(
        trigger_id=body["trigger_id"],
        view=blocks,
    )


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
    result = schedule_retro.schedule_event(view["private_metadata"], days, user_emails)
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


def channel_item(channel):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<#{channel['id']}>",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        channel["topic"]["value"]
                        if channel["topic"]["value"]
                        else "No information available"
                    ),
                }
            ],
        },
        {"type": "divider"},
    ]


def handle_update_status_command(
    client: WebClient, body, respond: Respond, ack: Ack, args
):
    ack()
    status = str.join(" ", args)
    valid_statuses = [
        "In Progress",
        "Open",
        "Ready to be Reviewed",
        "Reviewed",
        "Closed",
    ]

    if status not in valid_statuses:
        respond("Invalid status. Valid statuses are: " + ", ".join(valid_statuses))
    else:
        respond(f"Updating incident status to {status}...")
        incident_status.update_status(
            client,
            ack,
            respond,
            status,
            body["channel_id"],
            body["channel_name"],
            body["user_id"],
        )

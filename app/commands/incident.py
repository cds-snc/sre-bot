import os
import re
import datetime
import i18n

from integrations import google_drive, opsgenie
from models import webhooks
from commands.utils import (
    log_to_sentinel,
    get_user_locale,
    rearrange_by_datetime_ascending,
    convert_epoch_to_datetime_est,
    extract_google_doc_id,
)
from integrations.google_drive import (
    get_timeline_section,
    replace_text_between_headings,
)

from dotenv import load_dotenv

load_dotenv()

i18n.load_path.append("./commands/locales/")

i18n.set("locale", "en-US")
i18n.set("fallback", "en-US")

INCIDENT_CHANNEL = os.environ.get("INCIDENT_CHANNEL")
SLACK_SECURITY_USER_GROUP_ID = os.environ.get("SLACK_SECURITY_USER_GROUP_ID")
START_HEADING = "DO NOT REMOVE this message as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"


def handle_incident_action_buttons(client, ack, body, logger):
    delete_block = False
    name = body["actions"][0]["name"]
    value = body["actions"][0]["value"]
    user = body["user"]["id"]
    if name == "call-incident":
        open_modal(client, ack, {"text": value}, body)
        log_to_sentinel("call_incident_button_pressed", body)
    elif name == "ignore-incident":
        ack()
        webhooks.increment_acknowledged_count(value)
        attachments = body["original_message"]["attachments"]
        msg = (
            f"🙈  <@{user}> has acknowledged and ignored the incident.\n"
            f"<@{user}> a pris connaissance et ignoré l'incident."
        )
        # if the last attachment is a preview from a link, switch the places of the last 2 attachments so that the incident buttons can be appended properly
        if len(attachments) > 1:
            if "app_unfurl_url" in attachments[-1]:
                attachments[-2], attachments[-1] = attachments[-1], attachments[-2]
        attachments[-1] = {
            "color": "3AA3E3",
            "fallback": f"{msg}",
            "text": f"{msg}",
        }
        body["original_message"]["attachments"] = attachments
        body["original_message"]["channel"] = body["channel"]["id"]

        # rich_text blocks are only available for 1st party Slack clients (meaning Desktop, iOS, Android Slack apps)
        # https://github.com/slackapi/bolt-js/issues/1324
        if "blocks" in body["original_message"]:
            for block in body["original_message"]["blocks"]:
                if "type" in block and block["type"] == "rich_text":
                    delete_block = True

        if delete_block:
            body["original_message"]["blocks"] = []

        logger.info(f"Updating chat: {body['original_message']}")
        client.api_call("chat.update", json=body["original_message"])
        log_to_sentinel("ignore_incident_button_pressed", body)


def generate_incident_modal_view(command, options=[], locale="en-US"):
    return {
        "type": "modal",
        "callback_id": "incident_view",
        "title": {"type": "plain_text", "text": i18n.t("incident.modal.title")},
        "submit": {"type": "plain_text", "text": i18n.t("incident.submit")},
        "blocks": [
            {
                "type": "actions",
                "block_id": "locale",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": i18n.t("incident.locale_button"),
                            "emoji": True,
                        },
                        "value": locale,
                        "action_id": "incident_change_locale",
                    }
                ],
            },
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.congratulations"),
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": i18n.t("incident.modal.something_wrong"),
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": i18n.t("incident.modal.app_help"),
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.fill_the_fields"),
                },
            },
            {
                "block_id": "name",
                "type": "input",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "name",
                    "initial_value": command["text"],
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.description"),
                },
            },
            {
                "block_id": "product",
                "type": "input",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("incident.modal.product"),
                    },
                    "options": options,
                    "action_id": "product",
                },
                "label": {"type": "plain_text", "text": "Product", "emoji": True},
            },
        ],
    }


def open_modal(client, ack, command, body):
    ack()
    folders = google_drive.list_folders()
    options = [
        {
            "text": {"type": "plain_text", "text": i["name"]},
            "value": i["id"],
        }
        for i in folders
    ]
    if "user" in body:
        user_id = body["user"]["id"]
    else:
        user_id = body["user_id"]
    locale = get_user_locale(user_id, client)
    i18n.set("locale", locale)
    view = generate_incident_modal_view(command, options, locale)
    client.views_open(trigger_id=body["trigger_id"], view=view)


def handle_change_locale_button(ack, client, body):
    ack()
    folders = google_drive.list_folders()
    options = [
        {
            "text": {"type": "plain_text", "text": i["name"]},
            "value": i["id"],
        }
        for i in folders
    ]
    locale = body["actions"][0]["value"]
    if locale == "en-US":
        locale = "fr-FR"
    else:
        locale = "en-US"
    i18n.set("locale", locale)
    command = {"text": body["view"]["state"]["values"]["name"]["name"]["value"]}
    if command["text"] is None:
        command["text"] = ""
    view = generate_incident_modal_view(command, options, locale)
    client.views_update(view_id=body["view"]["id"], view=view)


def submit(ack, view, say, body, client, logger):
    ack(
        response_action="update",
        view=generate_success_modal(body),
    )

    errors = {}

    name = view["state"]["values"]["name"]["name"]["value"]
    folder = view["state"]["values"]["product"]["product"]["selected_option"]["value"]
    product = view["state"]["values"]["product"]["product"]["selected_option"]["text"][
        "text"
    ]

    if not re.match(r"^[\w\-\s]+$", name):
        errors[
            "name"
        ] = "Description must only contain number and letters // La description ne doit contenir que des nombres et des lettres"
    if len(name) > 60:
        errors[
            "name"
        ] = "Description must be less than 60 characters // La description doit contenir moins de 60 caractères"
    if len(errors) > 0:
        ack(response_action="errors", errors=errors)
        return

    log_to_sentinel("incident_called", body)

    # Get folder metadata
    folder_metadata = google_drive.list_metadata(folder).get("appProperties", {})
    oncall = []

    # Get OpsGenie data
    if "genie_schedule" in folder_metadata:
        for email in opsgenie.get_on_call_users(folder_metadata["genie_schedule"]):
            r = client.users_lookupByEmail(email=email)
            if r.get("ok"):
                oncall.append(r["user"])

    date = datetime.datetime.now().strftime("%Y-%m-%d")
    slug = f"{date} {name}".replace(" ", "-").lower()

    # Create channel
    response = client.conversations_create(name=f"incident-{slug}")
    channel_id = response["channel"]["id"]
    channel_name = response["channel"]["name"]
    logger.info(f"Created conversation: {channel_name}")

    channel_id = response["channel"]["id"]
    channel_url = f"https://gcdigital.slack.com/archives/{channel_id}"

    # Set topic
    client.conversations_setTopic(
        channel=channel_id, topic=f"Incident: {name} / {product}"
    )

    # Announce incident
    user_id = body["user"]["id"]
    text = (
        f"<@{user_id}> has kicked off a new incident: {name} for {product}"
        f" in <#{channel_id}>\n"
        f"<@{user_id}> a initié un nouvel incident: {name} pour {product}"
        f" dans <#{channel_id}>"
    )
    say(text=text, channel=INCIDENT_CHANNEL)

    # Add incident creator to channel
    client.conversations_invite(channel=channel_id, users=user_id)

    # Add meeting link
    meet_link = f"https://g.co/meet/incident-{slug}"
    # Max character length for Google Meet nickname is 60, 78 with constant URI
    if len(meet_link) > 78:
        meet_link = meet_link[:78]
    client.bookmarks_add(
        channel_id=channel_id, title="Meet link", type="link", link=meet_link
    )

    text = f"A hangout has been created at: {meet_link}"
    say(text=text, channel=channel_id)

    # Create incident document
    document_id = google_drive.create_new_incident(slug, folder)
    logger.info(f"Created document: {slug} in folder: {folder} / {document_id}")

    # Merge data
    google_drive.merge_data(
        document_id,
        name,
        product,
        channel_url,
        ", ".join(list(map(lambda x: x["profile"]["display_name_normalized"], oncall))),
    )
    document_link = f"https://docs.google.com/document/d/{document_id}/edit"

    # Update incident list
    google_drive.update_incident_list(document_link, name, slug, product, channel_url)

    # Bookmark incident document
    client.bookmarks_add(
        channel_id=channel_id,
        title="Incident report",
        type="link",
        link=document_link,
    )

    text = f":lapage: An incident report has been created at: {document_link}"
    say(text=text, channel=channel_id)

    # Reminder to brief up
    text = ":alphabet-yellow-question: Is this a `cybersecurity incident` (secret/data leak, account compromise, attack)? Please initiate the briefing process for CCCS and TBS OCIO Cyber. This just means we send a summary of the incident (or initial findings and updates if incident is ongoing) to cyberincident@cyber.gc.ca and CC zztbscybers@tbs-sct.gc.ca, and security@cds-snc.ca! CCCS will reach out with a case number, and any questions if they need more information."
    say(text=text, channel=channel_id)

    # Reminder to stop planned testing
    text = ":alphabet-yellow-question: Is someone `penetration or performance testing`? Please stop it to make your life easier."
    say(text=text, channel=channel_id)

    # Gather all user IDs in a list to ensure uniqueness
    users_to_invite = []

    # Add oncall users, excluding the user_id
    for user in oncall:
        if user["id"] != user_id:
            users_to_invite.append(user["id"])

    # Get users from the @security group
    response = client.usergroups_users_list(usergroup=SLACK_SECURITY_USER_GROUP_ID)
    if response.get("ok"):
        for security_user in response["users"]:
            if security_user != user_id:
                users_to_invite.append(security_user)

    # Invite all collected users to the channel in a single API call
    if users_to_invite:
        client.conversations_invite(channel=channel_id, users=users_to_invite)

    text = "Run `/sre incident roles` to assign roles to the incident"
    say(text=text, channel=channel_id)

    text = "Run `/sre incident close` to update the status of the incident document and incident spreadsheet to closed and to archive the channel"
    say(text=text, channel=channel_id)


def generate_success_modal(body):
    locale = body["view"]["blocks"][0]["elements"][0]["value"]
    if locale != "fr-FR":
        locale = "en-US"
    i18n.set("locale", locale)
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": i18n.t("incident.modal.title")},
        "close": {"type": "plain_text", "text": "OK"},
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.success"),
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": i18n.t("incident.modal.user_added"),
                    "emoji": True,
                },
            },
        ],
    }


def handle_reaction_added(client, ack, body, logger):
    ack()
    # get the channel in which the reaction was used
    channel_id = body["event"]["item"]["channel"]
    # Get the channel name which requires us to use the conversations_info API call
    channel_name = client.conversations_info(channel=channel_id)["channel"]["name"]

    # if the emoji added is a floppy disk emoji and we are in an incident channel, then add the message to the incident timeline
    if channel_name.startswith("incident-"):
        # get the message from the conversation
        try:
            # get the messages from the conversation and incident channel
            messages = return_messages(client, body, channel_id)

            # get the incident report document id from the incident channel
            # get and update the incident document
            document_id = ""
            response = client.bookmarks_list(channel_id=channel_id)
            if response["ok"]:
                for item in range(len(response["bookmarks"])):
                    if response["bookmarks"][item]["title"] == "Incident report":
                        document_id = extract_google_doc_id(
                            response["bookmarks"][item]["link"]
                        )
                        if document_id == "":
                            logger.error("No incident document found for this channel.")
            
            for message in messages:
                # convert the time which is now in epoch time to standard ET Time
                message_date_time = convert_epoch_to_datetime_est(message["ts"])
                # get the user name from the message
                user = client.users_profile_get(user=message["user"])
                # get the full name of the user so that we include it into the timeline
                user_full_name = user["profile"]["real_name"]

                # get the current timeline section content
                content = get_timeline_section(document_id)

                # if the message already exists in the timeline, then don't put it there again
                if content and message_date_time not in content:
                    # append the new message to the content
                    content += (
                        f"{message_date_time} {user_full_name}: {message['text']}"
                    )

                    # if there is an image in the message, then add it to the timeline
                    if "files" in message:
                        image = message["files"][0]["url_private"]
                        content += f"\nImage: {image}"

                    # sort all the message to be in ascending chronological order
                    sorted_content = rearrange_by_datetime_ascending(content)

                    # replace the content in the file with the new headings
                    replace_text_between_headings(
                        document_id, sorted_content, START_HEADING, END_HEADING
                    )
        except Exception as e:
            logger.error(e)


# Execute this function when a reaction was removed
def handle_reaction_removed(client, ack, body, logger):
    ack()
    # get the channel id
    channel_id = body["event"]["item"]["channel"]

    # Get the channel name which requires us to use the conversations_info API call
    result = client.conversations_info(channel=channel_id)
    channel_name = result["channel"]["name"]

    if channel_name.startswith("incident-"):
        try:
            messages = return_messages(client, body, channel_id)

            if not messages:
                logger.warning("No messages found")
                return
            # get the message we want to delete
            message = messages[0]

            # convert the epoch time to standard ET day/time
            message_date_time = convert_epoch_to_datetime_est(message["ts"])

            # get the user of the person that send the message
            user = client.users_profile_get(user=message["user"])
            # get the user's full name
            user_full_name = user["profile"]["real_name"]

            # get the incident report document id from the incident channel
            # get and update the incident document
            document_id = ""
            response = client.bookmarks_list(channel_id=channel_id)
            if response["ok"]:
                for item in range(len(response["bookmarks"])):
                    if response["bookmarks"][item]["title"] == "Incident report":
                        document_id = extract_google_doc_id(
                            response["bookmarks"][item]["link"]
                        )
                        if document_id == "":
                            logger.error("No incident document found for this channel.")
                            
            # Retrieve the current content of the timeline
            content = get_timeline_section(document_id)

            # Construct the message to remove
            message_to_remove = (
                f"\n{message_date_time} {user_full_name}: {message['text']}\n"
            )
            # if there is a file in the message, then add it to the message to remove
            if "files" in message:
                image = message["files"][0]["url_private"]
                message_to_remove += f"\nImage: {image}"

            # Remove the message
            if message_to_remove in content:
                content = content.replace(message_to_remove, "\n")

                # Update the timeline content
                result = replace_text_between_headings(
                    document_id,
                    content,
                    START_HEADING,
                    END_HEADING,
                )
            else:
                logger.warning("Message not found in the timeline")
                return
        except Exception as e:
            logger.error(e)


# Function to return the messages from the conversation
def return_messages(client, body, channel_id):
    # Fetch the message that had the reaction removed
    result = client.conversations_history(
        channel=channel_id,
        limit=1,
        inclusive=True,
        oldest=body["event"]["item"]["ts"],
    )
    # get the messages
    messages = result["messages"]
    # if the lenght is 0, then the message is part of a thread, so get the message from the thread
    if messages.__len__() == 0:
        # get thread messages
        result = client.conversations_replies(
            channel=channel_id,
            ts=body["event"]["item"]["ts"],
            inclusive=True,
            include_all_metadata=True,
        )
        messages = result["messages"]
    return messages

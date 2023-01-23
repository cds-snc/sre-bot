import os
import i18n
from commands import utils
from integrations import google_drive

from dotenv import load_dotenv

load_dotenv()

i18n.load_path.append("./commands/locales/")

# Set the locale
i18n.set("locale", "en-US")
i18n.set("fallback", "en-CA")


def update_locale(locale):
    # Function to update the locale
    if i18n.get("locale") != locale:
        i18n.set("locale", locale)


def role_command(ack, command, logger, respond, client, body):
    # Function to execute the role command based on the arguments provided

    # acknowledge to slack that the command was received
    ack()

    # get the user id and set the locale for the user
    user_id = body["user_id"]
    # get the user locale from slack.
    update_locale(utils.get_user_locale(user_id, client))
    logger.info("User locale: %s", i18n.get("locale"))

    logger.info("Role command received: %s", command["text"])

    # process the command
    if command["text"] == "":
        respond(i18n.t("role.help_text", command=command["command"]))
        return
    action, *args = utils.parse_command(command["text"])
    match action:
        case "help":
            update_locale("en-US")
            respond(i18n.t("role.help_text", command=command["command"]))
        case "aide":
            update_locale("fr-FR")
            respond(i18n.t("role.help_text", command=command["command"]))
        case "new":
            update_locale("en-US")
            request_start_modal(client, body, locale="en-US")
        case "nouveau":
            update_locale("fr-FR")
            request_start_modal(client, body, locale="fr-FR")
        case _:
            respond(
                i18n.t(
                    "role.unknown_command", action=action, command=command["command"]
                )
            )


def request_start_modal(client, body, locale):
    update_locale(locale)
    view = role_modal_view(locale)
    client.views_open(trigger_id=body["trigger_id"], view=view)


def role_modal_view(locale):
    # Function to display the GUI for creating a new role
    view = {
        "type": "modal",
        "callback_id": "role_view",
        "title": {"type": "plain_text", "text": i18n.t("role.title")},
        "submit": {"type": "plain_text", "text": i18n.t("role.submit")},
        "blocks": [
            {
                "type": "actions",
                "block_id": "role_locale",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": i18n.t("role.locale_button"),
                            "emoji": True,
                        },
                        "value": locale,
                        "action_id": "role_change_locale",
                    },
                ],
            },
            {
                "type": "input",
                "block_id": "role_name",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "role_name",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("role.placeholder_role"),
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("role.input_label"),
                    "emoji": True,
                },
            },
            {
                "type": "input",
                "block_id": "channel_name",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "channel_name",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("role.placeholder_channel"),
                    },
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("role.channel_name"),
                    "emoji": True,
                },
            },
            {
                "type": "input",
                "block_id": "users_invited",
                "element": {
                    "type": "multi_users_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": i18n.t("role.select_users"),
                        "emoji": True,
                    },
                    "action_id": "users_invited",
                },
                "label": {
                    "type": "plain_text",
                    "text": i18n.t("role.channel_invitees"),
                    "emoji": True,
                },
            },
        ],
    }
    return view


def role_view_handler(ack, body, say, logger, client):
    ack()
    logger.info("Body is: %s", body)

    role_name = body["view"]["state"]["values"]["role_name"]["role_name"]["value"]
    logger.info("Role name is: %s", role_name)
    private_channel_name = body["view"]["state"]["values"]["channel_name"][
        "channel_name"
    ]["value"]
    logger.info("Channel name is: %s", private_channel_name)

    # Steps to execute when the modal is submitted:
    # 1. Create a new folder in the Google Drive
    # 2. Copy the template files into the new folder
    # 3. Create a new channel and invite users

    # Step 1: Create a new folder in the Google Drive
    folder_id = google_drive.create_new_folder(
        role_name, os.getenv("INTERNAL_TALENT_FOLDER")
    )
    logger.info(f"Created folder: {role_name} / {folder_id}")

    # Step 2: Copy the template files into the new folder (Scoring Guilde, Template for Core Values interview notes, Template for Technical interview notes
    # Intake form, SoMC template)
    scoring_guide_id = google_drive.copy_file_to_folder(
        os.getenv("SCORING_GUIDE_TEMPLATE"),
        f"Template 2022/06 - {role_name} Interview Panel Scoring Document - <year/month> ",
        os.getenv("TEMPLATES_FOLDER"),
        folder_id,
    )
    logger.info(
        f"Created document: Scoring Guide in folder: Scoring Guide / {scoring_guide_id}"
    )

    core_values_interview_notes_id = google_drive.copy_file_to_folder(
        os.getenv("CORE_VALUES_INTERVIEW_NOTES_TEMPLATE"),
        f"Template EN+FR 2022/09- {role_name} - Core Values Panel - Interview Guide - <year/month> - <candidate initials> ",
        os.getenv("TEMPLATES_FOLDER"),
        folder_id,
    )
    logger.info(
        f"Created document: Core Values Interview Notes in folder: Core Values Interview Notes / {core_values_interview_notes_id}"
    )

    technical_interview_notes_id = google_drive.copy_file_to_folder(
        os.getenv("TECHNICAL_INTERVIEW_NOTES_TEMPLATE"),
        f"Template EN+FR 2022/09 - {role_name} - Technical Panel - Interview Guide - <year/month> - <candidate initials> ",
        os.getenv("TEMPLATES_FOLDER"),
        folder_id,
    )
    logger.info(
        f"Created document: Technical Interview Notes in folder: Technical Interview Notes / {technical_interview_notes_id}"
    )

    intake_form_id = google_drive.copy_file_to_folder(
        os.getenv("INTAKE_FORM_TEMPLATE"),
        f"TEMPLATE Month YYYY - {role_name} - Kick-off form",
        os.getenv("TEMPLATES_FOLDER"),
        folder_id,
    )
    logger.info(
        f"Created document: Intake Form in folder: Intake Form / {intake_form_id}"
    )

    somc_template_id = google_drive.copy_file_to_folder(
        os.getenv("SOMC_TEMPLATE"),
        "SoMC Template",
        os.getenv("TEMPLATES_FOLDER"),
        folder_id,
    )
    logger.info(
        f"Created document: SoMC Template in folder: SoMC Template / {somc_template_id}"
    )
    # Create channel
    response = client.conversations_create(name=private_channel_name, is_private=True)

    channel_name = response["channel"]["name"]
    logger.info(f"Created conversation: {channel_name}")
    channel_id = response["channel"]["id"]

    # Set topic and include the scoring guide id
    client.conversations_setTopic(
        channel=channel_id,
        topic=f"Channel for {role_name}\nScoring Guide: https://docs.google.com/spreadsheets/d/{scoring_guide_id}",
    )
    # Announce channel creation
    user_id = body["user"]["id"]
    text = (
        f"<@{user_id}> has created a new channel for {role_name} with channel name {channel_name}"
        f" in <#{channel_id}>\n"
    )
    say(text=text, channel=channel_id)

    # Add role creator to channel
    client.conversations_invite(channel=channel_id, users=user_id)

    # Invite others to the channel
    users = body["view"]["state"]["values"]["users_invited"]["users_invited"][
        "selected_users"
    ]
    client.conversations_invite(channel=channel_id, users=",".join(users))


def update_modal_locale(ack, client, body):
    # update the locale
    ack()
    locale = next(
        (
            action
            for action in body["actions"]
            if action["action_id"] == "role_change_locale"
        ),
        None,
    )["value"]
    if locale == "en-US":
        locale = "fr-FR"
    else:
        locale = "en-US"
    i18n.set("locale", locale)
    view_id = body["view"]["id"]
    view = role_modal_view(locale)
    client.views_update(view_id=view_id, view=view)

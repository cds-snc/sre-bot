import i18n  # type: ignore

from slack_bolt import Ack, App, Respond
from slack_sdk import WebClient
from integrations.google_workspace import google_drive
from integrations.slack import users as slack_users, commands as slack_commands

from core.config import settings
from core.logging import get_module_logger


PREFIX = settings.PREFIX
BOT_EMAIL = settings.google_workspace.SRE_BOT_EMAIL

SCORING_GUIDE_TEMPLATE = settings.talent_role.SCORING_GUIDE_TEMPLATE
CORE_VALUES_INTERVIEW_NOTES_TEMPLATE = (
    settings.talent_role.CORE_VALUES_INTERVIEW_NOTES_TEMPLATE
)
TECHNICAL_INTERVIEW_NOTES_TEMPLATE = (
    settings.talent_role.TECHNICAL_INTERVIEW_NOTES_TEMPLATE
)
INTAKE_FORM_TEMPLATE = settings.talent_role.INTAKE_FORM_TEMPLATE
PHONE_SCREEN_TEMPLATE = settings.talent_role.PHONE_SCREEN_TEMPLATE
RECRUITMENT_FEEDBACK_TEMPLATE = settings.talent_role.RECRUITMENT_FEEDBACK_TEMPLATE
PANELIST_GUIDEBOOK_TEMPLATE = settings.talent_role.PANELIST_GUIDEBOOK_TEMPLATE

TEMPLATES_FOLDER = settings.talent_role.TEMPLATES_FOLDER
INTERNAL_TALENT_FOLDER = settings.talent_role.INTERNAL_TALENT_FOLDER

ROLE_SCOPES = ["https://www.googleapis.com/auth/drive"]


# Set the locale
i18n.load_path.append("./locales/")
i18n.set("locale", "en-US")
i18n.set("fallback", "en-CA")


logger = get_module_logger()


def register(bot: App):
    bot.command(f"/{PREFIX}talent-role")(role_command)
    bot.view("role_view")(role_view_handler)
    bot.action("role_change_locale")(update_modal_locale)


def update_locale(locale):
    # Function to update the locale
    if i18n.get("locale") != locale:
        i18n.set("locale", locale)


def role_command(
    ack: Ack, command: dict, respond: Respond, client: WebClient, body: dict
):
    # Function to execute the role command based on the arguments provided

    # acknowledge to slack that the command was received
    ack()

    logger.info(
        "talent_role_command_received",
        command=command["text"],
        user_id=command["user_id"],
        user_name=command["user_name"],
        channel_id=command["channel_id"],
        channel_name=command["channel_name"],
    )
    # get the user id and set the locale for the user
    user_id = body["user_id"]
    # get the user locale from slack.
    update_locale(slack_users.get_user_locale(client, user_id))
    logger.info(
        "slack_user_locale_detected", user_id=user_id, locale=i18n.get("locale")
    )

    # process the command
    if command["text"] == "":
        respond(i18n.t("role.help_text", command=command["command"]))
        return
    action, *args = slack_commands.parse_command(command["text"])
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


def role_view_handler(ack, body, say, client):
    ack()

    def log_document_created(document_name, document_id):
        """Log the creation of a document with a consistent format."""
        logger.info(
            "talent_role_document_created",
            document_name=document_name,
            document_id=document_id,
        )

    role_name = body["view"]["state"]["values"]["role_name"]["role_name"]["value"]
    private_channel_name = body["view"]["state"]["values"]["channel_name"][
        "channel_name"
    ]["value"]
    logger.info(
        "talent_role_view_handler_called",
        role_name=role_name,
        private_channel_name=private_channel_name,
    )

    # Steps to execute when the modal is submitted:
    # 1. Create a new folder in the Google Drive
    # 2. Copy the template files into the new folder
    # 3. Create a new channel and invite users

    # Step 1: Create a new folder in the Google Drive
    folder = google_drive.create_folder(
        role_name,
        INTERNAL_TALENT_FOLDER,
        "id",
        scopes=ROLE_SCOPES,
        delegated_user_email=BOT_EMAIL,
    )
    folder_id = None
    if isinstance(folder, dict):
        folder_id = folder.get("id", None)
    else:
        logger.error(
            "talent_role_folder_creation_failed",
            folder_name=role_name,
            error=folder,
        )
        return

    logger.info(
        "talent_role_folder_created",
        folder_name=role_name,
        folder_id=folder_id,
        role_name=role_name,
    )

    # Step 2: Copy the template files into the new folder (Scoring Guilde, Template for Core Values interview notes, Template for Technical interview notes
    # Intake form, Phone screen template)
    scoring_guide_id = google_drive.copy_file_to_folder(
        SCORING_GUIDE_TEMPLATE,
        f"Template 2022/06 - {role_name} Interview Panel Scoring Document - <year/month> ",
        TEMPLATES_FOLDER,
        folder_id,
        scopes=ROLE_SCOPES,
        delegated_user_email=BOT_EMAIL,
    )
    log_document_created("Scoring Guide", scoring_guide_id)

    core_values_interview_notes_id = google_drive.copy_file_to_folder(
        CORE_VALUES_INTERVIEW_NOTES_TEMPLATE,
        f"Template EN+FR 2022/09- {role_name} - Core Values Panel - Interview Guide - <year/month> - <candidate initials> ",
        TEMPLATES_FOLDER,
        folder_id,
        scopes=ROLE_SCOPES,
        delegated_user_email=BOT_EMAIL,
    )
    log_document_created("Core Values Interview Notes", core_values_interview_notes_id)

    technical_interview_notes_id = google_drive.copy_file_to_folder(
        TECHNICAL_INTERVIEW_NOTES_TEMPLATE,
        f"Template EN+FR 2022/09 - {role_name} - Technical Panel - Interview Guide - <year/month> - <candidate initials> ",
        TEMPLATES_FOLDER,
        folder_id,
        scopes=ROLE_SCOPES,
        delegated_user_email=BOT_EMAIL,
    )
    log_document_created("Technical Interview Notes", technical_interview_notes_id)

    intake_form_id = google_drive.copy_file_to_folder(
        INTAKE_FORM_TEMPLATE,
        f"TEMPLATE Month YYYY - {role_name} - Kick-off form",
        TEMPLATES_FOLDER,
        folder_id,
        scopes=ROLE_SCOPES,
        delegated_user_email=BOT_EMAIL,
    )
    log_document_created("Intake Form", intake_form_id)

    phone_screen_template_id = google_drive.copy_file_to_folder(
        PHONE_SCREEN_TEMPLATE,
        "Phone Screen - Template",
        TEMPLATES_FOLDER,
        folder_id,
        scopes=ROLE_SCOPES,
        delegated_user_email=BOT_EMAIL,
    )
    log_document_created("Phone Screen Template", phone_screen_template_id)

    recruitment_feedback_template_id = google_drive.copy_file_to_folder(
        RECRUITMENT_FEEDBACK_TEMPLATE,
        f"Recruitment Feedback - {role_name}",
        TEMPLATES_FOLDER,
        folder_id,
        scopes=ROLE_SCOPES,
        delegated_user_email=BOT_EMAIL,
    )
    log_document_created(
        "Recruitment Feedback Template", recruitment_feedback_template_id
    )

    panelist_guidebook_template_id = google_drive.copy_file_to_folder(
        PANELIST_GUIDEBOOK_TEMPLATE,
        f"Panelist Guidebook - Interview Best Practices - {role_name}",
        TEMPLATES_FOLDER,
        folder_id,
        scopes=ROLE_SCOPES,
        delegated_user_email=BOT_EMAIL,
    )
    log_document_created("Panelist Guidebook Template", panelist_guidebook_template_id)

    # Create channel
    response = client.conversations_create(name=private_channel_name, is_private=True)

    channel_name = response["channel"]["name"]
    channel_id = response["channel"]["id"]
    logger.info(
        "talent_role_channel_created",
        channel_name=channel_name,
        channel_id=channel_id,
        role_name=role_name,
    )
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

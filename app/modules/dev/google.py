"""Testing new google service (will be removed)"""

from core.config import settings
from integrations.google_workspace import google_service, google_directory, meet
from core.logging import get_module_logger


GOOGLE_WORKSPACE_CUSTOMER_ID = google_service.GOOGLE_WORKSPACE_CUSTOMER_ID
GOOGLE_SRE_CALENDAR_ID = settings.google_workspace.GOOGLE_SRE_CALENDAR_ID
SRE_BOT_EMAIL = settings.google_workspace.SRE_BOT_EMAIL
SRE_DRIVE_ID = settings.google_workspace.SRE_DRIVE_ID
SRE_INCIDENT_FOLDER = settings.google_workspace.SRE_INCIDENT_FOLDER
INCIDENT_TEMPLATE = settings.google_workspace.INCIDENT_TEMPLATE
logger = get_module_logger()
handle_google_api_errors = google_service.handle_google_api_errors


@handle_google_api_errors
def get_groups():
    scopes = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]
    return google_service.execute_google_api_call(
        "admin",
        "directory_v1",
        "groups",
        "list",
        scopes,
        paginate=True,
        customer=GOOGLE_WORKSPACE_CUSTOMER_ID,
        maxResults=200,
        orderBy="email",
    )


@handle_google_api_errors
def get_members(group_key):
    scopes = ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"]
    members = google_service.execute_google_api_call(
        "admin",
        "directory_v1",
        "members",
        "list",
        scopes,
        paginate=True,
        groupKey=group_key,
        maxResults=200,
    )
    return members


def log_object_info(obj):
    """Logs only the keys of a dict or the type/length of a list."""
    if isinstance(obj, dict):
        logger.info(f"Dict keys: {list(obj.keys())}")
    elif isinstance(obj, list):
        logger.info(f"List of length {len(obj)}")
        if obj:
            log_object_info(obj[0])
    elif isinstance(obj, tuple):
        logger.info(f"Tuple of length {len(obj)}")
        for idx, item in enumerate(obj):
            logger.info(f"Tuple item {idx}:")
            log_object_info(item)
    else:
        logger.info(f"Object type: {type(obj).__name__}")
    return True


def google_service_command(ack, client, body, respond, logger):
    ack()
    logger.info("google_service_command", body=body)
    space = meet.create_space()
    logger.info("google_meet_event_created", space=space)
    if space:
        respond(
            f"Created a new Google Meet space: {space['name']} with meeting code: {space['meetingCode']}"
        )
    else:
        respond("Failed to create a Google Meet space.")

    groups = google_directory.list_groups()
    if groups:
        logger.info("google_groups_listed", groups=groups)
        respond(f"Listed {len(groups)} Google Groups.")

    # groups = get_groups()
    # if groups:
    #     logger.info("google_groups_listed", groups=groups)
    #     respond(f"Listed {len(groups)} Google Groups.")
    else:
        respond("No Google Groups found.")


def test_content():
    post_content = """
        This is a test post content.
        It can support multiple lines.

        For now, it is just a simple string. Future versions will support more complex content.

        Like HTML and markdown.
    """
    return post_content

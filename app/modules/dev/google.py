"""Testing new google service (will be removed)"""

from core.config import settings
from integrations.google_workspace import (
    google_service,
    google_calendar,
)
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
    groups = get_groups()
    if not groups:
        respond("No groups found.")
        return
    group = groups[1]
    logger.info("logging_group_details", details=group)
    logger.info("group_email", email=group["email"])
    email = group["email"]
    members = get_members(email)
    if not members:
        respond(f"No members found in group: {email}")
        return
    log_object_info(members)
    respond(f"Found {len(members)} members in group: {email}")
    for member in members:
        logger.info("member_details", details=member)

    event_start = "2025-05-15T15:30:00-04:00"
    event_end = "2025-05-15T16:00:00-04:00"
    event_title = "Test Calendar Event w/o SRE Bot Account"
    attendees = [SRE_BOT_EMAIL]

    logger.info("calendar_event", event_start=event_start, event_end=event_end)
    calendar_event = google_calendar.insert_event(
        start=event_start,
        end=event_end,
        emails=attendees,
        title=event_title,
        calendar_id=GOOGLE_SRE_CALENDAR_ID,
        incident_document=None,
    )
    logger.info("calendar_event_response", response=calendar_event)


def test_content():
    post_content = """
        This is a test post content.
        It can support multiple lines.

        For now, it is just a simple string. Future versions will support more complex content.

        Like HTML and markdown.
    """
    return post_content

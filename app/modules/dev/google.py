"""Testing new google service (will be removed)"""

import json
from core.config import settings
from core.logging import get_module_logger
from integrations.google_workspace import (
    google_service_next as google_service,
    google_directory_next,
    google_directory,
)
from integrations.slack.users import get_user_email_from_body

GOOGLE_WORKSPACE_CUSTOMER_ID = google_service.GOOGLE_WORKSPACE_CUSTOMER_ID
GOOGLE_SRE_CALENDAR_ID = settings.google_workspace.GOOGLE_SRE_CALENDAR_ID
SRE_BOT_EMAIL = settings.google_workspace.SRE_BOT_EMAIL
SRE_DRIVE_ID = settings.google_workspace.SRE_DRIVE_ID
SRE_INCIDENT_FOLDER = settings.google_workspace.SRE_INCIDENT_FOLDER
INCIDENT_TEMPLATE = settings.google_workspace.INCIDENT_TEMPLATE
logger = get_module_logger()


def google_service_command(ack, client, body, respond, logger):
    ack()
    logger.info("google_service_command", body=body)
    respond("Google service command received!")
    # Prepare kwargs to filter for group emails starting with 'aws-' and limit to 3 groups
    # No members_kwargs needed for this test, but could add roles, etc.
    result = google_directory_next.performance_comparison_example()
    try:
        with open("test_next.json", "w", encoding="utf-8") as f:
            json.dump(result["next"], f, indent=2)
        logger.info(
            "Saved group membership result to test_next.json", count=len(result["next"])
        )
    except Exception as e:
        logger.error("Failed to save test_next.json", error=str(e))
    try:
        with open("test_legacy.json", "w", encoding="utf-8") as f:
            json.dump(result["legacy"], f, indent=2)
        logger.info(
            "Saved group membership result2 to test_legacy.json",
            count=len(result["legacy"]),
        )
    except Exception as e:
        logger.error("Failed to save test_legacy.json", error=str(e))

    # Respond with a summary
    if result:
        legacy = result.get("legacy", {})
        next_ = result.get("next", {})

        legacy_count = legacy.get("group_count", 0)
        legacy_members = legacy.get("member_count", 0)
        legacy_time = legacy.get("time")
        legacy_groups = legacy.get("groups", [])

        next_count = next_.get("group_count", 0)
        next_members = next_.get("member_count", 0)
        next_time = next_.get("time")
        next_groups = next_.get("groups", [])

        def _sample_groups(groups, limit=5):
            out = []
            for g in (groups or [])[:limit]:
                if isinstance(g, dict):
                    out.append(g.get("email") or g.get("groupKey") or str(g))
                else:
                    out.append(str(g))
            return out

        legacy_sample = _sample_groups(legacy_groups)
        next_sample = _sample_groups(next_groups)

        summary_lines = [
            "Google directory comparison results:",
            "",
            "Legacy:",
            f"  groups: {legacy_count}",
            f"  members: {legacy_members}",
            f"  time: {legacy_time}",
            f"  sample groups: {legacy_sample}",
            "",
            "Next:",
            f"  groups: {next_count}",
            f"  members: {next_members}",
            f"  time: {next_time}",
            f"  sample groups: {next_sample}",
        ]

        respond("\n".join(summary_lines))
    else:
        respond("No groups found or failed to retrieve group information.")

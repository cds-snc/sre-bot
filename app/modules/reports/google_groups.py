import time
from datetime import datetime

from core.config import settings
from core.logging import get_module_logger
from integrations.google_workspace import (
    google_directory,
    sheets,
    google_drive,
)

FOLDER_REPORTS_GOOGLE_GROUPS = settings.reports.FOLDER_REPORTS_GOOGLE_GROUPS

logger = get_module_logger()


def generate_report(args, respond):
    respond("Generating Google Groups report is not implemented yet.")


def generate_group_members_report(args, respond):
    """Generate a report of Google Groups members."""
    if not FOLDER_REPORTS_GOOGLE_GROUPS:
        respond("Google Drive folder for reports not set.")
        return
    exclude_groups = ["AWS-"]
    logger.info(
        "group_members_report_started",
        group="Google Groups",
    )
    filename = f"groups_report_{datetime.now().strftime('%Y-%m-%d')}"
    logger.info("getting_group_file", filename=filename)
    files = google_drive.find_files_by_name(filename, FOLDER_REPORTS_GOOGLE_GROUPS)

    if len(files) == 0:
        logger.info("file_not_found_creating_new_file", filename=filename)
        file = google_drive.create_file(
            filename, FOLDER_REPORTS_GOOGLE_GROUPS, "spreadsheet"
        )
    else:
        file = files[0]
        logger.info("file_found", filename=filename, file=file)

    logger.info("getting_google_groups")
    groups = google_directory.list_groups()
    groups = [
        group
        for group in groups
        if not any(exclude in group["name"] for exclude in exclude_groups)
    ]

    if not groups:
        respond("No groups found.")
        return

    logger.info("groups_found", count=len(groups))
    groups_with_members = []
    for _index, group in enumerate(groups):
        logger.info(
            "processing_group",
            group_email=group["email"],
        )
        members = google_directory.list_group_members(group["email"])
        group["members"] = members
        groups_with_members.append(group)

    for group in groups_with_members:
        group_sheet_name = f"{group['name']}"
        logger.info("processing_group_sheet", group=group_sheet_name)
        if len(group_sheet_name) > 50:
            group_sheet_name = group_sheet_name[:50]

        try:
            sheet = sheets.get_sheet(file["id"], group_sheet_name)
        except Exception:
            sheet = None
        if sheet:
            logger.info("sheet_found", sheet=sheet)
        else:
            try:
                request = {
                    "requests": [
                        {
                            "addSheet": {
                                "properties": {
                                    "title": group_sheet_name,
                                }
                            }
                        }
                    ]
                }
                sheet = sheets.batch_update(file["id"], request)
                if sheet:
                    logger.info("sheet_created", sheet=group_sheet_name)
            except Exception as e:
                logger.error("sheet_creation_failed", error=str(e))

        values = [["Group Name", group_sheet_name], ["Email", "Role"]]
        group_sheet_name = f"{group_sheet_name}!A1"
        for member in group["members"]:
            values.append([member["email"], member["role"]])
        updated_sheet = sheets.batch_update_values(
            file["id"],
            group_sheet_name,
            values,
        )
        if updated_sheet:
            logger.info("sheet_updated", sheet=group_sheet_name)

        time.sleep(1.1)

    respond("Google Groups Members report generated.")

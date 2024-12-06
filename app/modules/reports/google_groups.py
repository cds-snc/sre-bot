import os
import time
from datetime import datetime
from dotenv import load_dotenv
from integrations.google_workspace import (
    google_directory,
    sheets,
    google_drive,
)

load_dotenv()

DELEGATED_USER_EMAIL = os.environ.get("GOOGLE_DELEGATED_ADMIN_EMAIL")
FOLDER_REPORTS_GOOGLE_GROUPS = os.environ.get(
    "FOLDER_REPORTS_GOOGLE_GROUPS", ""
)


def generate_report(args, respond):
    respond("Generating Google Groups report is not implemented yet.")


def generate_group_members_report(args, respond, logger):
    """Generate a report of Google Groups members."""
    if not FOLDER_REPORTS_GOOGLE_GROUPS:
        respond("Google Drive folder for reports not set.")
        return
    exclude_groups = ["AWS-"]
    logger.info("Generating Google Groups Members report...")
    filename = f"groups_report_{datetime.now().strftime('%Y-%m-%d')}"
    logger.info(f"Filename: {filename}")
    files = google_drive.find_files_by_name(filename, FOLDER_REPORTS_GOOGLE_GROUPS)

    if len(files) == 0:
        logger.info("No files found. Creating a new file.")
        file = google_drive.create_file(
            filename, FOLDER_REPORTS_GOOGLE_GROUPS, "spreadsheet"
        )
    else:
        logger.info("File found. Displaying the first file.")
        file = files[0]

    logger.info(f"File: {file}")

    groups = google_directory.list_groups()
    groups = [
        group
        for group in groups
        if not any(exclude in group["name"] for exclude in exclude_groups)
    ]

    if not groups:
        respond("No groups found.")
        return

    groups_with_members = []
    for index, group in enumerate(groups):
        logger.info(f"Processing group {index + 1}/{len(groups)}: {group['email']}")
        members = google_directory.list_group_members(group["email"])
        group["members"] = members
        groups_with_members.append(group)

    for group in groups_with_members:
        range = f"{group['name']}"
        logger.info(f"Creating sheet '{range}'")
        if len(range) > 50:
            range = range[:50]

        try:
            sheet = sheets.get_sheet(file["id"], range)
        except Exception:
            sheet = None
        if sheet:
            logger.info(f"Sheet '{range}' already exists")
        else:
            try:
                request = {
                    "requests": [
                        {
                            "addSheet": {
                                "properties": {
                                    "title": range,
                                }
                            }
                        }
                    ]
                }
                sheet = sheets.batch_update(file["id"], request)
                if sheet:
                    logger.info(f"Sheet '{range}' created")
            except Exception as e:
                logger.error(e)
        values = [["Group Name", range], ["Email", "Role"]]
        range = f"{range}!A1"
        for member in group["members"]:
            values.append([member["email"], member["role"]])
        updated_sheet = sheets.batch_update_values(
            file["id"],
            range,
            values,
        )
        if updated_sheet:
            logger.info(f"Sheet '{group['name']}' updated")

        time.sleep(1.1)

    respond("Google Groups Members report generated.")

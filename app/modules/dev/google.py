"""Testing new google service (will be removed)"""

import time
import json
import os
from datetime import datetime

from integrations.google_workspace import (
    google_directory,
    sheets,
    google_drive,
)
from integrations.slack import users as slack_users

from dotenv import load_dotenv

load_dotenv()

SRE_DRIVE_ID = os.environ.get("SRE_DRIVE_ID")
SRE_INCIDENT_FOLDER = os.environ.get("SRE_INCIDENT_FOLDER")
INCIDENT_TEMPLATE = os.environ.get("INCIDENT_TEMPLATE")
REPORT_GOOGLE_GROUPS_FOLDER = "18IYoyg5AFz3ZsZSSqvP1iaJur1V3Fmvi"
GROUPS_MEMBERSHIPS_FOLDER = "1KPwrP-fWA0VVCrxW22Z4GJLcTb5-Avjf"


def get_members(group):
    members = google_directory.list_group_members(group)
    return members


def google_service_command(ack, client, body, respond, logger):
    ack()

    exclude_groups = ["AWS-"]
    filename = f"groups_report_{datetime.now().strftime('%Y-%m-%d')}"
    logger.info(f"Filename: {filename}")

    files = google_drive.find_files_by_name(filename, REPORT_GOOGLE_GROUPS_FOLDER)

    if len(files) == 0:
        logger.info("No files found. Creating a new file.")
        file = google_drive.create_file(
            filename, REPORT_GOOGLE_GROUPS_FOLDER, "spreadsheet"
        )
    else:
        logger.info("File found. Displaying the first file.")
        file = files[0]

    logger.info(f"File: {file}")

    # file = google_drive.find_files_by_name(filename, REPORT_GOOGLE_GROUPS_FOLDER)

    # # sheetnames max 50 characters

    groups = google_directory.list_groups()

    groups = [
        group
        for group in groups
        if not any(exclude in group["name"] for exclude in exclude_groups)
    ]
    # response = google_directory.list_groups()

    # response = google_directory.list_groups_with_members(
    #     query="aws-*", authenticated_service=authenticated_service
    # )
    if not groups:
        respond("No groups found.")
        return

    groups_with_members = []
    for index, group in enumerate(groups):
        logger.info(f"Processing group {index + 1}/{len(groups)}: {group['email']}")
        members = get_members(group["email"])
        group["members"] = members
        groups_with_members.append(group)

    # Extract necessary information from the response
    logger.info("Response:")

    for group in groups_with_members:
        range = f"{group['name']}"
        if len(range) > 50:
            range = range[:50]

        sheet = sheets.get_sheet(file["id"], range)
        if sheet:
            logger.info(f"Sheet '{range}' already exists")
            
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

        time.sleep(1.1)  # Delay of 1.1 seconds between each write action


def test_content():
    post_content = """
        This is a test post content.
        It can support multiple lines.

        For now, it is just a simple string. Future versions will support more complex content.

        Like HTML and markdown.
    """
    return post_content

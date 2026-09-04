import hashlib
import time
from datetime import datetime

from structlog import get_logger

from infrastructure.configuration.integrations.google import get_google_resources_config
from infrastructure.directory import get_directory_provider
from integrations.google_workspace import (
    google_drive,
    sheets,
)

FOLDER_REPORTS_GOOGLE_GROUPS = get_google_resources_config().google_groups_reports_folder_id

logger = get_logger()

_SHEET_TITLE_MAX_LENGTH = 50
_SHEET_TITLE_DIGEST_LENGTH = 6


class DirectoryReportError(Exception):
    """Raised when a directory lookup needed by the report fails."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def _sheet_title(group_name: str) -> str:
    """Derive a bounded, collision-safe sheet title from a group display name."""
    # Apostrophes are stripped so no title can carry the A1 quote character.
    sanitised = group_name.replace("'", "")
    if sanitised == group_name and len(sanitised) <= _SHEET_TITLE_MAX_LENGTH:
        return sanitised
    # sha256, never the salted builtin hash(), so titles are stable across processes.
    digest = hashlib.sha256(group_name.encode("utf-8")).hexdigest()[:_SHEET_TITLE_DIGEST_LENGTH]
    keep = _SHEET_TITLE_MAX_LENGTH - _SHEET_TITLE_DIGEST_LENGTH - 1
    return f"{sanitised[:keep]}-{digest}"


def _a1_range(sheet_title: str, cell: str = "") -> str:
    """Quote a sheet title for A1 notation, doubling any embedded single quote."""
    quoted = "'{}'".format(sheet_title.replace("'", "''"))
    return f"{quoted}!{cell}" if cell else quoted


def generate_report(args, respond):
    respond("Generating Google Groups report is not implemented yet.")


def generate_group_members_report(args, respond):
    """Generate a report of Google Groups members."""
    log = logger.bind(
        operation="generate_group_members_report",
    )
    if not FOLDER_REPORTS_GOOGLE_GROUPS:
        respond("Google Drive folder for reports not set.")
        return
    exclude_groups = ["AWS-"]
    log.info(
        "group_members_report_started",
        group="Google Groups",
    )
    filename = f"groups_report_{datetime.now().strftime('%Y-%m-%d')}"
    log.info("getting_group_file", filename=filename)
    files = google_drive.find_files_by_name(filename, FOLDER_REPORTS_GOOGLE_GROUPS)

    if len(files) == 0:
        log.info("file_not_found_creating_new_file", filename=filename)
        file = google_drive.create_file(filename, FOLDER_REPORTS_GOOGLE_GROUPS, "spreadsheet")
    else:
        file = files[0]
        log.info("file_found", filename=filename, file=file)

    log.info("getting_google_groups")
    directory = get_directory_provider()
    groups_result = directory.list_groups()
    if not groups_result.is_success:
        log.error(
            "list_groups_failed",
            error_code=groups_result.error_code,
            error=groups_result.message,
        )
        raise DirectoryReportError(groups_result.message, groups_result.error_code)
    groups = [group for group in groups_result.data or [] if not any(exclude in (group.name or "") for exclude in exclude_groups)]

    if not groups:
        respond("No groups found.")
        return

    log.info("groups_found", count=len(groups))
    groups_with_members = []
    for group in groups:
        log.info(
            "processing_group",
            group_email=group.group_email,
        )
        members_result = directory.get_group_members(group.group_email)
        if not members_result.is_success:
            log.error(
                "get_group_members_failed",
                group_email=group.group_email,
                error_code=members_result.error_code,
                error=members_result.message,
            )
            raise DirectoryReportError(members_result.message, members_result.error_code)
        groups_with_members.append((group, members_result.data or []))

    for group, members in groups_with_members:
        sheet_title = _sheet_title(group.name or group.group_email)
        log.info("processing_group_sheet", group=sheet_title)

        try:
            sheet = sheets.get_sheet(file["id"], _a1_range(sheet_title))
        except Exception:
            sheet = None
        if sheet:
            log.info("sheet_found", sheet=sheet)
        else:
            try:
                request = {
                    "requests": [
                        {
                            "addSheet": {
                                "properties": {
                                    "title": sheet_title,
                                }
                            }
                        }
                    ]
                }
                sheet = sheets.batch_update(file["id"], request)
                if sheet:
                    log.info("sheet_created", sheet=sheet_title)
            except Exception as e:
                log.error("sheet_creation_failed", error=str(e))

        values = [["Group Name", sheet_title], ["Email", "Role"]]
        for member in members:
            values.append([member.email, member.role or ""])
        updated_sheet = sheets.batch_update_values(
            file["id"],
            _a1_range(sheet_title, "A1"),
            values,
        )
        if updated_sheet:
            log.info("sheet_updated", sheet=sheet_title)

        time.sleep(1.1)

    respond("Google Groups Members report generated.")

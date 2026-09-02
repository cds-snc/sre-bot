"""Characterization tests for the Google Groups members report.

These tests pin the behaviour the module has today, including its rough edges
(blanket excepts, unquoted A1 ranges). They are a change detector, not an
endorsement.

Stub strategy: the vendor modules are patched as bound in the module under test
by a single fixture, and every boundary assertion goes through an accessor
helper so the seam can be moved in one place.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from freezegun import freeze_time

from modules.reports import google_groups

_DIRECTORY = "modules.reports.google_groups.google_directory"
_DRIVE = "modules.reports.google_groups.google_drive"
_SHEETS = "modules.reports.google_groups.sheets"
_SLEEP = "modules.reports.google_groups.time.sleep"

_MSG_FOLDER_UNSET = "Google Drive folder for reports not set."
_MSG_NO_GROUPS = "No groups found."
_MSG_SUCCESS = "Google Groups Members report generated."

_FOLDER_ID = "FOLDER1"
_FILE_ID = "FILE1"


def _member(email: str, role: str) -> dict[str, str]:
    return {"email": email, "role": role}


def _group(name: str, email: str) -> dict[str, str]:
    return {"name": name, "email": email}


def _file_lookup(deps) -> tuple[str, str]:
    """Name and folder id handed to the Drive file lookup."""
    call = deps.drive.find_files_by_name.call_args
    return (call.args[0], call.args[1])


def _file_created(deps) -> list[tuple[str, str, str]]:
    """Filename, folder id and mime kind of every Drive file creation."""
    return [(call.args[0], call.args[1], call.args[2]) for call in deps.drive.create_file.call_args_list]


def _groups_listed(deps) -> int:
    return deps.directory.list_groups.call_count


def _members_requested(deps) -> list[str]:
    """Group keys passed to the Directory member lookup, in call order."""
    return [call.args[0] for call in deps.directory.list_group_members.call_args_list]


def _sheets_read(deps) -> list[tuple[str, str]]:
    """Spreadsheet id and range of every Sheets read."""
    return [(call.args[0], call.args[1]) for call in deps.sheets.get_sheet.call_args_list]


def _sheets_created(deps) -> list[tuple[str, str]]:
    """Spreadsheet id and addSheet title of every sheet creation."""
    return [
        (call.args[0], call.args[1]["requests"][0]["addSheet"]["properties"]["title"])
        for call in deps.sheets.batch_update.call_args_list
    ]


def _sheet_create_requests(deps) -> list[dict]:
    return [call.args[1] for call in deps.sheets.batch_update.call_args_list]


def _sheet_writes(deps) -> list[tuple[str, str, list[list[str]]]]:
    """Spreadsheet id, range and values matrix of every Sheets write."""
    return [(call.args[0], call.args[1], call.args[2]) for call in deps.sheets.batch_update_values.call_args_list]


def _sleep_delays(deps) -> list[float]:
    return [call.args[0] for call in deps.sleep.call_args_list]


@pytest.fixture
def report_deps():
    """Single owner of every patch and default return value for this module."""
    with (
        patch(_DIRECTORY) as directory,
        patch(_DRIVE) as drive,
        patch(_SHEETS) as sheets,
        patch(_SLEEP) as sleep,
        patch.object(google_groups, "FOLDER_REPORTS_GOOGLE_GROUPS", _FOLDER_ID),
    ):
        drive.find_files_by_name.return_value = []
        drive.create_file.return_value = {"id": _FILE_ID}
        directory.list_groups.return_value = [
            _group("GroupOne", "one@test.com"),
            _group("GroupTwo", "two@test.com"),
        ]
        directory.list_group_members.return_value = [
            _member("member1@test.com", "MEMBER"),
            _member("member2@test.com", "OWNER"),
        ]
        # explicit falsy read so the addSheet branch is exercised by default
        sheets.get_sheet.return_value = {}
        sheets.batch_update.return_value = {}
        sheets.batch_update_values.return_value = {}
        yield SimpleNamespace(
            directory=directory,
            drive=drive,
            sheets=sheets,
            sleep=sleep,
            respond=MagicMock(),
        )


@pytest.mark.unit
class TestGenerateGroupMembersReportBehaviour:
    """What the module computes and emits; must survive the adapter migrations."""

    def test_should_respond_and_stop_when_reports_folder_is_unset(self, report_deps):
        with patch.object(google_groups, "FOLDER_REPORTS_GOOGLE_GROUPS", ""):
            google_groups.generate_group_members_report([], report_deps.respond)

        report_deps.respond.assert_called_once_with(_MSG_FOLDER_UNSET)
        assert report_deps.drive.mock_calls == []
        assert report_deps.directory.mock_calls == []
        assert report_deps.sheets.mock_calls == []

    def test_should_respond_with_success_when_report_is_generated(self, report_deps):
        google_groups.generate_group_members_report([], report_deps.respond)

        report_deps.respond.assert_called_once_with(_MSG_SUCCESS)

    def test_should_exclude_groups_whose_name_contains_aws_prefix(self, report_deps):
        report_deps.directory.list_groups.return_value = [
            _group("AWS-Admins", "aws@test.com"),
            _group("GroupOne", "one@test.com"),
        ]

        google_groups.generate_group_members_report([], report_deps.respond)

        assert _members_requested(report_deps) == ["one@test.com"]
        assert [write[1] for write in _sheet_writes(report_deps)] == ["GroupOne!A1"]

    def test_should_respond_no_groups_after_creating_the_file_when_all_groups_excluded(self, report_deps):
        report_deps.directory.list_groups.return_value = [_group("AWS-Admins", "aws@test.com")]

        google_groups.generate_group_members_report([], report_deps.respond)

        report_deps.respond.assert_called_once_with(_MSG_NO_GROUPS)
        assert len(_file_created(report_deps)) == 1
        assert _sheet_writes(report_deps) == []

    def test_should_truncate_sheet_name_to_fifty_characters_in_cell_and_range(self, report_deps):
        long_name = "G" * 60
        report_deps.directory.list_groups.return_value = [_group(long_name, "long@test.com")]

        google_groups.generate_group_members_report([], report_deps.respond)

        truncated = "G" * 50
        _, cell_range, values = _sheet_writes(report_deps)[0]
        assert cell_range == f"{truncated}!A1"
        assert values[0] == ["Group Name", truncated]

    def test_should_write_header_rows_followed_by_members_in_order(self, report_deps):
        report_deps.directory.list_groups.return_value = [_group("GroupOne", "one@test.com")]

        google_groups.generate_group_members_report([], report_deps.respond)

        _, _, values = _sheet_writes(report_deps)[0]
        assert values == [
            ["Group Name", "GroupOne"],
            ["Email", "Role"],
            ["member1@test.com", "MEMBER"],
            ["member2@test.com", "OWNER"],
        ]

    def test_should_pause_once_per_surviving_group(self, report_deps):
        google_groups.generate_group_members_report([], report_deps.respond)

        assert _sleep_delays(report_deps) == [1.1, 1.1]

    def test_should_leave_sheet_names_containing_spaces_unquoted_in_ranges(self, report_deps):
        # Pinned, not endorsed: unquoted A1 ranges are the defect TASK-25.1.6.12 fixes.
        report_deps.directory.list_groups.return_value = [_group("SRE Team", "sre@test.com")]

        google_groups.generate_group_members_report([], report_deps.respond)

        assert _sheets_read(report_deps) == [(_FILE_ID, "SRE Team")]
        assert [write[1] for write in _sheet_writes(report_deps)] == ["SRE Team!A1"]


@pytest.mark.unit
class TestGenerateGroupMembersReportBoundary:
    """Arguments handed to the vendor modules; translated when the seam moves."""

    @freeze_time("2026-05-04")
    def test_should_look_up_a_date_derived_filename_in_the_reports_folder(self, report_deps):
        google_groups.generate_group_members_report([], report_deps.respond)

        assert _file_lookup(report_deps) == ("groups_report_2026-05-04", _FOLDER_ID)

    def test_should_create_a_spreadsheet_when_no_file_is_found(self, report_deps):
        with freeze_time("2026-05-04"):
            google_groups.generate_group_members_report([], report_deps.respond)

        assert _file_created(report_deps) == [("groups_report_2026-05-04", _FOLDER_ID, "spreadsheet")]

    def test_should_reuse_the_existing_file_id_without_creating_a_spreadsheet(self, report_deps):
        report_deps.drive.find_files_by_name.return_value = [{"id": "EXISTING1"}, {"id": "OTHER1"}]

        google_groups.generate_group_members_report([], report_deps.respond)

        assert _file_created(report_deps) == []
        assert {write[0] for write in _sheet_writes(report_deps)} == {"EXISTING1"}
        assert {read[0] for read in _sheets_read(report_deps)} == {"EXISTING1"}

    def test_should_list_groups_once_and_request_members_per_group_email(self, report_deps):
        google_groups.generate_group_members_report([], report_deps.respond)

        assert _groups_listed(report_deps) == 1
        report_deps.directory.list_groups.assert_called_once_with()
        assert _members_requested(report_deps) == ["one@test.com", "two@test.com"]

    def test_should_read_and_create_sheets_with_the_group_sheet_name(self, report_deps):
        report_deps.directory.list_groups.return_value = [_group("GroupOne", "one@test.com")]

        google_groups.generate_group_members_report([], report_deps.respond)

        assert _sheets_read(report_deps) == [(_FILE_ID, "GroupOne")]
        assert _sheet_create_requests(report_deps) == [{"requests": [{"addSheet": {"properties": {"title": "GroupOne"}}}]}]

    def test_should_write_values_positionally_with_file_id_and_range(self, report_deps):
        report_deps.directory.list_groups.return_value = [_group("GroupOne", "one@test.com")]

        google_groups.generate_group_members_report([], report_deps.respond)

        spreadsheet_id, cell_range, values = _sheet_writes(report_deps)[0]
        assert spreadsheet_id == _FILE_ID
        assert cell_range == "GroupOne!A1"
        assert values[1] == ["Email", "Role"]


@pytest.mark.unit
class TestGenerateGroupMembersReportFailureModes:
    """Failure and partial-result behaviour as it stands today."""

    def test_should_swallow_a_failing_sheet_read_and_fall_back_to_creating_the_sheet(self, report_deps):
        report_deps.sheets.get_sheet.side_effect = RuntimeError("boom")

        google_groups.generate_group_members_report([], report_deps.respond)

        assert [created[1] for created in _sheets_created(report_deps)] == ["GroupOne", "GroupTwo"]
        report_deps.respond.assert_called_once_with(_MSG_SUCCESS)

    def test_should_skip_sheet_creation_when_the_sheet_already_exists(self, report_deps):
        report_deps.sheets.get_sheet.return_value = {"sheets": [{"properties": {"title": "GroupOne"}}]}

        google_groups.generate_group_members_report([], report_deps.respond)

        assert _sheets_created(report_deps) == []
        assert len(_sheet_writes(report_deps)) == 2

    def test_should_swallow_a_failing_sheet_creation_and_still_write_values(self, report_deps):
        report_deps.sheets.batch_update.side_effect = RuntimeError("boom")

        google_groups.generate_group_members_report([], report_deps.respond)

        assert len(_sheet_writes(report_deps)) == 2
        report_deps.respond.assert_called_once_with(_MSG_SUCCESS)

    def test_should_propagate_a_failing_drive_lookup_before_any_other_call(self, report_deps):
        report_deps.drive.find_files_by_name.side_effect = RuntimeError("drive down")

        with pytest.raises(RuntimeError):
            google_groups.generate_group_members_report([], report_deps.respond)

        report_deps.respond.assert_not_called()
        assert _file_created(report_deps) == []
        assert _groups_listed(report_deps) == 0
        assert _sheet_writes(report_deps) == []

    def test_should_propagate_a_failing_group_listing_after_the_file_was_created(self, report_deps):
        report_deps.directory.list_groups.side_effect = RuntimeError("directory down")

        with pytest.raises(RuntimeError):
            google_groups.generate_group_members_report([], report_deps.respond)

        assert len(_file_created(report_deps)) == 1
        report_deps.respond.assert_not_called()
        assert _sheet_writes(report_deps) == []

    def test_should_propagate_a_mid_loop_member_failure_before_any_sheet_is_written(self, report_deps):
        report_deps.directory.list_group_members.side_effect = [
            [_member("member1@test.com", "MEMBER")],
            RuntimeError("members down"),
        ]

        with pytest.raises(RuntimeError):
            google_groups.generate_group_members_report([], report_deps.respond)

        assert _members_requested(report_deps) == ["one@test.com", "two@test.com"]
        assert _sheet_writes(report_deps) == []
        report_deps.respond.assert_not_called()

    def test_should_propagate_a_mid_loop_write_failure_leaving_the_first_sheet_written(self, report_deps):
        report_deps.sheets.batch_update_values.side_effect = [{}, RuntimeError("bad range")]

        with pytest.raises(RuntimeError):
            google_groups.generate_group_members_report([], report_deps.respond)

        assert [write[1] for write in _sheet_writes(report_deps)] == ["GroupOne!A1", "GroupTwo!A1"]
        report_deps.respond.assert_not_called()

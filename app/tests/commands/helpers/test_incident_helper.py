from commands.helpers import incident_helper


from unittest.mock import patch


def test_handle_incident_command_with_empty_args():
    assert incident_helper.handle_incident_command([]) == incident_helper.help_text


@patch("commands.helpers.incident_helper.google_drive.create_folder")
def test_handle_incident_command_with_create_command(create_folder_mock):
    create_folder_mock.return_value = "folder created"
    assert (
        incident_helper.handle_incident_command(["create-folder", "foo", "bar"])
        == "folder created"
    )


def test_handle_incident_command_with_help():
    assert (
        incident_helper.handle_incident_command(["help"]) == incident_helper.help_text
    )


@patch("commands.helpers.incident_helper.google_drive.list_folders")
def test_handle_incident_command_with_list_folders(list_folders_mock):
    list_folders_mock.return_value = [{"name": "foo"}, {"name": "bar"}]
    assert incident_helper.handle_incident_command(["list-folders"]) == "foo, bar"


def test_handle_incident_command_with_unknown_command():
    assert (
        incident_helper.handle_incident_command(["foo"])
        == "Unknown command: foo. Type `/sre incident help` to see a list of commands."
    )

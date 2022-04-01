from commands.helpers import incident_helper


from unittest.mock import MagicMock, patch


def test_handle_incident_command_with_empty_args():
    respond = MagicMock()
    incident_helper.handle_incident_command([], MagicMock(), MagicMock(), respond)
    respond.assert_called_once_with(incident_helper.help_text)


@patch("commands.helpers.incident_helper.google_drive.create_folder")
def test_handle_incident_command_with_create_command(create_folder_mock):
    create_folder_mock.return_value = "folder created"
    respond = MagicMock()
    incident_helper.handle_incident_command(
        ["create-folder", "foo", "bar"], MagicMock(), MagicMock(), respond
    )
    respond.assert_called_once_with("folder created")


def test_handle_incident_command_with_help():
    respond = MagicMock()
    incident_helper.handle_incident_command(["help"], MagicMock(), MagicMock(), respond)
    respond.assert_called_once_with(incident_helper.help_text)


@patch("commands.helpers.incident_helper.google_drive.list_folders")
def test_handle_incident_command_with_list_folders(list_folders_mock):
    respond = MagicMock()
    list_folders_mock.return_value = [{"name": "foo"}, {"name": "bar"}]
    incident_helper.handle_incident_command(
        ["list-folders"], MagicMock(), MagicMock(), respond
    )
    respond.assert_called_once_with("foo, bar")


def test_handle_incident_command_with_unknown_command():
    respond = MagicMock()
    incident_helper.handle_incident_command(["foo"], MagicMock(), MagicMock(), respond)
    respond.assert_called_once_with(
        "Unknown command: foo. Type `/sre incident help` to see a list of commands."
    )

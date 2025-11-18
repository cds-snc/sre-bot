from unittest.mock import patch, MagicMock
from modules.incident import on_call


@patch("modules.incident.on_call.get_on_call_users")
@patch("modules.incident.on_call.get_folder_metadata")
def test_get_on_call_user_from_folder(
    mock_get_folder_metadata,
    mock_opsgenie_get_on_call_users,
):
    client = MagicMock()
    folder = "folder_id"
    email = "user@example.com"
    user_info = {
        "ok": True,
        "user": {
            "id": "U12345",
            "name": "testuser",
            "real_name": "Test User",
            "profile": {
                "email": email,
                "real_name": "Test User",
                "display_name": "testuser",
            },
        },
    }
    mock_get_folder_metadata.return_value = {
        "appProperties": {"genie_schedule": "schedule_id"}
    }
    mock_opsgenie_get_on_call_users.return_value = [email]
    client.users_lookupByEmail.return_value = user_info

    result = on_call.get_on_call_users_from_folder(client, folder)

    # Assert that the result is a list with the expected user object
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id"] == "U12345"
    assert result[0]["profile"]["email"] == email


@patch("modules.incident.on_call.get_on_call_users")
@patch("modules.incident.on_call.get_folder_metadata")
def test_get_on_call_user_from_folder_tuple_metadata(
    mock_get_folder_metadata,
    mock_opsgenie_get_on_call_users,
):
    client = MagicMock()
    folder = "folder_id"
    email = "user2@example.com"
    user_info = {
        "ok": True,
        "user": {
            "id": "U67890",
            "name": "testuser2",
            "real_name": "Test User2",
            "profile": {
                "email": email,
                "real_name": "Test User2",
                "display_name": "testuser2",
            },
        },
    }
    # Simulate get_folder_metadata returning a tuple
    mock_get_folder_metadata.return_value = (
        {"appProperties": {"genie_schedule": "schedule_id2"}},
        "extra_value",
    )
    mock_opsgenie_get_on_call_users.return_value = [email]
    client.users_lookupByEmail.return_value = user_info

    result = on_call.get_on_call_users_from_folder(client, folder)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id"] == "U67890"
    assert result[0]["profile"]["email"] == email
    mock_opsgenie_get_on_call_users.assert_called_once_with("schedule_id2")
    client.users_lookupByEmail.assert_called_once_with(email=email)


@patch("modules.incident.on_call.get_on_call_users")
@patch("modules.incident.on_call.get_folder_metadata")
def test_get_on_call_user_from_folder_no_genie_schedule(
    mock_get_folder_metadata,
    mock_opsgenie_get_on_call_users,
):
    client = MagicMock()
    folder = "folder_id"
    # No 'genie_schedule' in appProperties
    mock_get_folder_metadata.return_value = {"appProperties": {}}
    # Should not matter, but set anyway
    mock_opsgenie_get_on_call_users.return_value = []
    client.users_lookupByEmail.return_value = {}

    result = on_call.get_on_call_users_from_folder(client, folder)

    assert isinstance(result, list)
    assert not result
    mock_opsgenie_get_on_call_users.assert_not_called()
    client.users_lookupByEmail.assert_not_called()


@patch("modules.incident.on_call.get_on_call_users")
@patch("modules.incident.on_call.get_folder_metadata")
def test_get_on_call_user_from_folder_any_type(
    mock_get_folder_metadata,
    mock_opsgenie_get_on_call_users,
):
    client = MagicMock()
    folder = "folder_id"
    mock_get_folder_metadata.return_value = "unexpected_string_value"
    mock_opsgenie_get_on_call_users.return_value = []
    client.users_lookupByEmail.return_value = {}

    result = on_call.get_on_call_users_from_folder(client, folder)

    assert isinstance(result, list)
    assert not result
    mock_opsgenie_get_on_call_users.assert_not_called()
    client.users_lookupByEmail.assert_not_called()

from unittest.mock import patch, MagicMock
from modules.incident import db_operations


@patch("modules.incident.db_operations.log_activity")
@patch("modules.incident.db_operations.uuid")
@patch("modules.incident.db_operations.datetime")
@patch("modules.incident.db_operations.dynamodb")
def test_create_incident(mock_dynamodb, mock_datetime, mock_uuid, mock_log_activity):
    mock_uuid.uuid4.return_value = "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"
    mock_created_at = mock_datetime.datetime.now.return_value.timestamp.return_value = (
        1234567890
    )
    mock_dynamodb.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert db_operations.create_incident(
        "channel_id",
        "channel_name",
        "name",
        "user_id",
        ["teams"],
        "report_url",
        meet_url="meet_url",
    )
    mock_dynamodb.put_item.assert_called_once_with(
        TableName="incidents",
        Item={
            "id": {"S": "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"},
            "created_at": {"S": str(mock_created_at)},
            "channel_id": {"S": "channel_id"},
            "channel_name": {"S": "channel_name"},
            "name": {"S": "name"},
            "status": {"S": "Open"},
            "user_id": {"S": "user_id"},
            "teams": {"SS": ["teams"]},
            "report_url": {"S": "report_url"},
            "meet_url": {"S": "meet_url"},
            "environment": {"S": "prod"},
            "logs": {"L": []},
            "incident_updates": {"L": []},
        },
    )
    mock_log_activity.assert_called_once_with(
        "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d",
        "User `user_id` created incident `name` in channel `channel_id`: 978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d",
    )


@patch("modules.incident.db_operations.log_activity")
@patch("modules.incident.db_operations.uuid")
@patch("modules.incident.db_operations.datetime")
@patch("modules.incident.db_operations.dynamodb")
def test_create_incident_with_optional_args(
    mock_dynamodb, mock_datetime, mock_uuid, mock_log_activity
):
    mock_uuid.uuid4.return_value = "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"
    mock_created_at = mock_datetime.datetime.now.return_value.timestamp.return_value = (
        1234567890
    )
    mock_dynamodb.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert db_operations.create_incident(
        "channel_id",
        "channel_name",
        "name",
        "user_id",
        ["teams"],
        "report_url",
        meet_url="meet_url",
        incident_commander="incident_commander",
        operations_lead="operations_lead",
        severity="severity",
        start_impact_time="start_time",
        end_impact_time="end_time",
        detection_time="detection_time",
        retrospective_url="retro_url",
        environment="dev",
    )
    mock_dynamodb.put_item.assert_called_once_with(
        TableName="incidents",
        Item={
            "id": {"S": "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"},
            "created_at": {"S": str(mock_created_at)},
            "channel_id": {"S": "channel_id"},
            "channel_name": {"S": "channel_name"},
            "name": {"S": "name"},
            "status": {"S": "Open"},
            "user_id": {"S": "user_id"},
            "teams": {"SS": ["teams"]},
            "report_url": {"S": "report_url"},
            "meet_url": {"S": "meet_url"},
            "environment": {"S": "dev"},
            "incident_commander": {"S": "incident_commander"},
            "operations_lead": {"S": "operations_lead"},
            "severity": {"S": "severity"},
            "start_impact_time": {"S": "start_time"},
            "end_impact_time": {"S": "end_time"},
            "detection_time": {"S": "detection_time"},
            "retrospective_url": {"S": "retro_url"},
            "logs": {"L": []},
            "incident_updates": {"L": []},
        },
    )
    mock_log_activity.assert_called_once_with(
        "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d",
        "User `user_id` created incident `name` in channel `channel_id`: 978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d",
    )


@patch("modules.incident.db_operations.log_activity")
@patch("modules.incident.db_operations.uuid")
@patch("modules.incident.db_operations.datetime")
@patch("modules.incident.db_operations.dynamodb")
def test_create_incident_handle_error(
    mock_dynamodb, mock_datetime, mock_uuid, mock_log_activity
):
    mock_uuid.uuid4.return_value = "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"
    mock_created_at = mock_datetime.datetime.now.return_value.timestamp.return_value = (
        1234567890
    )
    mock_dynamodb.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 400}}
    response = db_operations.create_incident(
        "channel_id",
        "channel_name",
        "name",
        "user_id",
        ["teams"],
        "report_url",
        meet_url="meet_url",
    )
    assert response is None
    mock_dynamodb.put_item.assert_called_once_with(
        TableName="incidents",
        Item={
            "id": {"S": "978f1d91-f2b4-4ad2-9f2f-86c0f1fce72d"},
            "created_at": {"S": str(mock_created_at)},
            "channel_id": {"S": "channel_id"},
            "channel_name": {"S": "channel_name"},
            "name": {"S": "name"},
            "status": {"S": "Open"},
            "user_id": {"S": "user_id"},
            "teams": {"SS": ["teams"]},
            "report_url": {"S": "report_url"},
            "meet_url": {"S": "meet_url"},
            "environment": {"S": "prod"},
            "logs": {"L": []},
            "incident_updates": {"L": []},
        },
    )
    mock_log_activity.assert_not_called()


@patch("modules.incident.db_operations.dynamodb")
def test_list_incidents(
    mock_dynamodb,
):
    mock_dynamodb.scan.return_value = [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
            "user_id": {"S": "qux"},
            "teams": {"SS": ["quux"]},
            "report_url": {"S": "corge"},
            "meet_url": {"S": "grault"},
            "status": {"S": "garply"},
            "start_impact_time": {"S": "waldo"},
            "end_impact_time": {"S": "fred"},
            "environment": {"S": "plugh"},
            "retrospective_url": {"S": "xyzzy"},
        }
    ]
    assert db_operations.list_incidents() == [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
            "user_id": {"S": "qux"},
            "teams": {"SS": ["quux"]},
            "report_url": {"S": "corge"},
            "meet_url": {"S": "grault"},
            "status": {"S": "garply"},
            "start_impact_time": {"S": "waldo"},
            "end_impact_time": {"S": "fred"},
            "environment": {"S": "plugh"},
            "retrospective_url": {"S": "xyzzy"},
        }
    ]


@patch("modules.incident.db_operations.dynamodb")
def test_list_incidents_empty(
    mock_dynamodb,
):
    mock_dynamodb.scan.return_value = []
    assert db_operations.list_incidents() == []


@patch("modules.incident.db_operations.log_activity")
@patch("modules.incident.db_operations.dynamodb")
def test_update_incident_field(mock_dynamodb, mock_log_activity):
    mock_logger = MagicMock()
    mock_dynamodb.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    assert db_operations.update_incident_field(
        mock_logger, "foo", "bar", "baz", "user_id"
    )
    mock_dynamodb.update_item.assert_called_once_with(
        TableName="incidents",
        Key={"id": {"S": "foo"}},
        UpdateExpression="SET #bar = :bar",
        ExpressionAttributeNames={"#bar": "bar"},
        ExpressionAttributeValues={":bar": {"S": "baz"}},
    )
    mock_log_activity.assert_called_once_with(
        "foo", "field `bar` updated to `baz` by user: user_id"
    )


@patch("modules.incident.db_operations.log_activity")
@patch("modules.incident.db_operations.dynamodb")
def test_update_incident_field_with_type(mock_dynamodb, mock_log_activity):
    mock_logger = MagicMock()
    mock_dynamodb.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    assert db_operations.update_incident_field(
        mock_logger, "foo", "bar", "baz", "user_id", "M"
    )
    mock_dynamodb.update_item.assert_called_once_with(
        TableName="incidents",
        Key={"id": {"S": "foo"}},
        UpdateExpression="SET #bar = :bar",
        ExpressionAttributeNames={"#bar": "bar"},
        ExpressionAttributeValues={":bar": {"M": "baz"}},
    )
    mock_log_activity.assert_called_once_with(
        "foo", "field `bar` updated to `baz` by user: user_id"
    )


@patch("modules.incident.db_operations.dynamodb")
def test_update_incident_field_handles_failure(mock_dynamodb):
    mock_logger = MagicMock()
    mock_dynamodb.update_item.return_value = None
    response = db_operations.update_incident_field(
        mock_logger, "foo", "bar", "baz", "user_id"
    )
    assert response is None


@patch("modules.incident.db_operations.dynamodb")
def test_get_incident(mock_dynamodb):
    mock_dynamodb.get_item.return_value = {
        "id": {"S": "foo"},
        "channel_id": {"S": "bar"},
        "channel_name": {"S": "baz"},
        "user_id": {"S": "qux"},
        "teams": {"SS": ["quux"]},
        "report_url": {"S": "corge"},
        "meet_url": {"S": "grault"},
        "status": {"S": "garply"},
        "start_impact_time": {"S": "waldo"},
        "end_impact_time": {"S": "fred"},
        "environment": {"S": "plugh"},
        "retrospective_url": {"S": "xyzzy"},
    }

    assert db_operations.get_incident("foo") == {
        "id": {"S": "foo"},
        "channel_id": {"S": "bar"},
        "channel_name": {"S": "baz"},
        "user_id": {"S": "qux"},
        "teams": {"SS": ["quux"]},
        "report_url": {"S": "corge"},
        "meet_url": {"S": "grault"},
        "status": {"S": "garply"},
        "start_impact_time": {"S": "waldo"},
        "end_impact_time": {"S": "fred"},
        "environment": {"S": "plugh"},
        "retrospective_url": {"S": "xyzzy"},
    }


@patch("modules.incident.db_operations.lookup_incident")
def test_get_incident_by_channel_id(mock_lookup_incident):
    mock_lookup_incident.return_value = [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
            "user_id": {"S": "qux"},
            "teams": {"SS": ["quux"]},
            "report_url": {"S": "corge"},
            "meet_url": {"S": "grault"},
            "status": {"S": "garply"},
            "start_impact_time": {"S": "waldo"},
            "end_impact_time": {"S": "fred"},
            "environment": {"S": "plugh"},
            "retrospective_url": {"S": "xyzzy"},
        }
    ]

    assert db_operations.get_incident_by_channel_id("bar") == {
        "id": {"S": "foo"},
        "channel_id": {"S": "bar"},
        "channel_name": {"S": "baz"},
        "user_id": {"S": "qux"},
        "teams": {"SS": ["quux"]},
        "report_url": {"S": "corge"},
        "meet_url": {"S": "grault"},
        "status": {"S": "garply"},
        "start_impact_time": {"S": "waldo"},
        "end_impact_time": {"S": "fred"},
        "environment": {"S": "plugh"},
        "retrospective_url": {"S": "xyzzy"},
    }
    mock_lookup_incident.assert_called_once_with("channel_id", "bar")


@patch("modules.incident.db_operations.lookup_incident")
def test_get_incident_by_channel_id_multiple_results(mock_lookup_incident):
    mock_lookup_incident.return_value = [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
        },
        {
            "id": {"S": "qux"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "quux"},
        },
    ]

    assert db_operations.get_incident_by_channel_id("bar") == {
        "id": {"S": "foo"},
        "channel_id": {"S": "bar"},
        "channel_name": {"S": "baz"},
    }

    mock_lookup_incident.assert_called_once_with("channel_id", "bar")


@patch("modules.incident.db_operations.lookup_incident")
def test_get_incident_by_channel_id_no_results(mock_lookup_incident):
    mock_lookup_incident.return_value = []

    assert db_operations.get_incident_by_channel_id("bar") is None

    mock_lookup_incident.assert_called_once_with("channel_id", "bar")


@patch("modules.incident.db_operations.dynamodb")
def test_lookup_incident(
    mock_dynamodb,
):
    incidents = [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
            "user_id": {"S": "qux"},
            "teams": {"SS": ["quux"]},
            "report_url": {"S": "corge"},
            "meet_url": {"S": "grault"},
            "status": {"S": "garply"},
            "start_impact_time": {"S": "waldo"},
            "end_impact_time": {"S": "fred"},
            "environment": {"S": "plugh"},
            "retrospective_url": {"S": "xyzzy"},
        },
    ]
    mock_dynamodb.scan.return_value = incidents
    assert db_operations.lookup_incident("channel_id", "bar") == [
        {
            "id": {"S": "foo"},
            "channel_id": {"S": "bar"},
            "channel_name": {"S": "baz"},
            "user_id": {"S": "qux"},
            "teams": {"SS": ["quux"]},
            "report_url": {"S": "corge"},
            "meet_url": {"S": "grault"},
            "status": {"S": "garply"},
            "start_impact_time": {"S": "waldo"},
            "end_impact_time": {"S": "fred"},
            "environment": {"S": "plugh"},
            "retrospective_url": {"S": "xyzzy"},
        }
    ]

    mock_dynamodb.scan.assert_called_once_with(
        TableName="incidents",
        FilterExpression="channel_id = :channel_id",
        ExpressionAttributeValues={":channel_id": {"S": "bar"}},
    )

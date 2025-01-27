from unittest.mock import ANY, patch

from modules.slack import webhooks


@patch("modules.slack.webhooks.dynamodb")
def test_create_webhook(dynamodb_mock):
    dynamodb_mock.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert webhooks.create_webhook("test_channel", "test_user_id", "test_name") == ANY
    dynamodb_mock.put_item.assert_called_once_with(
        TableName="webhooks",
        Item={
            "id": {"S": ANY},
            "channel": {"S": "test_channel"},
            "name": {"S": "test_name"},
            "created_at": {"S": ANY},
            "active": {"BOOL": True},
            "user_id": {"S": "test_user_id"},
            "invocation_count": {"N": "0"},
            "acknowledged_count": {"N": "0"},
        },
    )


@patch("modules.slack.webhooks.dynamodb")
def test_create_webhook_return_none(dynamodb_mock):
    dynamodb_mock.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 401}}
    assert webhooks.create_webhook("test_channel", "test_user_id", "test_name") is None
    dynamodb_mock.put_item.assert_called_once_with(
        TableName="webhooks",
        Item={
            "id": {"S": ANY},
            "channel": {"S": "test_channel"},
            "name": {"S": "test_name"},
            "created_at": {"S": ANY},
            "active": {"BOOL": True},
            "user_id": {"S": "test_user_id"},
            "invocation_count": {"N": "0"},
            "acknowledged_count": {"N": "0"},
        },
    )


@patch("modules.slack.webhooks.dynamodb")
def test_delete_webhook(dynamodb_mock):
    dynamodb_mock.delete_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    assert webhooks.delete_webhook("test_id") == {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    dynamodb_mock.delete_item.assert_called_once_with(
        TableName="webhooks", Key={"id": {"S": "test_id"}}
    )


@patch("modules.slack.webhooks.dynamodb")
def test_get_webhook(dynamodb_mock):
    dynamodb_mock.get_item.return_value = {
        "id": {"S": "test_id"},
        "channel": {"S": "test_channel"},
        "name": {"S": "test_name"},
        "created_at": {"S": "test_created_at"},
        "active": {"BOOL": True},
        "user_id": {"S": "test_user_id"},
        "invocation_count": {"N": "0"},
        "acknowledged_count": {"N": "0"},
    }
    assert webhooks.get_webhook("test_id") == {
        "id": {"S": "test_id"},
        "channel": {"S": "test_channel"},
        "name": {"S": "test_name"},
        "created_at": {"S": "test_created_at"},
        "active": {"BOOL": True},
        "user_id": {"S": "test_user_id"},
        "invocation_count": {"N": "0"},
        "acknowledged_count": {"N": "0"},
    }
    dynamodb_mock.get_item.assert_called_once_with(
        TableName="webhooks", Key={"id": {"S": "test_id"}}
    )


@patch("modules.slack.webhooks.dynamodb")
def test_get_webhook_with_no_result(dynamodb_mock):
    dynamodb_mock.get_item.return_value = {}
    assert webhooks.get_webhook("test_id") is None
    dynamodb_mock.get_item.assert_called_once_with(
        TableName="webhooks", Key={"id": {"S": "test_id"}}
    )


@patch("modules.slack.webhooks.dynamodb")
def test_increment_acknowledged_count(dynamodb_mock):
    dynamodb_mock.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    assert webhooks.increment_acknowledged_count("test_id") == {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    dynamodb_mock.update_item.assert_called_once_with(
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression="SET acknowledged_count = acknowledged_count + :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}},
    )


@patch("modules.slack.webhooks.dynamodb")
def test_increment_invocation_count(dynamodb_mock):
    dynamodb_mock.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    assert webhooks.increment_invocation_count("test_id") == {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    dynamodb_mock.update_item.assert_called_once_with(
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression="SET invocation_count = invocation_count + :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}},
    )


@patch("modules.slack.webhooks.dynamodb")
def test_list_all_webhooks(dynamodb_mock):
    dynamodb_mock.scan.return_value = [
        {
            "id": {"S": "test_id"},
            "channel": {"S": "test_channel"},
            "name": {"S": "test_name"},
            "created_at": {"S": "test_created_at"},
            "active": {"BOOL": True},
            "user_id": {"S": "test_user_id"},
            "invocation_count": {"N": "0"},
            "acknowledged_count": {"N": "0"},
        }
    ]
    assert webhooks.list_all_webhooks() == [
        {
            "id": {"S": "test_id"},
            "channel": {"S": "test_channel"},
            "name": {"S": "test_name"},
            "created_at": {"S": "test_created_at"},
            "active": {"BOOL": True},
            "user_id": {"S": "test_user_id"},
            "invocation_count": {"N": "0"},
            "acknowledged_count": {"N": "0"},
        }
    ]
    dynamodb_mock.scan.assert_called_once_with(
        TableName="webhooks", Select="ALL_ATTRIBUTES"
    )


@patch("modules.slack.webhooks.dynamodb")
def test_revoke_webhook(dynamodb_mock):
    dynamodb_mock.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    assert webhooks.revoke_webhook("test_id") == {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    dynamodb_mock.update_item.assert_called_once_with(
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression="SET active = :active",
        ExpressionAttributeValues={":active": {"BOOL": False}},
    )


@patch("modules.slack.webhooks.dynamodb")
def test_is_active_returns_true(dynamodb_mock):
    dynamodb_mock.get_item.return_value = {
        "id": {"S": "test_id"},
        "channel": {"S": "test_channel"},
        "name": {"S": "test_name"},
        "created_at": {"S": "test_created_at"},
        "active": {"BOOL": True},
        "user_id": {"S": "test_user_id"},
        "invocation_count": {"N": "0"},
        "acknowledged_count": {"N": "0"},
    }
    assert webhooks.is_active("test_id") is True


@patch("modules.slack.webhooks.dynamodb")
def test_is_active_returns_false(dynamodb_mock):
    dynamodb_mock.get_item.return_value = {
        "id": {"S": "test_id"},
        "channel": {"S": "test_channel"},
        "name": {"S": "test_name"},
        "created_at": {"S": "test_created_at"},
        "active": {"BOOL": False},
        "user_id": {"S": "test_user_id"},
        "invocation_count": {"N": "0"},
        "acknowledged_count": {"N": "0"},
    }
    assert webhooks.is_active("test_id") is False


@patch("modules.slack.webhooks.dynamodb")
def test_is_active_not_found(dynamodb_mock):
    dynamodb_mock.get_item.return_value = {}
    assert webhooks.is_active("test_id") is False


@patch("modules.slack.webhooks.dynamodb")
@patch("modules.slack.webhooks.get_webhook")
def test_toggle_webhook(get_webhook_mock, dynamodb_mock):
    dynamodb_mock.update_item.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    get_webhook_mock.return_value = {
        "id": {"S": "test_id"},
        "channel": {"S": "test_channel"},
        "name": {"S": "test_name"},
        "created_at": {"S": "test_created_at"},
        "active": {"BOOL": True},
        "user_id": {"S": "test_user_id"},
        "invocation_count": {"N": "0"},
        "acknowledged_count": {"N": "0"},
    }
    assert webhooks.toggle_webhook("test_id") == {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    dynamodb_mock.update_item.assert_called_once_with(
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression="SET active = :active",
        ExpressionAttributeValues={":active": {"BOOL": ANY}},
    )


@patch("modules.slack.webhooks.model_utils")
def test_validate_string_payload_type_valid_json(
    model_utils_mock,
):
    model_utils_mock.get_dict_of_parameters_from_models.return_value = {
        "WrongModel": ["test"],
        "TestModel": ["type"],
        "TestModel2": ["type2"],
    }
    model_utils_mock.has_parameters_in_model.side_effect = [0, 1, 0]
    assert webhooks.validate_string_payload_type('{"type": "test"}') == (
        "TestModel",
        {"type": "test"},
    )
    assert model_utils_mock.has_parameters_in_model.call_count == 3


@patch("modules.slack.webhooks.model_utils")
def test_validate_string_payload_same_params_in_multiple_models_returns_first_found(
    model_utils_mock, caplog
):
    model_utils_mock.get_dict_of_parameters_from_models.return_value = {
        "WrongModel": ["test"],
        "TestModel": ["type", "type2"],
        "TestModel2": ["type2"],
        "TestModel3": ["type"],
    }
    model_utils_mock.has_parameters_in_model.side_effect = [0, 2, 0, 1]
    response = webhooks.validate_string_payload_type(
        '{"type": "test", "type2": "test"}'
    )
    assert response == (
        "TestModel",
        {"type": "test", "type2": "test"},
    )
    assert response != (
        "TestModel3",
        {"type": "test"},
    )
    assert model_utils_mock.has_parameters_in_model.call_count == 4


def test_validate_string_payload_type_error_loading_json(caplog):
    with caplog.at_level("WARNING"):
        assert webhooks.validate_string_payload_type("{") == (None, None)
    assert "Invalid JSON payload" in caplog.text


def test_validate_string_payload_type_unknown_payload_type(caplog):
    with caplog.at_level("WARNING"):
        assert webhooks.validate_string_payload_type('{"type": "unknown"}') == (
            None,
            None,
        )
    warning_message = 'Unknown type for payload: {"type": "unknown"}'
    assert warning_message in caplog.text

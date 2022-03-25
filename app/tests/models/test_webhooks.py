from unittest.mock import ANY, patch

from models import webhooks


@patch("models.webhooks.client")
def test_create_webhook(client_mock):
    client_mock.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert webhooks.create_webhook("test_channel", "test_user_id", "test_name") == ANY
    client_mock.put_item.assert_called_once_with(
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


@patch("models.webhooks.client")
def test_create_webhook_return_none(client_mock):
    client_mock.put_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 401}}
    assert webhooks.create_webhook("test_channel", "test_user_id", "test_name") is None
    client_mock.put_item.assert_called_once_with(
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


@patch("models.webhooks.client")
def test_delete_webhook(client_mock):
    client_mock.delete_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert webhooks.delete_webhook("test_id") == {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    client_mock.delete_item.assert_called_once_with(
        TableName="webhooks", Key={"id": {"S": "test_id"}}
    )


@patch("models.webhooks.client")
def test_get_webhook(client_mock):
    client_mock.get_item.return_value = {
        "Item": {
            "id": {"S": "test_id"},
            "channel": {"S": "test_channel"},
            "name": {"S": "test_name"},
            "created_at": {"S": "test_created_at"},
            "active": {"BOOL": True},
            "user_id": {"S": "test_user_id"},
            "invocation_count": {"N": "0"},
            "acknowledged_count": {"N": "0"},
        }
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
    client_mock.get_item.assert_called_once_with(
        TableName="webhooks", Key={"id": {"S": "test_id"}}
    )


@patch("models.webhooks.client")
def test_get_webhook_with_no_result(client_mock):
    client_mock.get_item.return_value = {}
    assert webhooks.get_webhook("test_id") is None
    client_mock.get_item.assert_called_once_with(
        TableName="webhooks", Key={"id": {"S": "test_id"}}
    )


@patch("models.webhooks.client")
def test_increment_acknowledged_count(client_mock):
    client_mock.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert webhooks.increment_acknowledged_count("test_id") == {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    client_mock.update_item.assert_called_once_with(
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression="SET acknowledged_count = acknowledged_count + :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}},
    )


@patch("models.webhooks.client")
def test_increment_invocation_count(client_mock):
    client_mock.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert webhooks.increment_invocation_count("test_id") == {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    client_mock.update_item.assert_called_once_with(
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression="SET invocation_count = invocation_count + :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}},
    )


@patch("models.webhooks.client")
def test_list_all_webhooks(client_mock):
    client_mock.scan.return_value = {
        "Items": [
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
    }
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
    client_mock.scan.assert_called_once_with(
        TableName="webhooks", Select="ALL_ATTRIBUTES"
    )


@patch("models.webhooks.client")
def test_revoke_webhook(client_mock):
    client_mock.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
    assert webhooks.revoke_webhook("test_id") == {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    client_mock.update_item.assert_called_once_with(
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression="SET active = :active",
        ExpressionAttributeValues={":active": {"BOOL": False}},
    )


@patch("models.webhooks.client")
@patch("models.webhooks.get_webhook")
def test_toggle_webhook(get_webhook_mock, client_mock):
    client_mock.update_item.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
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
    client_mock.update_item.assert_called_once_with(
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression="SET active = :active",
        ExpressionAttributeValues={":active": {"BOOL": ANY}},
    )

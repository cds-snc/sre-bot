"""Behaviour of the webhooks persistence helpers over the DynamoDB adapter.

The adapter is replaced with ``MagicMock(spec=DynamoDBAdapter)`` returned from a
patched ``build_dynamodb_adapter``; each method returns an ``OperationResult``
so the helpers' branching on success, absence and failure is exercised without
botocore. Log assertions patch the module logger.
"""

from typing import Any
from unittest.mock import ANY, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from infrastructure.operations import OperationResult, OperationStatus
from modules.slack import webhooks
from packages.aws_platform.adapters.dynamodb import DynamoDBAdapter

WEBHOOK_ITEM: dict[str, Any] = {
    "id": {"S": "test_id"},
    "channel": {"S": "test_channel"},
    "name": {"S": "test_name"},
    "created_at": {"S": "test_created_at"},
    "active": {"BOOL": True},
    "user_id": {"S": "test_user_id"},
    "invocation_count": {"N": "0"},
    "acknowledged_count": {"N": "0"},
    "hook_type": {"S": "alert"},
}


def _failure() -> OperationResult[Any]:
    return OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="boom",
        error_code="ThrottlingException",
    )


FAILURE_FIELDS = {
    "status": OperationStatus.TRANSIENT_ERROR.value,
    "error_code": "ThrottlingException",
    "error": "boom",
}


def _unclassified_client_error(operation: str) -> ClientError:
    """Build a ClientError whose code sits outside every adapter classification catalogue."""
    return ClientError({"Error": {"Code": "ValidationException", "Message": "missing attribute"}}, operation)


UNCLASSIFIED_FIELDS = {
    "status": "unclassified",
    "error_code": "ValidationException",
    "error": "missing attribute",
}


def _assert_unclassified_unavailable(error: Exception) -> None:
    """Assert the raised store error classifies an unmapped SDK code as permanent with no provider text."""
    assert isinstance(error, webhooks.WebhookStoreUnavailableError)
    assert error.status is OperationStatus.PERMANENT_ERROR
    assert error.error_code == "ValidationException"
    assert error.retry_after is None
    assert "missing attribute" not in str(error)


@pytest.fixture
def adapter():
    """Patch the module's adapter factory with a spec'd mock and yield the mock."""
    mock = MagicMock(spec=DynamoDBAdapter)
    with patch("modules.slack.webhooks.build_dynamodb_adapter", return_value=mock) as factory:
        mock.factory = factory
        yield mock


@pytest.fixture
def logger_mock():
    with patch("modules.slack.webhooks.logger") as mock:
        yield mock


def _expected_item(hook_type: str) -> dict[str, Any]:
    return {
        "id": {"S": ANY},
        "channel": {"S": "test_channel"},
        "name": {"S": "test_name"},
        "created_at": {"S": ANY},
        "active": {"BOOL": True},
        "user_id": {"S": "test_user_id"},
        "invocation_count": {"N": "0"},
        "acknowledged_count": {"N": "0"},
        "hook_type": {"S": hook_type},
    }


# -- create_webhook -------------------------------------------------------------


def test_create_webhook_returns_id_on_success(adapter):
    """A successful put returns the generated id that was written as the item key."""
    adapter.put_item.return_value = OperationResult.success()

    webhook_id = webhooks.create_webhook("test_channel", "test_user_id", "test_name")

    adapter.put_item.assert_called_once_with(TableName="webhooks", Item=_expected_item("alert"))
    assert isinstance(webhook_id, str)
    assert adapter.put_item.call_args.kwargs["Item"]["id"] == {"S": webhook_id}


def test_create_webhook_with_type(adapter):
    """The hook_type argument is persisted on the item."""
    adapter.put_item.return_value = OperationResult.success()

    webhooks.create_webhook("test_channel", "test_user_id", "test_name", "info")

    adapter.put_item.assert_called_once_with(TableName="webhooks", Item=_expected_item("info"))


def test_create_webhook_returns_none_and_logs_on_failure(adapter, logger_mock):
    """A failed put keeps the existing failure contract (None) and logs the classified failure."""
    adapter.put_item.return_value = _failure()

    assert webhooks.create_webhook("test_channel", "test_user_id", "test_name") is None
    logger_mock.error.assert_called_once_with("webhook_create_failed", **FAILURE_FIELDS)


def test_create_webhook_returns_none_and_logs_on_unclassified_client_error(adapter, logger_mock):
    """An SDK error the adapter does not classify follows the classified failure contract.

    The adapter mock raises a ClientError with a code outside every classification
    catalogue, as the adapter re-raises it in production. The helper returns None,
    which the create flow already reports to the user, and logs the raw code.
    """
    adapter.put_item.side_effect = _unclassified_client_error("PutItem")

    assert webhooks.create_webhook("test_channel", "test_user_id", "test_name") is None
    logger_mock.error.assert_called_once_with("webhook_create_failed", **UNCLASSIFIED_FIELDS)


# -- get_webhook ----------------------------------------------------------------


def test_get_webhook_returns_item(adapter):
    """A found item is returned in its AttributeValue shape."""
    adapter.get_item.return_value = OperationResult.success(data=WEBHOOK_ITEM)

    assert webhooks.get_webhook("test_id") == WEBHOOK_ITEM
    adapter.get_item.assert_called_once_with(TableName="webhooks", Key={"id": {"S": "test_id"}})


def test_get_webhook_returns_none_when_absent(adapter):
    """An absent item is a success with no data, so the helper keeps returning None."""
    adapter.get_item.return_value = OperationResult.success(data=None)

    assert webhooks.get_webhook("test_id") is None


def test_get_webhook_raises_and_logs_on_failure(adapter, logger_mock):
    """A failed read raises so it is never mistaken for a missing webhook.

    The raised error carries the classification callers map to a response (status,
    error code, retry delay) while its message stays generic, without provider text.
    """
    adapter.get_item.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="boom",
        error_code="ThrottlingException",
        retry_after=5,
    )

    with pytest.raises(webhooks.WebhookStoreUnavailableError) as exc_info:
        webhooks.get_webhook("test_id")

    assert exc_info.value.status is OperationStatus.TRANSIENT_ERROR
    assert exc_info.value.error_code == "ThrottlingException"
    assert exc_info.value.retry_after == 5
    assert "boom" not in str(exc_info.value)
    logger_mock.error.assert_called_once_with("webhook_get_failed", webhook_id="test_id", **FAILURE_FIELDS)


def test_get_webhook_raises_and_logs_on_unclassified_client_error(adapter, logger_mock):
    """An SDK error the adapter does not classify surfaces as the store-unavailable error.

    The adapter mock raises a ClientError with a code outside every classification
    catalogue. Callers only catch the store-unavailable error, so the unmapped case
    must reach them in that shape: permanent, carrying the code, no retry delay and
    no provider text in the message.
    """
    adapter.get_item.side_effect = _unclassified_client_error("GetItem")

    with pytest.raises(webhooks.WebhookStoreUnavailableError) as exc_info:
        webhooks.get_webhook("test_id")

    _assert_unclassified_unavailable(exc_info.value)
    assert isinstance(exc_info.value.__cause__, ClientError)
    logger_mock.error.assert_called_once_with("webhook_get_failed", webhook_id="test_id", **UNCLASSIFIED_FIELDS)


# -- lookup_webhooks ------------------------------------------------------------


def test_lookup_webhooks_returns_items(adapter):
    """The scan filters on the field with a string AttributeValue and returns every item."""
    adapter.scan.return_value = OperationResult.success(data=[WEBHOOK_ITEM, WEBHOOK_ITEM])

    assert webhooks.lookup_webhooks("channel", "test_channel") == [WEBHOOK_ITEM, WEBHOOK_ITEM]
    adapter.scan.assert_called_once_with(
        TableName="webhooks",
        FilterExpression="channel = :channel",
        ExpressionAttributeValues={":channel": {"S": "test_channel"}},
    )


def test_lookup_webhooks_returns_empty_list(adapter):
    """An empty scan stays an empty list."""
    adapter.scan.return_value = OperationResult.success(data=[])

    assert webhooks.lookup_webhooks("channel", "test_channel") == []


def test_lookup_webhooks_raises_and_logs_on_failure(adapter, logger_mock):
    """A failed scan raises instead of passing as "no webhooks"."""
    adapter.scan.return_value = _failure()

    with pytest.raises(webhooks.WebhookStoreUnavailableError):
        webhooks.lookup_webhooks("channel", "test_channel")

    logger_mock.error.assert_called_once_with("webhook_lookup_failed", field="channel", **FAILURE_FIELDS)


def test_lookup_webhooks_raises_and_logs_on_unclassified_client_error(adapter, logger_mock):
    """An unclassified SDK error on the filtered scan raises the store-unavailable error and is logged."""
    adapter.scan.side_effect = _unclassified_client_error("Scan")

    with pytest.raises(webhooks.WebhookStoreUnavailableError) as exc_info:
        webhooks.lookup_webhooks("channel", "test_channel")

    _assert_unclassified_unavailable(exc_info.value)
    logger_mock.error.assert_called_once_with("webhook_lookup_failed", field="channel", **UNCLASSIFIED_FIELDS)


# -- list_all_webhooks ----------------------------------------------------------


def test_list_all_webhooks_returns_items(adapter):
    """The full-table scan returns every item."""
    adapter.scan.return_value = OperationResult.success(data=[WEBHOOK_ITEM])

    assert webhooks.list_all_webhooks() == [WEBHOOK_ITEM]
    adapter.scan.assert_called_once_with(TableName="webhooks", Select="ALL_ATTRIBUTES")


def test_list_all_webhooks_returns_empty_list(adapter):
    """An empty table stays an empty list."""
    adapter.scan.return_value = OperationResult.success(data=[])

    assert webhooks.list_all_webhooks() == []


def test_list_all_webhooks_raises_and_logs_on_failure(adapter, logger_mock):
    """A failed scan raises instead of passing as an empty table."""
    adapter.scan.return_value = _failure()

    with pytest.raises(webhooks.WebhookStoreUnavailableError):
        webhooks.list_all_webhooks()

    logger_mock.error.assert_called_once_with("webhook_list_failed", **FAILURE_FIELDS)


def test_list_all_webhooks_raises_and_logs_on_unclassified_client_error(adapter, logger_mock):
    """An unclassified SDK error on the full-table scan raises the store-unavailable error and is logged."""
    adapter.scan.side_effect = _unclassified_client_error("Scan")

    with pytest.raises(webhooks.WebhookStoreUnavailableError) as exc_info:
        webhooks.list_all_webhooks()

    _assert_unclassified_unavailable(exc_info.value)
    logger_mock.error.assert_called_once_with("webhook_list_failed", **UNCLASSIFIED_FIELDS)


# -- counters -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("helper", "attribute"),
    [
        (webhooks.increment_acknowledged_count, "acknowledged_count"),
        (webhooks.increment_invocation_count, "invocation_count"),
    ],
)
def test_increment_count_sends_without_retries(adapter, helper, attribute):
    """Counter increments are not replay-safe, so they go to the retries-disabled client.

    The expression seeds a missing counter at zero in the same atomic write, so items
    stored without the attribute are counted instead of rejected by DynamoDB.
    """
    adapter.update_item.return_value = OperationResult.success()

    assert helper("test_id") is None
    adapter.update_item.assert_called_once_with(
        retries=False,
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression=f"SET {attribute} = if_not_exists({attribute}, :zero) + :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}, ":zero": {"N": "0"}},
    )


@pytest.mark.parametrize(
    ("helper", "event"),
    [
        (webhooks.increment_acknowledged_count, "webhook_acknowledged_count_increment_failed"),
        (webhooks.increment_invocation_count, "webhook_invocation_count_increment_failed"),
    ],
)
def test_increment_count_logs_and_returns_none_on_failure(adapter, logger_mock, helper, event):
    """A failed increment is logged and dropped so it never blocks webhook delivery."""
    adapter.update_item.return_value = _failure()

    assert helper("test_id") is None
    logger_mock.error.assert_called_once_with(event, webhook_id="test_id", **FAILURE_FIELDS)


@pytest.mark.parametrize(
    ("helper", "event"),
    [
        (webhooks.increment_acknowledged_count, "webhook_acknowledged_count_increment_failed"),
        (webhooks.increment_invocation_count, "webhook_invocation_count_increment_failed"),
    ],
)
def test_increment_count_logs_and_returns_none_on_unclassified_client_error(adapter, logger_mock, helper, event):
    """An SDK error the adapter does not classify is still logged and dropped for counters.

    The adapter mock raises a ClientError with a code outside every classification
    catalogue, as the adapter re-raises it in production; the helper must swallow it
    so a counter never blocks webhook delivery.
    """
    adapter.update_item.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "missing attribute"}},
        "UpdateItem",
    )

    assert helper("test_id") is None
    logger_mock.error.assert_called_once_with(
        event,
        webhook_id="test_id",
        status="unclassified",
        error_code="ValidationException",
        error="missing attribute",
    )


@pytest.mark.parametrize(
    "helper",
    [webhooks.increment_acknowledged_count, webhooks.increment_invocation_count],
)
def test_increment_count_propagates_programmer_errors(adapter, helper):
    """Only SDK errors are swallowed; a programmer error still propagates."""
    adapter.update_item.side_effect = TypeError("bad call")

    with pytest.raises(TypeError):
        helper("test_id")


# -- toggle_webhook -------------------------------------------------------------


def test_toggle_webhook_flips_active_flag(adapter):
    """The stored active flag is inverted with one adapter for both the read and the write."""
    adapter.get_item.return_value = OperationResult.success(data=WEBHOOK_ITEM)
    adapter.update_item.return_value = OperationResult.success()

    assert webhooks.toggle_webhook("test_id") is None

    adapter.factory.assert_called_once_with()
    adapter.get_item.assert_called_once_with(TableName="webhooks", Key={"id": {"S": "test_id"}})
    adapter.update_item.assert_called_once_with(
        TableName="webhooks",
        Key={"id": {"S": "test_id"}},
        UpdateExpression="SET active = :active",
        ExpressionAttributeValues={":active": {"BOOL": False}},
    )


def test_toggle_webhook_logs_and_skips_write_when_absent(adapter, logger_mock):
    """A missing webhook is logged as a warning and nothing is written."""
    adapter.get_item.return_value = OperationResult.success(data=None)

    assert webhooks.toggle_webhook("test_id") is None

    adapter.update_item.assert_not_called()
    logger_mock.warning.assert_called_once_with("webhook_toggle_not_found", webhook_id="test_id")


def test_toggle_webhook_raises_when_read_fails(adapter):
    """A failed read raises before any write is attempted."""
    adapter.get_item.return_value = _failure()

    with pytest.raises(webhooks.WebhookStoreUnavailableError):
        webhooks.toggle_webhook("test_id")

    adapter.update_item.assert_not_called()


def test_toggle_webhook_raises_and_logs_when_update_fails(adapter, logger_mock):
    """A failed write raises after logging the classified failure."""
    adapter.get_item.return_value = OperationResult.success(data=WEBHOOK_ITEM)
    adapter.update_item.return_value = _failure()

    with pytest.raises(webhooks.WebhookStoreUnavailableError):
        webhooks.toggle_webhook("test_id")

    logger_mock.error.assert_called_once_with("webhook_toggle_failed", webhook_id="test_id", **FAILURE_FIELDS)


def test_toggle_webhook_raises_and_logs_on_unclassified_client_error_on_write(adapter, logger_mock):
    """An unclassified SDK error on the update mirrors the classified write failure: logged, then raised."""
    adapter.get_item.return_value = OperationResult.success(data=WEBHOOK_ITEM)
    adapter.update_item.side_effect = _unclassified_client_error("UpdateItem")

    with pytest.raises(webhooks.WebhookStoreUnavailableError) as exc_info:
        webhooks.toggle_webhook("test_id")

    _assert_unclassified_unavailable(exc_info.value)
    logger_mock.error.assert_called_once_with("webhook_toggle_failed", webhook_id="test_id", **UNCLASSIFIED_FIELDS)


# -- removed helpers ------------------------------------------------------------


@pytest.mark.parametrize("name", ["delete_webhook", "revoke_webhook", "is_active"])
def test_dead_helpers_are_removed(name):
    """Helpers with no production caller are not part of the module surface."""
    assert not hasattr(webhooks, name)


# -- validate_string_payload_type -----------------------------------------------


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
def test_validate_string_payload_same_params_in_multiple_models_returns_first_found(model_utils_mock, caplog):
    model_utils_mock.get_dict_of_parameters_from_models.return_value = {
        "WrongModel": ["test"],
        "TestModel": ["type", "type2"],
        "TestModel2": ["type2"],
        "TestModel3": ["type"],
    }
    model_utils_mock.has_parameters_in_model.side_effect = [0, 2, 0, 1]
    response = webhooks.validate_string_payload_type('{"type": "test", "type2": "test"}')
    assert response == (
        "TestModel",
        {"type": "test", "type2": "test"},
    )
    assert response != (
        "TestModel3",
        {"type": "test"},
    )
    assert model_utils_mock.has_parameters_in_model.call_count == 4


@patch("modules.slack.webhooks.logger")
def test_validate_string_payload_type_error_loading_json(logger_mock):
    assert webhooks.validate_string_payload_type("{") == (None, None)
    logger_mock.warning.assert_called_with(
        "string_payload_validation_error",
        error="Invalid JSON payload",
    )


@patch("modules.slack.webhooks.logger")
def test_validate_string_payload_type_unknown_payload_type(logger_mock):
    assert webhooks.validate_string_payload_type('{"type": "unknown"}') == (
        None,
        None,
    )
    warning_message = "Unknown payload type"
    logger_mock.warning.assert_called_with(
        "string_payload_validation_error",
        error=warning_message,
        payload='{"type": "unknown"}',
    )

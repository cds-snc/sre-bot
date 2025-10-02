# --- AwsNotificationPattern and related function tests ---
import re
import types
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError
from models.webhooks import AwsSnsPayload
from modules.webhooks.aws_sns_notification import (
    AwsNotificationPattern,
    NOTIFICATION_HANDLERS,
    find_matching_handler,
    handle_generic_notification,
    process_aws_notification_payload,
    register_notification_pattern,
)


def test_aws_notification_pattern_validators():
    pattern = AwsNotificationPattern(
        name="test",
        pattern="foo",
        handler="modules.webhooks.patterns.aws_sns_notification.cloudwatch_alarm.handle_cloudwatch_alarm",
        match_type="contains",
        match_target="message",
        priority=1,
        enabled=True,
    )
    assert pattern.name == "test"
    assert pattern.pattern == "foo"
    assert pattern.handler.startswith("modules.webhooks.patterns")
    assert pattern.match_type == "contains"
    assert pattern.match_target == "message"
    assert pattern.priority == 1
    assert pattern.enabled is True


def test_aws_notification_pattern_validate_invalid_name():
    with pytest.raises(ValueError) as excinfo:
        AwsNotificationPattern(
            name="",
            pattern="foo",
            handler="x.y.z",
        )
    assert "AwsNotificationPattern.name must be a non-empty str" in str(excinfo.value)


def test_aws_notification_pattern_validate_name_type_error():
    with pytest.raises(ValueError) as excinfo:
        AwsNotificationPattern(
            name=123,  # not a string
            pattern="foo",
            handler="x.y.z",
        )
    assert "Input should be a valid string" in str(excinfo.value)


def test_aws_notification_pattern_validate_invalid_fields():
    with pytest.raises(ValueError) as excinfo:
        AwsNotificationPattern(
            name="test",
            pattern="",
            handler="x.y.z",
        )
    assert "AwsNotificationPattern.pattern must be a non-empty str" in str(
        excinfo.value
    )


def test_aws_notification_pattern_validate_invalid_fields_extended():
    with pytest.raises(ValueError) as excinfo:
        AwsNotificationPattern(
            name="test",
            pattern="foo",
            handler="",
        )
    assert "AwsNotificationPattern.handler must be a non-empty str" in str(
        excinfo.value
    )


def test_aws_notification_pattern_validate_invalid_match_type_enabled_priority():
    with pytest.raises(ValueError) as excinfo:
        AwsNotificationPattern(
            name="test",
            pattern="foo",
            handler="x.y.z",
            match_type="invalid",
        )
    assert (
        "Input should be 'regex', 'contains', 'callable' or 'message_structure'"
        in str(excinfo.value)
    )


def test_aws_notification_pattern_validate_priority_none():
    with pytest.raises(ValidationError) as excinfo:
        AwsNotificationPattern(
            name="test",
            pattern="foo",
            handler="x.y.z",
            priority=None,
        )
    assert "Input should be a valid integer" in str(excinfo.value)


def test_aws_notification_pattern_validate_invalid_enabled_priority_extended():
    with pytest.raises(ValueError) as excinfo:
        AwsNotificationPattern(
            name="test",
            pattern="foo",
            handler="x.y.z",
            enabled=234,
        )
    assert "Input should be a valid boolean, unable to interpret input" in str(
        excinfo.value
    )


def test_aws_notification_pattern_validate_invalid_priority():
    with pytest.raises(ValidationError) as excinfo:
        AwsNotificationPattern(
            name="test",
            pattern="foo",
            handler="x.y.z",
            priority="not-an-int",
        )
    assert (
        "Input should be a valid integer, unable to parse string as an integer"
        in str(excinfo.value)
    )


def test_get_compiled_pattern_callable_attribute_error(monkeypatch):
    dummy_module = types.ModuleType("dummy_module")
    monkeypatch.setitem(__import__("sys").modules, "dummy_module", dummy_module)
    pattern = AwsNotificationPattern(
        name="callable",
        pattern="dummy_module.notafunc",
        handler="x.y.z",
        match_type="callable",
    )
    with pytest.raises(ValueError) as excinfo:
        pattern.get_compiled_pattern()
    assert "Cannot import callable" in str(excinfo.value)


def test_aws_notification_pattern_get_handler_function(monkeypatch):
    dummy_module = types.ModuleType("dummy_handler_module")

    def dummy_handler(payload, client):
        return [{"type": "section", "text": {"type": "mrkdwn", "text": "handled"}}]

    setattr(dummy_module, "dummy_handler", dummy_handler)
    monkeypatch.setitem(__import__("sys").modules, "dummy_handler_module", dummy_module)
    pattern = AwsNotificationPattern(
        name="handler",
        pattern="foo",
        handler="dummy_handler_module.dummy_handler",
        match_type="contains",
    )
    handler_func = pattern.get_handler_function()
    assert callable(handler_func)
    result = handler_func(AwsSnsPayload(Message="abc"), MagicMock())
    assert isinstance(result, list)
    assert result[0]["text"]["text"] == "handled"
    pattern.handler = "notamodule.notafunc"
    with pytest.raises(ValueError):
        pattern.get_handler_function()


def test_get_handler_function_import_error():
    pattern = AwsNotificationPattern(
        name="handler",
        pattern="foo",
        handler="notamodule.notafunc",
        match_type="contains",
    )
    with pytest.raises(ValueError) as excinfo:
        pattern.get_handler_function()
    assert "Cannot import handler" in str(excinfo.value)


def test_get_handler_function_attribute_error(monkeypatch):
    dummy_module = types.ModuleType("dummy_handler_module")
    monkeypatch.setitem(__import__("sys").modules, "dummy_handler_module", dummy_module)
    pattern = AwsNotificationPattern(
        name="handler",
        pattern="foo",
        handler="dummy_handler_module.notafunc",
        match_type="contains",
    )
    with pytest.raises(ValueError) as excinfo:
        pattern.get_handler_function()
    assert "Cannot import handler" in str(excinfo.value)


def test_get_handler_function_value_error(monkeypatch):
    dummy_module = types.ModuleType("dummy_handler_module")
    monkeypatch.setitem(__import__("sys").modules, "dummy_handler_module", dummy_module)
    pattern = AwsNotificationPattern(
        name="handler",
        pattern="foo",
        handler="dummy_handler_module",
        match_type="contains",
    )
    with pytest.raises(ValueError) as excinfo:
        pattern.get_handler_function()
    assert "Cannot import handler" in str(excinfo.value)


def test_from_dict_register_pattern_and_find_matching_handler(monkeypatch):
    NOTIFICATION_HANDLERS.clear()
    pattern1 = AwsNotificationPattern(
        name="contains",
        pattern="hello",
        handler="dummy_handler_module.dummy_handler",
        match_type="contains",
        match_target="message",
    )
    register_notification_pattern(pattern1)
    pattern2 = AwsNotificationPattern(
        name="regex",
        pattern="world$",
        handler="dummy_handler_module.dummy_handler",
        match_type="regex",
        match_target="message",
    )
    register_notification_pattern(pattern2)
    dummy_module = types.ModuleType("dummy_module")

    def dummy_func(payload, parsed_message):
        return payload.Message == "callme"

    setattr(dummy_module, "dummy_func", dummy_func)
    monkeypatch.setitem(__import__("sys").modules, "dummy_module", dummy_module)
    pattern3 = AwsNotificationPattern(
        name="callable",
        pattern="dummy_module.dummy_func",
        handler="dummy_handler_module.dummy_handler",
        match_type="callable",
        match_target="message",
    )
    register_notification_pattern(pattern3)
    payload1 = AwsSnsPayload(Message="hello world")
    payload2 = AwsSnsPayload(Message="the world")
    payload3 = AwsSnsPayload(Message="callme")
    payload4 = AwsSnsPayload(Message="nomatch")
    assert find_matching_handler(payload1, payload1.Message).name == "contains"
    assert find_matching_handler(payload2, payload2.Message).name == "regex"
    assert find_matching_handler(payload3, payload3.Message).name == "callable"
    assert find_matching_handler(payload4, payload4.Message) is None


def test_handle_generic_notification():
    client = MagicMock()
    payload = AwsSnsPayload(Message="foo bar")
    blocks = handle_generic_notification(payload, client)
    assert isinstance(blocks, list)
    assert blocks == []


def test_process_aws_notification_payload(monkeypatch):
    NOTIFICATION_HANDLERS.clear()
    dummy_module = types.ModuleType("dummy_handler_module")

    def dummy_handler(payload, client):
        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"handled: {payload.Message}"},
            }
        ]

    setattr(dummy_module, "dummy_handler", dummy_handler)
    monkeypatch.setitem(__import__("sys").modules, "dummy_handler_module", dummy_module)
    pattern = AwsNotificationPattern(
        name="contains",
        pattern="abc",
        handler="dummy_handler_module.dummy_handler",
        match_type="contains",
        match_target="message",
    )
    register_notification_pattern(pattern)
    payload = AwsSnsPayload(Message="abc")
    client = MagicMock()
    result = process_aws_notification_payload(payload, client)
    assert isinstance(result, list)
    assert any("handled: abc" in b["text"]["text"] for b in result if "text" in b)
    payload2 = AwsSnsPayload(Message="no match")
    result2 = process_aws_notification_payload(payload2, client)
    assert result2 == []


def test_aws_notification_pattern_from_dict():
    d = {
        "name": "dictpattern",
        "pattern": "bar",
        "handler": "modules.webhooks.patterns.aws_sns_notification.cloudwatch_alarm.handle_cloudwatch_alarm",
        "match_type": "contains",
        "match_target": "message",
        "priority": 2,
        "enabled": False,
    }
    pattern = AwsNotificationPattern.from_dict(d)
    assert pattern.name == "dictpattern"
    assert pattern.pattern == "bar"
    assert pattern.handler.startswith("modules.webhooks.patterns")
    assert pattern.match_type == "contains"
    assert pattern.match_target == "message"
    assert pattern.priority == 2
    assert pattern.enabled is False


def test_aws_notification_pattern_get_compiled_pattern_regex():
    pattern = AwsNotificationPattern(
        name="regex",
        pattern="foo.*bar",
        handler="modules.webhooks.patterns.aws_sns_notification.cloudwatch_alarm.handle_cloudwatch_alarm",
        match_type="regex",
        match_target="message",
    )
    compiled = pattern.get_compiled_pattern()
    assert isinstance(compiled, re.Pattern)
    assert compiled.pattern == "foo.*bar"
    # Invalid regex
    pattern.pattern = "[unclosed"
    with pytest.raises(ValueError):
        pattern.get_compiled_pattern()


def test_aws_notification_pattern_get_compiled_pattern_contains():
    pattern = AwsNotificationPattern(
        name="contains",
        pattern="needle",
        handler="modules.webhooks.patterns.aws_sns_notification.cloudwatch_alarm.handle_cloudwatch_alarm",
        match_type="contains",
        match_target="message",
    )
    compiled = pattern.get_compiled_pattern()
    assert compiled == "needle"


def test_aws_notification_pattern_get_compiled_pattern_callable(monkeypatch):
    dummy_module = types.ModuleType("dummy_module")

    def dummy_func(payload, parsed_message):
        return payload.Message == "match"

    setattr(dummy_module, "dummy_func", dummy_func)
    monkeypatch.setitem(__import__("sys").modules, "dummy_module", dummy_module)
    pattern = AwsNotificationPattern(
        name="callable",
        pattern="dummy_module.dummy_func",
        handler="modules.webhooks.patterns.aws_sns_notification.cloudwatch_alarm.handle_cloudwatch_alarm",
        match_type="callable",
        match_target="message",
    )
    compiled = pattern.get_compiled_pattern()
    assert callable(compiled)
    payload = AwsSnsPayload(Message="match")
    assert compiled(payload, payload.Message) is True
    payload2 = AwsSnsPayload(Message="nope")
    assert compiled(payload2, payload2.Message) is False
    # Invalid import
    pattern.pattern = "notamodule.notafunc"
    with pytest.raises(ValueError):
        pattern.get_compiled_pattern()


def test_validate_slack_blocks():
    from modules.webhooks.aws_sns_notification import validate_slack_blocks

    # Valid blocks
    valid_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}},
        {"type": "divider"},
        {"type": "header", "text": {"type": "plain_text", "text": "Header"}},
    ]
    assert validate_slack_blocks(valid_blocks) is True

    # Invalid blocks - not a list
    assert validate_slack_blocks("not a list") is False

    # Invalid blocks - block not a dict
    assert validate_slack_blocks(["not a dict"]) is False

    # Invalid blocks - missing type
    assert validate_slack_blocks([{"text": "no type"}]) is False

    # Invalid blocks - section missing text
    assert validate_slack_blocks([{"type": "section"}]) is False

    # Invalid blocks - header missing text
    assert validate_slack_blocks([{"type": "header"}]) is False

    # Invalid blocks - divider with extra fields
    assert validate_slack_blocks([{"type": "divider", "extra": "field"}]) is False

    # Empty list is valid
    assert validate_slack_blocks([]) is True


def test_get_match_text_invalid_target(monkeypatch):
    # Create a valid pattern first
    pattern = AwsNotificationPattern(
        name="test",
        pattern="foo",
        handler="x.y.z",
        match_target="message",
    )
    # Then directly set an invalid target to bypass validation
    monkeypatch.setattr(pattern, "match_target", "invalid_target")
    payload = AwsSnsPayload(Message="abc")
    assert pattern.get_match_text(payload, "abc") == ""


def test_get_match_text_all_targets():
    pattern = AwsNotificationPattern(
        name="test",
        pattern="foo",
        handler="x.y.z",
        match_target="message",
    )
    payload = AwsSnsPayload(
        Message="test message",
        Subject="test subject",
        TopicArn="arn:aws:sns:us-east-1:123:test",
    )

    # Test message target
    pattern.match_target = "message"
    assert pattern.get_match_text(payload, "parsed") == "test message"

    # Test subject target
    pattern.match_target = "subject"
    assert pattern.get_match_text(payload, "parsed") == "test subject"

    # Test topic_arn target
    pattern.match_target = "topic_arn"
    assert pattern.get_match_text(payload, "parsed") == "arn:aws:sns:us-east-1:123:test"

    # Test parsed_message target with dict
    pattern.match_target = "parsed_message"
    parsed_dict = {"key": "value"}
    assert pattern.get_match_text(payload, parsed_dict) == '{"key": "value"}'

    # Test parsed_message target with string
    assert pattern.get_match_text(payload, "parsed string") == "parsed string"


def test_find_matching_handler_exception_handling(monkeypatch):
    from modules.webhooks.aws_sns_notification import (
        NOTIFICATION_HANDLERS,
        find_matching_handler,
        register_notification_pattern,
    )

    NOTIFICATION_HANDLERS.clear()

    # Create a pattern that raises an exception during get_compiled_pattern
    class BadPattern(AwsNotificationPattern):
        def get_compiled_pattern(self):
            raise ValueError("Pattern compilation failed")

    bad_pattern = BadPattern(
        name="bad_pattern",
        pattern="foo",
        handler="x.y.z",
        match_type="regex",
    )
    register_notification_pattern(bad_pattern)

    payload = AwsSnsPayload(Message="test")
    result = find_matching_handler(payload, "test")
    assert result is None


def test_find_matching_handler_message_structure():
    from modules.webhooks.aws_sns_notification import (
        NOTIFICATION_HANDLERS,
        find_matching_handler,
        register_notification_pattern,
    )

    NOTIFICATION_HANDLERS.clear()

    # Pattern that matches message structure
    pattern = AwsNotificationPattern(
        name="struct_pattern",
        pattern="AlarmName",
        handler="x.y.z",
        match_type="message_structure",
        match_target="parsed_message",
    )
    register_notification_pattern(pattern)

    payload = AwsSnsPayload(Message='{"AlarmName": "TestAlarm"}')
    parsed_message = {"AlarmName": "TestAlarm", "State": "ALARM"}

    result = find_matching_handler(payload, parsed_message)
    assert result is not None
    assert result.name == "struct_pattern"

    # Should not match if key is missing
    parsed_message_no_match = {"State": "ALARM"}
    result_no_match = find_matching_handler(payload, parsed_message_no_match)
    assert result_no_match is None


def test_process_aws_notification_payload_handler_exception(monkeypatch):
    from modules.webhooks.aws_sns_notification import (
        NOTIFICATION_HANDLERS,
        process_aws_notification_payload,
        register_notification_pattern,
    )

    NOTIFICATION_HANDLERS.clear()

    # Create a handler that raises an exception
    def bad_handler(payload, client):
        raise RuntimeError("Handler execution failed")

    dummy_module = types.ModuleType("bad_handler_module")
    setattr(dummy_module, "bad_handler", bad_handler)
    monkeypatch.setitem(__import__("sys").modules, "bad_handler_module", dummy_module)

    pattern = AwsNotificationPattern(
        name="bad_handler_pattern",
        pattern="test",
        handler="bad_handler_module.bad_handler",
        match_type="contains",
    )
    register_notification_pattern(pattern)

    payload = AwsSnsPayload(Message="test message")
    client = MagicMock()

    result = process_aws_notification_payload(payload, client)
    # Should fall back to generic handler (returns empty list)
    assert result == []


def test_process_aws_notification_payload_invalid_blocks(monkeypatch):
    from modules.webhooks.aws_sns_notification import (
        NOTIFICATION_HANDLERS,
        process_aws_notification_payload,
        register_notification_pattern,
    )

    NOTIFICATION_HANDLERS.clear()

    # Create a handler that returns invalid blocks
    def invalid_blocks_handler(payload, client):
        return "not a list"  # Invalid return type

    dummy_module = types.ModuleType("invalid_handler_module")
    setattr(dummy_module, "invalid_blocks_handler", invalid_blocks_handler)
    monkeypatch.setitem(
        __import__("sys").modules, "invalid_handler_module", dummy_module
    )

    pattern = AwsNotificationPattern(
        name="invalid_blocks_pattern",
        pattern="test",
        handler="invalid_handler_module.invalid_blocks_handler",
        match_type="contains",
    )
    register_notification_pattern(pattern)

    payload = AwsSnsPayload(Message="test message")
    client = MagicMock()

    result = process_aws_notification_payload(payload, client)
    # Should fall back to generic handler due to invalid blocks
    assert result == []


def test_process_aws_notification_payload_import_error(monkeypatch):
    from modules.webhooks.aws_sns_notification import (
        NOTIFICATION_HANDLERS,
        process_aws_notification_payload,
        register_notification_pattern,
    )

    NOTIFICATION_HANDLERS.clear()

    pattern = AwsNotificationPattern(
        name="import_error_pattern",
        pattern="test",
        handler="nonexistent_module.nonexistent_handler",
        match_type="contains",
    )
    register_notification_pattern(pattern)

    payload = AwsSnsPayload(Message="test message")
    client = MagicMock()

    result = process_aws_notification_payload(payload, client)
    # Should fall back to generic handler due to import error
    assert result == []

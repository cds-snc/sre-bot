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

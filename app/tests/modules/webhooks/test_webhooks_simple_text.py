# --- SimpleTextPattern and related function tests ---
import re
import types
import pytest
from pydantic import ValidationError
from models.webhooks import SimpleTextPayload, WebhookPayload, WebhookResult
from modules.webhooks.simple_text import (
    PATTERN_HANDLERS,
    SimpleTextPattern,
    find_matching_handler,
    handle_generic_text,
    process_simple_text_payload,
    register_pattern,
)


def test_simple_text_pattern_validators():
    # Valid pattern
    pattern = SimpleTextPattern(
        name="test",
        pattern="foo",
        handler="modules.webhooks.patterns.simple_text.upptime.handle_upptime_payload",
        match_type="contains",
        priority=1,
        enabled=True,
    )
    assert pattern.name == "test"
    assert pattern.pattern == "foo"
    assert pattern.handler.startswith("modules.webhooks.patterns")
    assert pattern.match_type == "contains"
    assert pattern.priority == 1
    assert pattern.enabled is True


def test_simple_text_pattern_validate_invalid_name():
    # Invalid name
    with pytest.raises(ValueError) as excinfo:
        SimpleTextPattern(
            name="",
            pattern="foo",
            handler="x.y.z",
        )
    assert "SimpleTextPattern.name must be a non-empty str" in str(excinfo.value)


def test_simple_text_pattern_validate_invalid_fields():
    # Invalid pattern
    with pytest.raises(ValueError) as excinfo:
        SimpleTextPattern(
            name="test",
            pattern="",
            handler="x.y.z",
        )
    assert "SimpleTextPattern.pattern must be a non-empty str" in str(excinfo.value)


def test_simple_text_pattern_validate_invalid_fields_extended():
    # Invalid handler
    with pytest.raises(ValueError) as excinfo:
        SimpleTextPattern(
            name="test",
            pattern="foo",
            handler="",
        )

    assert "SimpleTextPattern.handler must be a non-empty str" in str(excinfo.value)


def test_simple_text_pattern_validate_invalid_match_type_enabled_priority():
    # Invalid match_type
    with pytest.raises(ValueError) as excinfo:
        SimpleTextPattern(
            name="test",
            pattern="foo",
            handler="x.y.z",
            match_type="invalid",
        )
    assert "Input should be 'regex', 'contains' or 'callable'" in str(excinfo.value)


def test_simple_text_pattern_validate_invalid_enabled_priority_extended():
    # Invalid enabled
    with pytest.raises(ValueError) as excinfo:
        SimpleTextPattern(
            name="test",
            pattern="foo",
            handler="x.y.z",
            enabled=234,
        )
    assert "Input should be a valid boolean" in str(excinfo.value)


def test_simple_text_pattern_validate_invalid_priority():
    # Invalid priority
    with pytest.raises(ValidationError) as excinfo:
        SimpleTextPattern(
            name="test",
            pattern="foo",
            handler="x.y.z",
            priority="not-an-int",
        )

    assert "Input should be a valid integer" in str(excinfo.value)


def test_get_compiled_pattern_callable_attribute_error(monkeypatch):
    dummy_module = types.ModuleType("dummy_module")
    monkeypatch.setitem(__import__("sys").modules, "dummy_module", dummy_module)
    pattern = SimpleTextPattern(
        name="callable",
        pattern="dummy_module.notafunc",
        handler="x.y.z",
        match_type="callable",
    )
    with pytest.raises(ValueError) as excinfo:
        pattern.get_compiled_pattern()
    assert "Cannot import callable" in str(excinfo.value)


# get_handler_function
def test_simple_text_pattern_get_handler_function(monkeypatch):
    dummy_module = types.ModuleType("dummy_handler_module")

    def dummy_handler(text):
        return WebhookPayload(text=f"handled: {text}")

    setattr(dummy_module, "dummy_handler", dummy_handler)
    monkeypatch.setitem(__import__("sys").modules, "dummy_handler_module", dummy_module)
    pattern = SimpleTextPattern(
        name="handler",
        pattern="foo",
        handler="dummy_handler_module.dummy_handler",
        match_type="contains",
    )
    handler_func = pattern.get_handler_function()
    assert callable(handler_func)
    result = handler_func("abc")
    assert isinstance(result, WebhookPayload)
    assert result.text == "handled: abc"
    pattern.handler = "notamodule.notafunc"
    with pytest.raises(ValueError):
        pattern.get_handler_function()


def test_get_handler_function_import_error():
    pattern = SimpleTextPattern(
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
    pattern = SimpleTextPattern(
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
    pattern = SimpleTextPattern(
        name="handler",
        pattern="foo",
        handler="dummy_handler_module",
        match_type="contains",
    )
    with pytest.raises(ValueError) as excinfo:
        pattern.get_handler_function()
    assert "Cannot import handler" in str(excinfo.value)


# from_dict, register_pattern, find_matching_handler
def test_register_pattern_and_find_matching_handler(monkeypatch):
    PATTERN_HANDLERS.clear()
    pattern1 = SimpleTextPattern(
        name="contains",
        pattern="hello",
        handler="dummy_handler_module.dummy_handler",
        match_type="contains",
    )
    register_pattern(pattern1)
    pattern2 = SimpleTextPattern(
        name="regex",
        pattern="world$",
        handler="dummy_handler_module.dummy_handler",
        match_type="regex",
    )
    register_pattern(pattern2)
    dummy_module = types.ModuleType("dummy_module")

    def dummy_func(text):
        return text == "callme"

    setattr(dummy_module, "dummy_func", dummy_func)
    monkeypatch.setitem(__import__("sys").modules, "dummy_module", dummy_module)
    pattern3 = SimpleTextPattern(
        name="callable",
        pattern="dummy_module.dummy_func",
        handler="dummy_handler_module.dummy_handler",
        match_type="callable",
    )
    register_pattern(pattern3)
    assert find_matching_handler("hello world").name == "contains"
    assert find_matching_handler("the world").name == "regex"
    assert find_matching_handler("callme").name == "callable"
    assert find_matching_handler("nomatch") is None


# handle_generic_text
def test_handle_generic_text():
    payload = handle_generic_text("foo bar")
    assert isinstance(payload, WebhookPayload)
    assert payload.text == "foo bar"


# process_simple_text_payload
def test_process_simple_text_payload(monkeypatch):
    PATTERN_HANDLERS.clear()
    dummy_module = types.ModuleType("dummy_handler_module")

    def dummy_handler(text):
        return WebhookPayload(text=f"handled: {text}")

    setattr(dummy_module, "dummy_handler", dummy_handler)
    monkeypatch.setitem(__import__("sys").modules, "dummy_handler_module", dummy_module)
    pattern = SimpleTextPattern(
        name="contains",
        pattern="abc",
        handler="dummy_handler_module.dummy_handler",
        match_type="contains",
    )
    register_pattern(pattern)
    payload = SimpleTextPayload(text="abc")
    result = process_simple_text_payload(payload)
    assert isinstance(result, WebhookResult)
    assert result.status == "success"
    assert result.action == "post"
    assert isinstance(result.payload, WebhookPayload)
    assert result.payload.text == "handled: abc"
    payload2 = SimpleTextPayload(text="no match")
    result2 = process_simple_text_payload(payload2)
    assert result2.payload.text == "no match"


def test_simple_text_pattern_from_dict():
    d = {
        "name": "dictpattern",
        "pattern": "bar",
        "handler": "modules.webhooks.patterns.simple_text.upptime.handle_upptime_payload",
        "match_type": "contains",
        "priority": 2,
        "enabled": False,
    }
    pattern = SimpleTextPattern.from_dict(d)
    assert pattern.name == "dictpattern"
    assert pattern.pattern == "bar"
    assert pattern.handler.startswith("modules.webhooks.patterns")
    assert pattern.match_type == "contains"
    assert pattern.priority == 2
    assert pattern.enabled is False


def test_simple_text_pattern_get_compiled_pattern_regex():
    pattern = SimpleTextPattern(
        name="regex",
        pattern="foo.*bar",
        handler="modules.webhooks.patterns.simple_text.upptime.handle_upptime_payload",
        match_type="regex",
    )
    compiled = pattern.get_compiled_pattern()
    assert isinstance(compiled, re.Pattern)
    assert compiled.pattern == "foo.*bar"
    # Invalid regex
    pattern.pattern = "[unclosed"
    with pytest.raises(ValueError):
        pattern.get_compiled_pattern()


def test_simple_text_pattern_get_compiled_pattern_contains():
    pattern = SimpleTextPattern(
        name="contains",
        pattern="needle",
        handler="modules.webhooks.patterns.simple_text.upptime.handle_upptime_payload",
        match_type="contains",
    )
    compiled = pattern.get_compiled_pattern()
    assert compiled == "needle"


def test_simple_text_pattern_get_compiled_pattern_callable(monkeypatch):
    # Create a dummy callable in a dummy module
    dummy_module = types.ModuleType("dummy_module")

    def dummy_func(text):
        return text == "match"

    setattr(dummy_module, "dummy_func", dummy_func)
    monkeypatch.setitem(__import__("sys").modules, "dummy_module", dummy_module)
    pattern = SimpleTextPattern(
        name="callable",
        pattern="dummy_module.dummy_func",
        handler="modules.webhooks.patterns.simple_text.upptime.handle_upptime_payload",
        match_type="callable",
    )
    compiled = pattern.get_compiled_pattern()
    assert callable(compiled)
    assert compiled("match") is True
    assert compiled("nope") is False
    # Invalid import
    pattern.pattern = "notamodule.notafunc"
    with pytest.raises(ValueError):
        pattern.get_compiled_pattern()

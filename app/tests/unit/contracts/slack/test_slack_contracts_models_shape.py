"""Unit tests for the Slack command models in contracts.slack.models.

The tests import the five command types from the contracts layer, check the
shape each type has always had (dataclass-ness, mutability, exception base) and
scan the package source so no Slack SDK import reaches the contracts layer.
"""

import ast
import dataclasses
from pathlib import Path

import pytest

import contracts.slack
from contracts.slack.models import (
    Argument,
    ArgumentParsingError,
    ArgumentType,
    CommandPayload,
    CommandResponse,
)

_FORBIDDEN_SDK_ROOTS = frozenset({"slack_bolt", "slack_sdk"})


@pytest.mark.unit
class TestSlackContractsModelsShape:
    def test_argument_type_is_str_enum_with_all_members(self):
        assert [member.value for member in ArgumentType] == [
            "string",
            "email",
            "boolean",
            "integer",
            "choice",
            "csv",
        ]
        assert ArgumentType.EMAIL == "email"

    @pytest.mark.parametrize("model", [Argument, CommandPayload, CommandResponse])
    def test_command_models_are_mutable_dataclasses(self, model: type):
        assert dataclasses.is_dataclass(model)
        assert model.__dataclass_params__.frozen is False  # type: ignore[attr-defined]

    def test_argument_parsing_error_is_exception_dataclass(self):
        error = ArgumentParsingError(argument="--role", message="bad", suggestion="use OWNER")

        assert isinstance(error, Exception)
        assert dataclasses.is_dataclass(ArgumentParsingError)
        assert str(error) == "Error parsing --role: bad\n  Suggestion: use OWNER"

    def test_command_payload_generates_correlation_id_when_missing(self):
        payload = CommandPayload(text="/sre help", user_id="U1")

        assert payload.correlation_id.startswith("cmd-")
        assert payload.user_locale == "en-US"

    def test_contracts_slack_has_no_slack_sdk_import(self):
        package_dir = Path(contracts.slack.__file__).parent
        offenders: list[str] = []
        for source in package_dir.rglob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = [node.module.split(".")[0]]
                else:
                    continue
                offenders.extend(f"{source.name}: {root}" for root in roots if root in _FORBIDDEN_SDK_ROOTS)

        assert offenders == []

"""Unit tests for the Slack registrar and reply Protocols in contracts.slack.

A Protocol-conformant fake registrar stands in for the Slack runtime: the
tests assign it to the Protocol types (checked statically by mypy), run a real
package hookimpl against it, and compare the Protocol's ``register_command``
signature with the runtime provider's so the two cannot drift apart. An AST
scan of the package source proves no Slack SDK import reaches the contracts
layer.
"""

import ast
import inspect
from pathlib import Path

import pytest

import contracts.slack
import packages.user_rotations as user_rotations_module
from contracts.slack.registrar import SlackCommandRegistrar
from contracts.slack.reply import SlackReplyPort
from integrations.slack.provider import SlackPlatformProvider
from tests.factories.slack import FakeSlackRegistrar, FakeSlackReply

pytestmark = pytest.mark.unit

_FORBIDDEN_SDK_ROOTS = frozenset({"slack_bolt", "slack_sdk"})


def test_fake_registrar_satisfies_the_registrar_and_reply_protocols() -> None:
    registrar: SlackCommandRegistrar = FakeSlackRegistrar()
    reply: SlackReplyPort = registrar.reply

    assert isinstance(reply, FakeSlackReply)
    assert reply.post_ephemeral(channel_id="C1", user_id="U1", text="hi").is_success


def test_hookimpl_registers_its_commands_through_the_registrar() -> None:
    registrar = FakeSlackRegistrar()

    user_rotations_module.register_slack_commands(registrar=registrar)

    assert [(entry["command"], entry["parent"]) for entry in registrar.commands] == [
        ("rotations", "sre"),
        ("view", "sre.rotations"),
    ]


def test_registrar_register_command_mirrors_the_runtime_provider_signature() -> None:
    protocol_params = inspect.signature(SlackCommandRegistrar.register_command).parameters
    provider_params = inspect.signature(SlackPlatformProvider.register_command).parameters

    assert list(protocol_params) == list(provider_params)
    assert {name: param.default for name, param in protocol_params.items()} == {
        name: param.default for name, param in provider_params.items()
    }
    assert {name: param.kind for name, param in protocol_params.items()} == {
        name: param.kind for name, param in provider_params.items()
    }


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("post_message", ["self", "channel_id", "text", "username", "icon_url"]),
        ("post_ephemeral", ["self", "channel_id", "user_id", "text"]),
        ("open_view", ["self", "trigger_id", "view"]),
    ],
)
def test_reply_port_methods_take_keyword_only_arguments(method: str, expected: list[str]) -> None:
    params = inspect.signature(getattr(SlackReplyPort, method)).parameters

    assert list(params) == expected
    assert all(param.kind is inspect.Parameter.KEYWORD_ONLY for name, param in params.items() if name != "self")


def test_contracts_slack_registrar_and_reply_import_no_slack_sdk() -> None:
    package_dir = Path(contracts.slack.__file__).parent
    offenders: list[str] = []
    for source in (package_dir / "registrar.py", package_dir / "reply.py"):
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

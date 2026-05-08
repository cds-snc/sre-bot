"""Unit tests for infrastructure.slack.routing.CommandRouter.

Covers registration, hierarchical routing, dispatch, help generation,
auto-generated intermediate nodes, and error paths — all in isolation.
"""

import pytest

from infrastructure.slack.models import CommandPayload, CommandResponse
from infrastructure.slack.parsing import Argument, ArgumentType
from infrastructure.slack.routing import CommandRouter

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def _payload(
    text: str = "", user_id: str = "U001", locale: str = "en-US"
) -> CommandPayload:
    return CommandPayload(text=text, user_id=user_id, user_locale=locale)


def _ok_handler(payload: CommandPayload) -> CommandResponse:
    return CommandResponse(message=f"ok:{payload.text}")


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRATION
# ─────────────────────────────────────────────────────────────────────────────


class TestCommandRegistration:
    def test_register_root_command_stored(self):
        router = CommandRouter()
        router.register("sre", _ok_handler)

        assert "sre" in router._commands

    def test_register_child_command_stored(self):
        router = CommandRouter()
        router.register("groups", _ok_handler, parent="sre")

        assert "sre.groups" in router._commands

    def test_register_child_auto_creates_parent_node(self):
        router = CommandRouter()
        router.register("add", _ok_handler, parent="sre.groups")

        assert "sre" in router._commands
        assert "sre.groups" in router._commands
        assert "sre.groups.add" in router._commands

    def test_auto_generated_parent_has_no_handler(self):
        router = CommandRouter()
        router.register("add", _ok_handler, parent="sre.groups")

        assert router._commands["sre"].handler is None
        assert router._commands["sre"].is_auto_generated is True

    def test_root_commands_returns_sorted_roots(self):
        router = CommandRouter()
        router.register("zebrabot", None)
        router.register("alphacmd", None)
        router.register("sub", None, parent="alphacmd")

        roots = router.root_commands()

        assert roots == ["alphacmd", "zebrabot"]

    def test_root_commands_empty_when_no_commands(self):
        router = CommandRouter()

        assert router.root_commands() == []


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE — hierarchical traversal
# ─────────────────────────────────────────────────────────────────────────────


class TestRoute:
    def test_empty_text_dispatches_directly(self):
        router = CommandRouter()
        router.register("sre", _ok_handler)
        payload = _payload(text="")

        response = router.route("sre", "", payload)

        assert response.message == "ok:"

    def test_unknown_subcommand_falls_through_to_dispatch(self):
        router = CommandRouter()
        router.register("sre", _ok_handler)
        payload = _payload()

        response = router.route("sre", "unknowncmd", payload)

        # Falls through: text set to full input before dispatching sre
        assert "ok:" in response.message

    def test_known_subcommand_routes_recursively(self):
        router = CommandRouter()

        def leaf(p: CommandPayload) -> CommandResponse:
            return CommandResponse(message=f"leaf:{p.text}")

        router.register("list", leaf, parent="sre")
        payload = _payload()

        response = router.route("sre", "list", payload)

        assert response.message == "leaf:"

    def test_three_level_routing_strips_command_tokens(self):
        router = CommandRouter()

        def leaf(p: CommandPayload) -> CommandResponse:
            return CommandResponse(message=f"args:{p.text}")

        router.register("add", leaf, parent="sre.groups")
        payload = _payload()

        response = router.route("sre", "groups add owner@example.com", payload)

        assert response.message == "args:owner@example.com"

    def test_help_keyword_triggers_dispatch_on_current_node(self):
        router = CommandRouter()
        router.register("list", _ok_handler, parent="sre")
        payload = _payload()

        response = router.route("sre", "help", payload)

        assert response.ephemeral is True
        assert response.message  # non-empty help text

    def test_help_keyword_variants_all_trigger_help(self):
        router = CommandRouter()
        router.register("list", _ok_handler, parent="sre")

        for keyword in ("help", "--help", "-h", "aide"):
            payload = _payload()
            response = router.route("sre", keyword, payload)
            assert (
                response.ephemeral is True
            ), f"keyword={keyword!r} should be ephemeral"

    def test_quoted_argument_preserved_through_routing(self):
        router = CommandRouter()

        def leaf(p: CommandPayload) -> CommandResponse:
            return CommandResponse(message=p.text)

        router.register("create", leaf, parent="incident")
        payload = _payload()

        response = router.route("incident", 'create --title "DB outage"', payload)

        assert "DB outage" in response.message


# ─────────────────────────────────────────────────────────────────────────────
# DISPATCH — handler resolution
# ─────────────────────────────────────────────────────────────────────────────


class TestDispatch:
    def test_dispatch_unknown_command_returns_unknown_error(self):
        router = CommandRouter()
        payload = _payload()

        response = router.dispatch("nonexistent", payload)

        assert response.ephemeral is True
        assert "Unknown command" in response.message

    def test_dispatch_command_without_handler_returns_help(self):
        router = CommandRouter()
        router.register("sre", None)  # no handler
        payload = _payload()

        response = router.dispatch("sre", payload)

        assert response.ephemeral is True

    def test_dispatch_with_handler_calls_handler(self):
        def handler(p: CommandPayload) -> CommandResponse:
            return CommandResponse(message="done")

        router = CommandRouter()
        router.register("ping", handler)
        payload = _payload()

        response = router.dispatch("ping", payload)

        assert response.message == "done"

    def test_dispatch_handler_exception_returns_error_response(self):
        router = CommandRouter()

        def bad_handler(p):
            raise ValueError("boom")

        router.register("explode", bad_handler)
        payload = _payload()

        response = router.dispatch("explode", payload)

        assert response.ephemeral is True
        assert "boom" in response.message

    def test_dispatch_without_text_and_arguments_defined_returns_help(self):
        """When a command defines arguments and no text is given, return help."""
        router = CommandRouter()
        args = [Argument(name="id", required=True)]
        handler = MagicMock(return_value=CommandResponse(message="done"))
        router.register("show", handler, arguments=args)
        payload = _payload(text="")

        response = router.dispatch("show", payload)

        assert response.ephemeral is True
        handler.assert_not_called()

    def test_dispatch_with_fallback_handler_invoked_when_no_text(self):
        router = CommandRouter()
        args = [Argument(name="id", required=True)]
        fallback = MagicMock(return_value=CommandResponse(message="fallback"))
        router.register("show", MagicMock(), arguments=args, fallback_handler=fallback)
        payload = _payload(text="")

        response = router.dispatch("show", payload)

        fallback.assert_called_once_with(payload)
        assert response.message == "fallback"

    def test_dispatch_with_valid_arguments_passes_parsed_args_to_handler(self):
        router = CommandRouter()
        args = [Argument(name="--count", type=ArgumentType.INTEGER)]
        received: list = []

        def handler(p, parsed):
            received.append(parsed)
            return CommandResponse(message="ok")

        router.register("run", handler, arguments=args)
        payload = _payload(text="--count 5")

        response = router.dispatch("run", payload)

        assert response.message == "ok"
        assert received[0]["--count"] == 5

    def test_dispatch_argument_parsing_error_returns_error_response(self):
        router = CommandRouter()
        args = [
            Argument(name="--role", type=ArgumentType.CHOICE, choices=["admin", "user"])
        ]
        router.register("set", MagicMock(), arguments=args)
        payload = _payload(text="--role superuser")

        response = router.dispatch("set", payload)

        assert response.ephemeral is True
        assert (
            "Argument parsing error" in response.message
            or "parsing error" in response.message.lower()
        )

    def test_dispatch_with_schema_validation_error_returns_validation_error(self):
        from pydantic import BaseModel

        class MySchema(BaseModel):
            count: int

        router = CommandRouter()
        args = [Argument(name="count")]
        router.register(
            "run",
            MagicMock(),
            arguments=args,
            schema=MySchema,
        )
        payload = _payload(text="not_a_number")

        response = router.dispatch("run", payload)

        assert response.ephemeral is True
        assert (
            "Validation error" in response.message
            or "validation error" in response.message.lower()
        )

    def test_dispatch_with_argument_mapper_used_for_schema_validation(self):
        """argument_mapper transforms args for schema validation, not for handler call."""
        from pydantic import BaseModel

        class MappedSchema(BaseModel):
            mapped_name: str

        router = CommandRouter()
        args = [Argument(name="--name")]
        received: list = []

        def mapper(parsed):
            return {"mapped_name": parsed.get("--name")}

        def handler(p, parsed):
            received.append(parsed)
            return CommandResponse(message="ok")

        router.register(
            "greet",
            handler,
            arguments=args,
            argument_mapper=mapper,
            schema=MappedSchema,
        )
        payload = _payload(text="--name Alice")

        response = router.dispatch("greet", payload)

        # Handler receives the raw parsed dict, mapper is used only for schema validation
        assert response.message == "ok"
        assert received[0]["--name"] == "Alice"


# Need to import MagicMock for the tests that use it
from unittest.mock import MagicMock  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# HELP GENERATION
# ─────────────────────────────────────────────────────────────────────────────


class TestHelpGeneration:
    def test_generate_help_returns_non_empty_string(self):
        router = CommandRouter()
        router.register("sre", None, description="SRE commands")
        router.register("groups", None, parent="sre", description="Group management")

        text = router.generate_help()

        assert isinstance(text, str)
        assert len(text) > 0

    def test_generate_help_with_root_command_scoped(self):
        router = CommandRouter()
        router.register("groups", None, parent="sre", description="Group management")

        text = router.generate_help(root_command="sre")

        assert isinstance(text, str)

    def test_generate_command_help_returns_non_empty_string(self):
        router = CommandRouter()
        router.register("list", _ok_handler, parent="sre", description="List resources")

        text = router.generate_command_help("sre.list")

        assert isinstance(text, str)
        assert len(text) > 0

    def test_generate_command_help_unknown_command_returns_string(self):
        router = CommandRouter()

        text = router.generate_command_help("nonexistent")

        assert isinstance(text, str)

    def test_translator_used_in_help(self):
        translator = MagicMock(return_value="Commandes Disponibles")
        router = CommandRouter(translator=translator)
        router.register("sre", None, description="SRE commands")

        text = router.generate_help()

        translator.assert_called()
        assert isinstance(text, str)

    def test_translator_fallback_on_exception(self):
        def bad_translator(key, fallback, locale):
            raise RuntimeError("translation service down")

        router = CommandRouter(translator=bad_translator)
        router.register("sre", None, description="SRE commands")

        # Should not raise; should fall back to default text
        text = router.generate_help()

        assert isinstance(text, str)


# ─────────────────────────────────────────────────────────────────────────────
# set_translator
# ─────────────────────────────────────────────────────────────────────────────


class TestSetTranslator:
    def test_set_translator_updates_internal_translator(self):
        router = CommandRouter()
        translator = MagicMock(return_value="ok")

        router.set_translator(translator)

        assert router._translator is translator

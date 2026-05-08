"""Unit tests for infrastructure.slack.parsing.

Covers ArgumentType, Argument properties, CommandArgumentParser tokenization,
parse, and all validation branches (email, integer, choice, csv, required,
defaults, aliases, allow_multiple).
"""

import pytest

from infrastructure.slack.parsing import (
    Argument,
    ArgumentParsingError,
    ArgumentType,
    CommandArgumentParser,
)

pytestmark = pytest.mark.unit


# ─────────────────────────────────────────────────────────────────────────────
# Argument — property helpers
# ─────────────────────────────────────────────────────────────────────────────


class TestArgumentProperties:
    def test_flag_detected_correctly(self):
        arg = Argument(name="--managed", type=ArgumentType.BOOLEAN)
        assert arg.is_flag is True
        assert arg.is_option is False
        assert arg.is_positional is False

    def test_option_detected_correctly(self):
        arg = Argument(name="--role")
        assert arg.is_option is True
        assert arg.is_flag is False
        assert arg.is_positional is False

    def test_positional_detected_correctly(self):
        arg = Argument(name="group_id")
        assert arg.is_positional is True
        assert arg.is_flag is False
        assert arg.is_option is False

    def test_get_canonical_name_strips_aliases(self):
        arg = Argument(name="--role, -r")
        assert arg.get_canonical_name() == "--role"

    def test_get_canonical_name_no_alias(self):
        arg = Argument(name="--count")
        assert arg.get_canonical_name() == "--count"


# ─────────────────────────────────────────────────────────────────────────────
# ArgumentParsingError
# ─────────────────────────────────────────────────────────────────────────────


class TestArgumentParsingError:
    def test_str_without_suggestion(self):
        err = ArgumentParsingError(argument="--role", message="bad value")
        assert "bad value" in str(err)
        assert "--role" in str(err)

    def test_str_with_suggestion(self):
        err = ArgumentParsingError(
            argument="--role", message="bad value", suggestion="Use admin or user"
        )
        assert "Use admin or user" in str(err)


# ─────────────────────────────────────────────────────────────────────────────
# CommandArgumentParser — tokenization
# ─────────────────────────────────────────────────────────────────────────────


class TestTokenization:
    def _tokenize(self, text: str):
        parser = CommandArgumentParser([])
        return parser._tokenize(text)

    def test_simple_tokens(self):
        assert self._tokenize("a b c") == ["a", "b", "c"]

    def test_double_quoted_token_preserved(self):
        tokens = self._tokenize('"hello world"')
        assert tokens == ["hello world"]

    def test_single_quoted_token_preserved(self):
        tokens = self._tokenize("'hello world'")
        assert tokens == ["hello world"]

    def test_backtick_quoted_token_preserved(self):
        tokens = self._tokenize("`hello world`")
        assert tokens == ["hello world"]

    def test_mixed_quoted_and_unquoted(self):
        tokens = self._tokenize('--title "DB outage" --managed')
        assert tokens == ["--title", "DB outage", "--managed"]

    def test_empty_string_returns_empty_list(self):
        assert self._tokenize("") == []

    def test_whitespace_only_returns_empty_list(self):
        assert self._tokenize("   ") == []

    def test_escaped_space_treated_as_literal(self):
        tokens = self._tokenize(r"hello\ world")
        assert tokens == ["hello world"]

    def test_quoted_empty_string_is_preserved(self):
        tokens = self._tokenize('""')
        assert tokens == [""]


# ─────────────────────────────────────────────────────────────────────────────
# CommandArgumentParser — parse: flags
# ─────────────────────────────────────────────────────────────────────────────


class TestParseFlags:
    def test_flag_present_sets_true(self):
        args = [Argument(name="--managed", type=ArgumentType.BOOLEAN)]
        parser = CommandArgumentParser(args)

        result = parser.parse("--managed")

        assert result["--managed"] is True

    def test_flag_absent_not_in_result_before_defaults(self):
        args = [Argument(name="--managed", type=ArgumentType.BOOLEAN)]
        parser = CommandArgumentParser(args)

        result = parser.parse("")

        # No default defined; key may be absent or None
        assert result.get("--managed") is None

    def test_flag_with_default_false_applied(self):
        args = [Argument(name="--managed", type=ArgumentType.BOOLEAN, default=False)]
        parser = CommandArgumentParser(args)

        result = parser.parse("")

        assert result["--managed"] is False


# ─────────────────────────────────────────────────────────────────────────────
# CommandArgumentParser — parse: options
# ─────────────────────────────────────────────────────────────────────────────


class TestParseOptions:
    def test_option_parsed_correctly(self):
        args = [Argument(name="--role")]
        parser = CommandArgumentParser(args)

        result = parser.parse("--role admin")

        assert result["--role"] == "admin"

    def test_option_missing_value_raises(self):
        args = [Argument(name="--role")]
        parser = CommandArgumentParser(args)

        with pytest.raises(ArgumentParsingError) as exc_info:
            parser.parse("--role")

        assert "--role" in str(exc_info.value)

    def test_unknown_option_raises(self):
        parser = CommandArgumentParser([])

        with pytest.raises(ArgumentParsingError) as exc_info:
            parser.parse("--unknown value")

        assert "Unknown option" in str(exc_info.value)

    def test_alias_resolves_to_canonical(self):
        args = [Argument(name="--role", aliases=["-r"])]
        parser = CommandArgumentParser(args)

        result = parser.parse("-r admin")

        assert result["--role"] == "admin"

    def test_allow_multiple_collects_list(self):
        args = [Argument(name="--tag", allow_multiple=True)]
        parser = CommandArgumentParser(args)

        result = parser.parse("--tag alpha --tag beta")

        assert result["--tag"] == ["alpha", "beta"]

    def test_option_default_applied_when_absent(self):
        args = [Argument(name="--env", default="production")]
        parser = CommandArgumentParser(args)

        result = parser.parse("")

        assert result["--env"] == "production"


# ─────────────────────────────────────────────────────────────────────────────
# CommandArgumentParser — parse: positional
# ─────────────────────────────────────────────────────────────────────────────


class TestParsePositional:
    def test_positional_parsed_correctly(self):
        args = [Argument(name="group_id")]
        parser = CommandArgumentParser(args)

        result = parser.parse("grp-123")

        assert result["group_id"] == "grp-123"

    def test_too_many_positional_raises(self):
        args = [Argument(name="group_id")]
        parser = CommandArgumentParser(args)

        with pytest.raises(ArgumentParsingError) as exc_info:
            parser.parse("grp-123 extra")

        assert "Too many positional" in str(exc_info.value)

    def test_required_positional_missing_raises(self):
        args = [Argument(name="group_id", required=True)]
        parser = CommandArgumentParser(args)

        with pytest.raises(ArgumentParsingError):
            parser.parse("")

    def test_positional_with_quoted_value(self):
        args = [Argument(name="title")]
        parser = CommandArgumentParser(args)

        result = parser.parse('"My Title"')

        assert result["title"] == "My Title"


# ─────────────────────────────────────────────────────────────────────────────
# CommandArgumentParser — type validation
# ─────────────────────────────────────────────────────────────────────────────


class TestTypeValidation:
    def test_email_type_accepts_valid_email(self):
        args = [Argument(name="email", type=ArgumentType.EMAIL)]
        parser = CommandArgumentParser(args)

        result = parser.parse("user@example.com")

        assert result["email"] == "user@example.com"

    def test_email_type_rejects_invalid_email(self):
        args = [Argument(name="email", type=ArgumentType.EMAIL)]
        parser = CommandArgumentParser(args)

        with pytest.raises(ArgumentParsingError):
            parser.parse("not-an-email")

    def test_integer_type_accepts_valid_int(self):
        args = [Argument(name="--count", type=ArgumentType.INTEGER)]
        parser = CommandArgumentParser(args)

        result = parser.parse("--count 42")

        assert result["--count"] == 42

    def test_integer_type_rejects_non_int(self):
        args = [Argument(name="--count", type=ArgumentType.INTEGER)]
        parser = CommandArgumentParser(args)

        with pytest.raises(ArgumentParsingError):
            parser.parse("--count abc")

    def test_choice_type_accepts_valid_choice(self):
        args = [
            Argument(name="--role", type=ArgumentType.CHOICE, choices=["admin", "user"])
        ]
        parser = CommandArgumentParser(args)

        result = parser.parse("--role admin")

        assert result["--role"] == "admin"

    def test_choice_type_rejects_invalid_choice(self):
        args = [
            Argument(name="--role", type=ArgumentType.CHOICE, choices=["admin", "user"])
        ]
        parser = CommandArgumentParser(args)

        with pytest.raises(ArgumentParsingError):
            parser.parse("--role superuser")

    def test_csv_type_splits_values(self):
        args = [Argument(name="tags", type=ArgumentType.CSV)]
        parser = CommandArgumentParser(args)

        result = parser.parse("alpha,beta,gamma")

        assert result["tags"] == ["alpha", "beta", "gamma"]

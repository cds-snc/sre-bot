"""Unit tests for quote-aware tokenizer.

Tests all quote preservation scenarios including:
- Double quotes, single quotes, backticks
- Escaped quotes
- Mixed quote types
- Whitespace preservation
- Special characters
- Newlines (for multiline justifications)
- Real-world command examples
"""

from infrastructure.platforms.parsing import (
    Argument,
    ArgumentType,
    CommandArgumentParser,
)


class TestTokenizer:
    """Test quote-aware tokenization with full preservation."""

    def test_tokenize_double_quotes(self):
        """Test double-quoted values are preserved."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse('--message "Hello world"')
        assert result["--message"] == "Hello world"

    def test_tokenize_single_quotes(self):
        """Test single-quoted values are preserved."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse("--message 'Hello world'")
        assert result["--message"] == "Hello world"

    def test_tokenize_backticks(self):
        """Test backtick-quoted values are preserved."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse("--message `Hello world`")
        assert result["--message"] == "Hello world"

    def test_tokenize_escaped_quotes(self):
        """Test escaped quotes inside quoted strings."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse('--message "He said \\"hello\\" to me"')
        assert result["--message"] == 'He said "hello" to me'

    def test_tokenize_mixed_quotes(self):
        """Test mixed quote types."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse("""--message "He said 'hello' to me" """)
        assert result["--message"] == "He said 'hello' to me"

    def test_tokenize_multiple_spaces_in_quotes(self):
        """Test multiple spaces preserved in quoted values."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse('--message "Hello    world"')
        assert result["--message"] == "Hello    world"  # 4 spaces preserved

    def test_tokenize_special_characters_in_quotes(self):
        """Test special characters preserved in quotes."""
        parser = CommandArgumentParser(
            [Argument(name="--justification", type=ArgumentType.STRING)]
        )
        result = parser.parse('--justification "Emergency: incident #123 (critical!)"')
        assert result["--justification"] == "Emergency: incident #123 (critical!)"

    def test_tokenize_newlines_in_quotes(self):
        """Test newlines preserved in quoted values."""
        parser = CommandArgumentParser(
            [Argument(name="--justification", type=ArgumentType.STRING)]
        )
        result = parser.parse('--justification "Line 1\nLine 2\nLine 3"')
        assert result["--justification"] == "Line 1\nLine 2\nLine 3"

    def test_real_world_groups_add_command(self):
        """Test actual groups add command with quoted justification."""
        parser = CommandArgumentParser(
            [
                Argument(
                    name="member_email",
                    type=ArgumentType.EMAIL,
                    required=True,
                ),
                Argument(
                    name="group_id",
                    type=ArgumentType.STRING,
                    required=True,
                ),
                Argument(
                    name="provider",
                    type=ArgumentType.CHOICE,
                    choices=["aws", "google"],
                    required=True,
                ),
                Argument(
                    name="--justification",
                    type=ArgumentType.STRING,
                    required=True,
                ),
            ]
        )

        # This is the actual command format users will enter
        result = parser.parse(
            'user@example.com my-group aws --justification "Emergency access for incident #123"'
        )

        assert result["member_email"] == "user@example.com"
        assert result["group_id"] == "my-group"
        assert result["provider"] == "aws"
        assert result["--justification"] == "Emergency access for incident #123"

    def test_tokenize_tabs_in_quotes(self):
        """Test tabs and mixed whitespace preserved in quotes."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse('--message "Hello\t\tworld"')
        assert result["--message"] == "Hello\t\tworld"

    def test_tokenize_empty_quoted_string(self):
        """Test empty quoted strings are preserved as empty strings."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse('--message ""')
        assert result["--message"] == ""

    def test_tokenize_multiple_quoted_values(self):
        """Test multiple quoted arguments in one command."""
        parser = CommandArgumentParser(
            [
                Argument(name="--first", type=ArgumentType.STRING),
                Argument(name="--second", type=ArgumentType.STRING),
            ]
        )
        result = parser.parse('--first "First value" --second "Second value"')
        assert result["--first"] == "First value"
        assert result["--second"] == "Second value"

    def test_tokenize_quotes_at_end(self):
        """Test quoted value at end of command."""
        parser = CommandArgumentParser(
            [
                Argument(name="group_id", type=ArgumentType.STRING),
                Argument(name="--reason", type=ArgumentType.STRING),
            ]
        )
        result = parser.parse('my-group --reason "End of line"')
        assert result["group_id"] == "my-group"
        assert result["--reason"] == "End of line"

    def test_tokenize_adjacent_quoted_values(self):
        """Test adjacent quoted values (edge case)."""
        parser = CommandArgumentParser(
            [Argument(name="--message", type=ArgumentType.STRING)]
        )
        result = parser.parse('--message "first""second"')
        # Adjacent quotes should produce "firstsecond"
        assert result["--message"] == "firstsecond"

    def test_tokenize_url_with_special_chars(self):
        """Test URL with special characters in quotes."""
        parser = CommandArgumentParser(
            [Argument(name="--url", type=ArgumentType.STRING)]
        )
        result = parser.parse('--url "https://example.com/path?query=value&other=123"')
        assert result["--url"] == "https://example.com/path?query=value&other=123"

    def test_tokenize_json_in_quotes(self):
        """Test JSON-like content in quotes."""
        parser = CommandArgumentParser(
            [Argument(name="--data", type=ArgumentType.STRING)]
        )
        result = parser.parse('--data \'{"key": "value", "nested": {"item": "test"}}\'')
        assert result["--data"] == '{"key": "value", "nested": {"item": "test"}}'

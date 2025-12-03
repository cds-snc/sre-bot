"""Integration tests for quote preservation through command router."""

import pytest
import shlex

from infrastructure.commands.router import CommandRouter


@pytest.fixture
def command_router():
    """Create a CommandRouter for testing."""
    return CommandRouter(namespace="test")


class TestRouterQuotePreservation:
    """Tests for quote preservation through router."""

    def test_requote_tokens_method_directly(self, command_router):
        """Test the _requote_tokens method directly with various inputs."""
        # Tokens with spaces need quoting
        tokens = [
            "add",
            "user@example.com",
            "my group",
            "provider",
            "test justification",
        ]
        result = command_router._requote_tokens(tokens)

        # Should have quotes around tokens with spaces
        assert '"my group"' in result or "'my group'" in result
        assert '"test justification"' in result or "'test justification'" in result
        # Should NOT have quotes around tokens without spaces
        assert result.startswith("add ")
        assert "user@example.com" in result

    def test_requote_tokens_with_special_chars(self, command_router):
        """Test _requote_tokens with special shell characters."""
        tokens = ["add", "group", "reason: |&;<>()$`"]
        result = command_router._requote_tokens(tokens)

        # Should quote token with special chars
        assert any(c in result for c in ['"', "'"])

    def test_requote_tokens_without_spaces(self, command_router):
        """Test _requote_tokens with tokens that don't need quoting."""
        tokens = ["add", "user@example.com", "mygroup", "provider"]
        result = command_router._requote_tokens(tokens)

        # Should return simple join without extra quotes
        expected = "add user@example.com mygroup provider"
        assert result == expected

    def test_requote_tokens_preserves_token_count(self, command_router):
        """Test that _requote_tokens preserves token count through re-tokenization.

        This is the critical test that verifies the fix:
        - We tokenize once (in router to extract subcommand)
        - We re-quote tokens (using _requote_tokens)
        - We re-tokenize (in provider)
        - The final tokens should have same count and content
        """
        original_tokens = [
            "add",
            "user@example.com",
            "my group",
            "provider",
            "test justification",
        ]

        # Re-quote the tokens (what the router does)
        requoted = command_router._requote_tokens(original_tokens)

        # Re-tokenize (what the provider does)
        retokenized = shlex.split(requoted, posix=True)

        # Should have same number of tokens with same semantic meaning
        assert len(retokenized) == len(original_tokens), (
            f"Token count mismatch: {len(retokenized)} != {len(original_tokens)}. "
            f"Requoted: {requoted!r}"
        )
        assert retokenized[0] == "add"
        assert retokenized[1] == "user@example.com"
        assert retokenized[2] == "my group"
        assert retokenized[3] == "provider"
        assert retokenized[4] == "test justification"

    def test_requote_tokens_complex_quoted_args(self, command_router):
        """Test _requote_tokens with complex quoted arguments."""
        # Simulate what happens when router extracts tokens from:
        # 'groups add user@example.com "aws admins" provider "reason: added for audit"'
        tokens = [
            "add",
            "user@example.com",
            "aws admins",
            "provider",
            "reason: added for audit",
        ]

        requoted = command_router._requote_tokens(tokens)
        retokenized = shlex.split(requoted, posix=True)

        assert len(retokenized) == 5
        assert retokenized[2] == "aws admins"
        assert retokenized[4] == "reason: added for audit"

    def test_requote_tokens_empty_list(self, command_router):
        """Test _requote_tokens with empty token list."""
        tokens = []
        result = command_router._requote_tokens(tokens)
        assert result == ""

    def test_requote_tokens_single_token(self, command_router):
        """Test _requote_tokens with single token."""
        tokens = ["add"]
        result = command_router._requote_tokens(tokens)
        assert result == "add"

    def test_requote_tokens_quotes_in_value(self, command_router):
        """Test _requote_tokens when token contains quotes."""
        # Value with internal quotes should be handled correctly
        tokens = ["add", 'value with "quotes"']
        result = command_router._requote_tokens(tokens)
        retokenized = shlex.split(result, posix=True)

        # The retokenized value should preserve the internal quotes
        assert len(retokenized) == 2
        assert retokenized[0] == "add"
        # The exact format depends on shlex.quote behavior
        assert '"quotes"' in retokenized[1] or "'quotes'" in retokenized[1]

    def test_fix_end_to_end_simulation(self, command_router):
        """Simulate the complete flow that was broken before the fix.

        Before the fix:
        1. Original: 'groups add user@example.com mygroup provider "test justification"'
        2. Router tokenizes: ['groups', 'add', 'user@example.com', 'mygroup', 'provider', 'test justification']
        3. Router joins tokens[1:]: 'add user@example.com mygroup provider test justification' ← WRONG, quotes lost!
        4. Provider tokenizes: ['add', 'user@example.com', 'mygroup', 'provider', 'test', 'justification']
        5. Parse error: Extra arguments (7 total tokens, 6 expected)

        After the fix:
        1. Original: 'groups add user@example.com mygroup provider "test justification"'
        2. Router tokenizes: ['groups', 'add', 'user@example.com', 'mygroup', 'provider', 'test justification']
        3. Router requotes tokens[1:]: 'add user@example.com mygroup provider "test justification"' ← CORRECT!
        4. Provider tokenizes: ['add', 'user@example.com', 'mygroup', 'provider', 'test justification']
        5. Success: 5 tokens as expected (after subcommand removed)
        """
        # Simulate what router receives from Slack
        original_text = (
            'groups add user@example.com mygroup provider "test justification"'
        )

        # Step 1: Router tokenizes (first tokenization)
        initial_tokens = shlex.split(original_text, posix=True)
        assert initial_tokens == [
            "groups",
            "add",
            "user@example.com",
            "mygroup",
            "provider",
            "test justification",
        ], "Initial tokenization failed"

        # Step 2: Router applies fix - re-quote tokens[1:]
        requoted = command_router._requote_tokens(initial_tokens[1:])

        # Step 3: Provider receives re-quoted text and tokenizes again
        provider_tokens = shlex.split(requoted, posix=True)

        # Step 4: Verify tokens are correct (5 tokens after subcommand removed, not 7)
        # Before fix: would be ['add', 'user@example.com', 'mygroup', 'provider', 'test', 'justification']
        # After fix:  is    ['add', 'user@example.com', 'mygroup', 'provider', 'test justification']
        assert (
            len(provider_tokens) == 5
        ), f"Expected 5 tokens, got {len(provider_tokens)}: {provider_tokens}"
        assert provider_tokens[0] == "add"
        assert provider_tokens[1] == "user@example.com"
        assert provider_tokens[2] == "mygroup"
        assert provider_tokens[3] == "provider"
        assert (
            provider_tokens[4] == "test justification"
        )  # CRITICAL: This must be ONE token

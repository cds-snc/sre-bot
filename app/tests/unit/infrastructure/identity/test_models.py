"""Tests for infrastructure.identity.models module."""

import pytest

from infrastructure.identity.models import IdentitySource, SlackUser, User


class TestIdentitySource:
    """Test suite for IdentitySource enum."""

    def test_identity_source_values(self):
        """Test IdentitySource enum has expected values."""
        assert IdentitySource.SLACK.value == "slack"
        assert IdentitySource.API_JWT.value == "api_jwt"
        assert IdentitySource.WEBHOOK.value == "webhook"
        assert IdentitySource.SYSTEM.value == "system"

    def test_identity_source_from_string(self):
        """Test IdentitySource can be created from string value."""
        source = IdentitySource("slack")
        assert source == IdentitySource.SLACK

    def test_identity_source_comparison(self):
        """Test IdentitySource enum comparison."""
        assert IdentitySource.SLACK == IdentitySource.SLACK
        assert IdentitySource.SLACK != IdentitySource.API_JWT


class TestUser:
    """Test suite for User model."""

    def test_user_creation_with_all_fields(self):
        """Test User can be created with all fields."""
        user = User(
            user_id="user123",
            email="test@example.com",
            display_name="Test User",
            source=IdentitySource.SLACK,
            platform_id="U123ABC",
            permissions=["read", "write"],
            metadata={"team": "engineering"},
        )

        assert user.user_id == "user123"
        assert user.email == "test@example.com"
        assert user.display_name == "Test User"
        assert user.source == IdentitySource.SLACK
        assert user.platform_id == "U123ABC"
        assert user.permissions == ["read", "write"]
        assert user.metadata == {"team": "engineering"}

    def test_user_creation_with_defaults(self):
        """Test User handles optional fields with defaults."""
        user = User(
            user_id="user123",
            email="test@example.com",
            display_name="Test User",
            source=IdentitySource.SYSTEM,
            platform_id="system",
        )

        assert user.permissions == []
        assert user.metadata == {}

    def test_user_validation_required_fields(self):
        """Test User validation requires all required fields."""
        with pytest.raises(ValueError):
            User(
                user_id="user123",
                email="test@example.com",
                # Missing display_name, source, platform_id
                source=IdentitySource.SLACK,
                platform_id="U123",
            )

    def test_user_dict_conversion(self):
        """Test User can be converted to dict."""
        user = User(
            user_id="user123",
            email="test@example.com",
            display_name="Test User",
            source=IdentitySource.SLACK,
            platform_id="U123ABC",
            permissions=["read"],
            metadata={"key": "value"},
        )

        user_dict = user.model_dump()
        assert user_dict["user_id"] == "user123"
        assert user_dict["email"] == "test@example.com"
        assert user_dict["source"] == "slack"  # Enum value

    def test_user_json_schema(self):
        """Test User generates valid JSON schema."""
        schema = User.model_json_schema()
        assert "properties" in schema
        assert "user_id" in schema["properties"]
        assert "email" in schema["properties"]
        assert "display_name" in schema["properties"]


class TestSlackUser:
    """Test suite for SlackUser model."""

    def test_slack_user_creation_with_all_fields(self):
        """Test SlackUser can be created with all fields."""
        user = SlackUser(
            user_id="test@example.com",
            email="test@example.com",
            display_name="Test User",
            source=IdentitySource.SLACK,
            platform_id="U123ABC",
            slack_user_id="U123ABC",
            slack_team_id="T456DEF",
            slack_user_name="testuser",
            permissions=["read"],
            metadata={"slack_team": "T456DEF"},
        )

        assert user.user_id == "test@example.com"
        assert user.slack_user_id == "U123ABC"
        assert user.slack_team_id == "T456DEF"
        assert user.slack_user_name == "testuser"

    def test_slack_user_creation_with_defaults(self):
        """Test SlackUser handles optional Slack fields with defaults."""
        user = SlackUser(
            user_id="test@example.com",
            email="test@example.com",
            display_name="Test User",
            source=IdentitySource.SLACK,
            platform_id="U123ABC",
            slack_user_id="U123ABC",
        )

        assert user.slack_team_id == ""
        assert user.slack_user_name == ""
        assert user.permissions == []
        assert user.metadata == {}

    def test_slack_user_inherits_from_user(self):
        """Test SlackUser inherits User functionality."""
        user = SlackUser(
            user_id="test@example.com",
            email="test@example.com",
            display_name="Test User",
            source=IdentitySource.SLACK,
            platform_id="U123ABC",
            slack_user_id="U123ABC",
            permissions=["admin"],
        )

        # Verify inherited fields
        assert isinstance(user, User)
        assert user.user_id == "test@example.com"
        assert user.permissions == ["admin"]

    def test_slack_user_dict_conversion(self):
        """Test SlackUser can be converted to dict."""
        user = SlackUser(
            user_id="test@example.com",
            email="test@example.com",
            display_name="Test User",
            source=IdentitySource.SLACK,
            platform_id="U123ABC",
            slack_user_id="U123ABC",
            slack_team_id="T456DEF",
            slack_user_name="testuser",
        )

        user_dict = user.model_dump()
        assert user_dict["slack_user_id"] == "U123ABC"
        assert user_dict["slack_team_id"] == "T456DEF"
        assert user_dict["slack_user_name"] == "testuser"

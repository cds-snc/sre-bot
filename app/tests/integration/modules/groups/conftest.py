"""
Module-level conftest.py for groups integration tests.

Provides groups-specific fixtures for integration testing:
- Group factory instances
- Member factory instances
- Provider-specific mocks
- Module configuration

These fixtures extend the root-level integration test fixtures
and provide groups-module-specific test data and mocks.
"""

import pytest
from unittest.mock import MagicMock


# ============================================================================
# Groups Module Fixtures
# ============================================================================


@pytest.fixture
def groups_module():
    """Import the groups service module.

    Returns:
        module: Loaded groups module
    """
    from modules.groups.core import service

    return service


@pytest.fixture
def groups_orchestration():
    """Import the orchestration module.

    Returns:
        module: Loaded orchestration module
    """
    from modules.groups.core import orchestration

    return orchestration


@pytest.fixture
def groups_validation():
    """Import the validation module.

    Returns:
        module: Loaded validation module
    """
    from modules.groups.domain import validation

    return validation


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_group():
    """Provide a test group object.

    Returns:
        Dict: Test group data
    """
    return {
        "id": "test-group-123",
        "email": "test-group@example.com",
        "name": "Test Group",
        "description": "Integration test group",
        "provider": "google",
        "canonical_id": "canonical-test-group-123",
    }


@pytest.fixture
def test_member():
    """Provide a test member object.

    Returns:
        Dict: Test member data
    """
    return {
        "email": "testuser@example.com",
        "first_name": "Test",
        "last_name": "User",
        "role": "member",
    }


@pytest.fixture
def test_members_list():
    """Provide a list of test members.

    Returns:
        List[Dict]: Multiple test member objects
    """
    return [
        {
            "email": "user1@example.com",
            "first_name": "User",
            "last_name": "One",
            "role": "member",
        },
        {
            "email": "user2@example.com",
            "first_name": "User",
            "last_name": "Two",
            "role": "manager",
        },
        {
            "email": "user3@example.com",
            "first_name": "User",
            "last_name": "Three",
            "role": "member",
        },
    ]


@pytest.fixture
def test_groups_list():
    """Provide a list of test groups.

    Returns:
        List[Dict]: Multiple test group objects
    """
    return [
        {
            "id": "group-1",
            "email": "team-a@example.com",
            "name": "Team A",
            "provider": "google",
            "canonical_id": "canonical-1",
        },
        {
            "id": "group-2",
            "email": "team-b@example.com",
            "name": "Team B",
            "provider": "google",
            "canonical_id": "canonical-2",
        },
        {
            "id": "group-3",
            "email": "team-c@example.com",
            "name": "Team C",
            "provider": "aws",
            "canonical_id": "canonical-3",
        },
    ]


# ============================================================================
# Multi-Provider Test Data
# ============================================================================


@pytest.fixture
def google_test_group():
    """Google-specific test group.

    Returns:
        Dict: Google group data
    """
    return {
        "id": "google-group-123",
        "email": "google-team@example.com",
        "name": "Google Team",
        "description": "Integration test group on Google",
        "provider": "google",
        "canonical_id": "canonical-google-123",
        "members_count": 5,
    }


@pytest.fixture
def aws_test_group():
    """AWS-specific test group.

    Returns:
        Dict: AWS group data
    """
    return {
        "id": "aws-group-456",
        "name": "aws-team",
        "description": "Integration test group on AWS",
        "provider": "aws",
        "canonical_id": "canonical-aws-456",
        "members_count": 3,
    }


@pytest.fixture
def google_member_email():
    """Google member email for testing.

    Returns:
        str: Test email address
    """
    return "newmember@example.com"


@pytest.fixture
def aws_member_id():
    """AWS member ID for testing.

    Returns:
        str: Test AWS member ID
    """
    return "aws-member-789"


# ============================================================================
# Operation Test Data
# ============================================================================


@pytest.fixture
def add_member_request():
    """Test request for adding a member.

    Returns:
        Dict: Add member request parameters
    """
    return {
        "group_id": "test-group-123",
        "member_email": "newmember@example.com",
        "provider": "google",
        "justification": "User onboarding requires system access",
    }


@pytest.fixture
def remove_member_request():
    """Test request for removing a member.

    Returns:
        Dict: Remove member request parameters
    """
    return {
        "group_id": "test-group-123",
        "member_email": "member@example.com",
        "provider": "google",
        "justification": "User offboarding requires access revocation",
    }


@pytest.fixture
def bulk_operations_request():
    """Test request for bulk operations.

    Returns:
        Dict: Bulk operations request parameters
    """
    return {
        "operations": [
            {
                "action": "add_member",
                "group_id": "group-1",
                "member_email": "user1@example.com",
                "provider": "google",
                "justification": "Team member onboarding for project",
            },
            {
                "action": "add_member",
                "group_id": "group-2",
                "member_email": "user2@example.com",
                "provider": "google",
                "justification": "Team member onboarding for project",
            },
            {
                "action": "remove_member",
                "group_id": "group-3",
                "member_email": "user3@example.com",
                "provider": "aws",
                "justification": "Team member offboarding from project",
            },
        ]
    }


# ============================================================================
# Expected Response Fixtures
# ============================================================================


@pytest.fixture
def successful_add_response():
    """Expected response for successful add_member operation.

    Returns:
        Dict: Expected successful response
    """
    return {
        "success": True,
        "status": "success",
        "operation_id": "op-123",
        "group_id": "test-group-123",
        "member_email": "newmember@example.com",
        "provider": "google",
        "timestamp": "2025-11-04T10:00:00Z",
    }


@pytest.fixture
def successful_remove_response():
    """Expected response for successful remove_member operation.

    Returns:
        Dict: Expected successful response
    """
    return {
        "success": True,
        "status": "success",
        "operation_id": "op-124",
        "group_id": "test-group-123",
        "member_email": "member@example.com",
        "provider": "google",
        "timestamp": "2025-11-04T10:00:00Z",
    }


@pytest.fixture
def error_response():
    """Expected response for failed operation.

    Returns:
        Dict: Expected error response
    """
    return {
        "status": "error",
        "error_code": "member_not_found",
        "message": "Member not found in group",
        "group_id": "test-group-123",
        "member_email": "nonexistent@example.com",
        "provider": "google",
    }


# ============================================================================
# Mock Capture Fixtures
# ============================================================================


@pytest.fixture
def captured_operations():
    """Capture orchestration operations during test.

    Returns:
        List: List to capture orchestration operations
    """
    return []


@pytest.fixture
def captured_events():
    """Capture dispatched events during test.

    Returns:
        List: List to capture events
    """
    return []


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def integration_settings():
    """Integration test configuration.

    Returns:
        Dict: Test configuration values
    """
    return {
        "timeout": 30,
        "retry_count": 3,
        "enable_events": True,
        "enable_logging": True,
    }


@pytest.fixture
def mock_logger(monkeypatch):
    """Mock logger for integration tests.

    Returns:
        MagicMock: Mock logger
    """
    logger = MagicMock()
    return logger


# ============================================================================
# Provider Setup Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def mock_sentinel_and_activate_providers(monkeypatch, mock_sentinel_client):
    """Mock Sentinel client and activate test providers for integration testing.

    Sets up:
    - Sentinel client mock to prevent external API calls
    - Google (primary) and AWS (secondary) mock providers

    This fixture runs automatically (autouse=True) for all integration tests.
    """
    from unittest.mock import MagicMock
    from modules.groups import providers as providers_module

    # Create mock primary provider (google)
    mock_google = MagicMock()
    mock_google.prefix = "g"
    mock_google.primary = True
    mock_google.is_manager = MagicMock(return_value=True)
    mock_google.add_member = MagicMock()
    mock_google.remove_member = MagicMock()
    mock_google.get_group_members = MagicMock()

    # Create mock secondary provider (aws)
    mock_aws = MagicMock()
    mock_aws.prefix = "aws"
    mock_aws.primary = False
    mock_aws.add_member = MagicMock()
    mock_aws.remove_member = MagicMock()
    mock_aws.get_group_members = MagicMock()

    # Mock provider registry
    mock_registry = {
        "google": mock_google,
        "aws": mock_aws,
    }

    # Patch provider functions
    monkeypatch.setattr(
        providers_module,
        "get_active_providers",
        lambda: mock_registry,
    )
    monkeypatch.setattr(
        providers_module,
        "get_primary_provider",
        lambda: mock_google,
    )
    monkeypatch.setattr(
        providers_module,
        "get_primary_provider_name",
        lambda: "google",
    )

    return {
        "google": mock_google,
        "aws": mock_aws,
        "registry": mock_registry,
        "sentinel": mock_sentinel_client,
    }


# ============================================================================
# Test Markers
# ============================================================================


def pytest_configure(config):
    """Register groups-specific markers."""
    config.addinivalue_line(
        "markers",
        "integration_groups: mark test as groups module integration test",
    )
    config.addinivalue_line(
        "markers",
        "integration_service: mark test as service integration test",
    )
    config.addinivalue_line(
        "markers",
        "integration_orchestration: mark test as orchestration integration test",
    )
    config.addinivalue_line(
        "markers",
        "integration_providers: mark test as provider integration test",
    )

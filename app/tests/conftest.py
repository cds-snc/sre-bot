import sys
import logging
from typing import Any, Optional
import pytest


# Ensure project root is on path BEFORE importing test factories.
project_root = "/workspace/app"
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tests.factories.google import (  # noqa: E402
    make_google_groups,
    make_google_members,
    make_google_users,
)
from tests.factories.aws import (  # noqa: E402
    make_aws_users,
    make_aws_groups,
    make_aws_groups_memberships,
    make_aws_groups_w_users,
    make_aws_groups_w_users_with_legacy,
)
from tests.factories.commands import (  # noqa: E402
    make_argument,
    make_command,
    make_command_context,
)

# Ensure the application package root is on sys.path so importing application
# modules (e.g. `core.config`) works during pytest collection. Pytest may
# import `conftest` before the project root is on sys.path depending on
# invocation; add it explicitly here before importing application modules.
# pylint: disable=wrong-import-position


def pytest_configure(config):
    """Hook called after command line options have been parsed.

    Mock Slack App initialization BEFORE any modules are imported to prevent
    auth errors during test collection when main.py is imported and tries to
    instantiate the Slack App at module load time.
    """
    from unittest.mock import MagicMock

    # Create a mock that allows all attribute access and method calls
    def mock_app_init(self, *args, **kwargs):
        """Mock App.__init__ to skip auth_test."""
        # Initialize minimal required attributes without calling auth_test
        self._token = kwargs.get("token")
        self._client = MagicMock()
        self._client.auth_test = MagicMock(
            return_value={"ok": True, "user_id": "U12345"}
        )
        self.command = MagicMock()
        self.view = MagicMock()
        self.action = MagicMock()
        self.event = MagicMock()
        self.middleware = MagicMock()
        self.add_middleware = MagicMock()
        self.add_event_handler = MagicMock()

    # Patch before any imports
    import slack_bolt

    slack_bolt.App.__init__ = mock_app_init


@pytest.fixture(autouse=True)
def suppress_structlog_output():
    """Suppress structlog output during tests.

    Note: Logging is now primarily suppressed in core.logging.configure_logging()
    when pytest is detected. This fixture provides additional belt-and-suspenders
    suppression and can be used for test-specific logging control if needed.
    """
    # Additional suppression as backup (core.logging already handles this)
    root_logger = logging.getLogger()
    original_level = root_logger.level

    # Ensure root logger suppresses all output
    if original_level < logging.CRITICAL + 1:
        root_logger.setLevel(logging.CRITICAL + 1)

    yield

    # Restore original level after test
    root_logger.setLevel(original_level)


@pytest.fixture
def reset_provider_registries(monkeypatch):
    """Reset provider registries to clean state between tests.

    Use this fixture when tests manipulate provider registration to ensure
    isolation. Not autouse to avoid overhead for tests that don't need it.
    """
    import modules.groups.providers as providers

    baseline_primary_discovered = dict(providers._primary_discovered)
    baseline_primary_active = providers._primary_active
    baseline_secondary_discovered = dict(providers._secondary_discovered)
    baseline_secondary_active = dict(providers._secondary_active)

    try:
        yield
    finally:
        providers._primary_discovered.clear()
        providers._primary_discovered.update(baseline_primary_discovered)
        providers._primary_active = baseline_primary_active
        providers._secondary_discovered.clear()
        providers._secondary_discovered.update(baseline_secondary_discovered)
        providers._secondary_active.clear()
        providers._secondary_active.update(baseline_secondary_active)


@pytest.fixture
def mock_provider_config():
    """Factory for creating provider configuration dictionaries.

    Returns a function that generates provider config dicts with
    sensible defaults for testing configuration-driven activation.

    Usage:
        config = mock_provider_config(
            provider_name="google",
            enabled=True,
            primary=True,
            prefix="g",
            capabilities={"supports_member_management": True}
        )
    """

    def _factory(
        provider_name: str,
        enabled: bool = True,
        primary: bool = False,
        prefix: Optional[str] = None,
        capabilities: Optional[dict] = None,
    ) -> dict:
        config: dict[str, Any] = {"enabled": enabled}

        if primary:
            config["primary"] = True

        if prefix:
            config["prefix"] = prefix

        if capabilities:
            config["capabilities"] = capabilities

        return {provider_name: config}

    return _factory


@pytest.fixture
def single_provider_config(mock_provider_config):
    """Provider configuration with single enabled primary provider.

    Returns:
        dict: Configuration for a single Google Workspace provider
    """
    return mock_provider_config(
        provider_name="google",
        enabled=True,
        primary=True,
        capabilities={"supports_member_management": True, "provides_role_info": True},
    )


@pytest.fixture
def multi_provider_config(mock_provider_config):
    """Provider configuration with multiple enabled providers.

    Returns:
        dict: Configuration for Google (primary) and AWS (secondary) providers
    """
    google_cfg = mock_provider_config(
        provider_name="google",
        enabled=True,
        primary=True,
        capabilities={"supports_member_management": True, "provides_role_info": True},
    )

    aws_cfg = mock_provider_config(
        provider_name="aws",
        enabled=True,
        primary=False,
        prefix="aws",
        capabilities={
            "supports_member_management": True,
            "supports_batch_operations": True,
            "max_batch_size": 100,
        },
    )

    # Merge both configs
    config = {**google_cfg, **aws_cfg}
    return config


@pytest.fixture
def disabled_provider_config(mock_provider_config):
    """Provider configuration with one enabled and one disabled provider.

    Returns:
        dict: Configuration with Google enabled (primary) and AWS disabled
    """
    google_cfg = mock_provider_config(
        provider_name="google", enabled=True, primary=True
    )

    aws_cfg = mock_provider_config(
        provider_name="aws", enabled=False, prefix="aws"  # Explicitly disabled
    )

    config = {**google_cfg, **aws_cfg}
    return config


# Google API Python Client


# Google Discovery Directory Resource
# Legacy Fixtures
@pytest.fixture
def google_groups():
    def _google_groups(n=3, prefix="", domain="test.com"):
        return [
            {
                "id": f"{prefix}google_group_id{i+1}",
                "name": f"{prefix}group-name{i+1}",
                "email": f"{prefix}group-name{i+1}@{domain}",
                "description": f"{prefix}description{i+1}",
                "directMembersCount": i + 1,
            }
            for i in range(n)
        ]

    return _google_groups


@pytest.fixture
def google_users():
    def _google_users(n=3, prefix="", domain="test.com"):
        users = []
        for i in range(n):
            user = {
                "id": f"{prefix}user_id{i+1}",
                "primaryEmail": f"{prefix}user-email{i+1}@{domain}",
                "emails": [
                    {
                        "address": f"{prefix}user-email{i+1}@{domain}",
                        "primary": True,
                        "type": "work",
                    }
                ],
                "suspended": False,
                "name": {
                    "fullName": f"Given_name_{i+1} Family_name_{i+1}",
                    "familyName": f"Family_name_{i+1}",
                    "givenName": f"Given_name_{i+1}",
                    "displayName": f"Given_name_{i+1} Family_name_{i+1}",
                },
            }
            users.append(user)
        return users

    return _google_users


@pytest.fixture
def google_group_members(google_users):
    def _google_group_members(n=3, prefix="", domain="test.com"):
        users = google_users(n, prefix, domain)
        return [
            {
                "kind": "admin#directory#member",
                "email": user["primaryEmail"],
                "role": "MEMBER",
                "type": "USER",
                "status": "ACTIVE",
                "id": user["id"],
            }
            for user in users
        ]

    return _google_group_members


# Fixture with users
@pytest.fixture
def google_groups_w_users(google_groups, google_group_members, google_users):
    def _google_groups_w_users(
        n_groups=1, n_users=3, group_prefix="", user_prefix="", domain="test.com"
    ):
        groups = google_groups(n_groups, prefix=group_prefix, domain=domain)
        members = google_group_members(n_users, prefix=user_prefix, domain=domain)
        users = google_users(n_users, prefix=user_prefix, domain=domain)

        combined_members = []
        for member, user in zip(members, users):
            combined_member = {**member, **user}
            combined_members.append(combined_member)

        for group in groups:
            group["members"] = combined_members
        return groups

    return _google_groups_w_users


# Additional fixtures for comprehensive testing
@pytest.fixture
def google_groups_with_legacy_structure(
    google_group_factory, google_member_factory, google_user_factory
):
    """Factory to create groups with legacy-compatible member structure."""

    def _factory(n_groups=1, n_members_per_group=2, domain="test.com"):
        groups = google_group_factory(n_groups, domain=domain)
        result = []

        for i, group in enumerate(groups):
            # Create members for this group
            members = google_member_factory(
                n_members_per_group, prefix=f"g{i}-", domain=domain
            )
            users = google_user_factory(
                n_members_per_group, prefix=f"g{i}-", domain=domain
            )

            # Create legacy-compatible members with flattened user details
            legacy_members = []
            for member, user in zip(members, users):
                # Ensure email consistency
                member["email"] = user["primaryEmail"]

                # Create legacy member with flattened user details
                legacy_member = {**member}
                legacy_member["user_details"] = user

                # Flatten user details into top-level member dict (legacy compatibility)
                for k, v in user.items():
                    if k not in legacy_member:
                        legacy_member[k] = v

                legacy_members.append(legacy_member)

            group_with_members = {**group}
            group_with_members["members"] = legacy_members
            result.append(group_with_members)

        return result

    return _factory


# --- Google Directory API Pydantic factories ---


@pytest.fixture
def google_group_factory():
    """
    Factory fixture to generate a list of valid Google Group dicts for tests.
    Usage:
        groups = google_group_factory(n=2, prefix="dev-")
        # returns a list of dicts (model_dump)
    """

    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        # Delegate to shared helper to avoid duplicated logic
        return make_google_groups(n=n, prefix=prefix, domain=domain, as_model=as_model)

    return _factory


@pytest.fixture
def google_user_factory():
    """
    Factory fixture to generate a list of valid Google User dicts or models for tests.
    Usage:
        users = google_user_factory(n=2, prefix="dev-")
        # returns a list of dicts (model_dump)
        users = google_user_factory(n=2, as_model=True)
        # returns a list of User models
    """

    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        # Delegate to shared helper to avoid duplicated logic
        return make_google_users(n=n, prefix=prefix, domain=domain, as_model=as_model)

    return _factory


@pytest.fixture
def google_member_factory():
    """
    Factory fixture to generate a list of valid Google Member dicts or models for tests.
    Usage:
        members = google_member_factory(n=2, prefix="dev-")
        # returns a list of dicts (model_dump)
        members = google_member_factory(n=2, as_model=True)
        # returns a list of Member models
    """

    def _factory(n=3, prefix="", domain="test.com", as_model=False):
        # Delegate to shared helper to avoid duplicated logic
        return make_google_members(n=n, prefix=prefix, domain=domain, as_model=as_model)

    return _factory


@pytest.fixture
def google_batch_response_factory():
    """Factory to create Google API batch response structures."""

    def _factory(success_responses=None, error_responses=None):
        results = {}

        if success_responses:
            results.update(success_responses)

        if error_responses:
            # Add error responses - could be None or error objects
            results.update(error_responses)

        return {"results": results}

    return _factory


# AWS API fixtures


@pytest.fixture
def aws_users():
    # Delegate to factory implementation
    def _wrapper(n=3, prefix="", domain="test.com", store_id="d-123412341234"):
        return make_aws_users(n=n, prefix=prefix, domain=domain, store_id=store_id)

    return _wrapper


@pytest.fixture
def aws_groups():
    def _wrapper(n=3, prefix="", store_id="d-123412341234"):
        return make_aws_groups(n=n, prefix=prefix, store_id=store_id)

    return _wrapper


@pytest.fixture
def aws_groups_memberships():
    def _wrapper(n=3, prefix="", group_id=1, store_id="d-123412341234"):
        return make_aws_groups_memberships(
            n=n, prefix=prefix, group_id=group_id, store_id=store_id
        )

    return _wrapper


@pytest.fixture
def aws_groups_w_users(aws_groups, aws_users, aws_groups_memberships):
    def _wrapper(
        n_groups=1,
        n_users=3,
        group_prefix="",
        user_prefix="",
        domain="test.com",
        store_id="d-123412341234",
    ):
        return make_aws_groups_w_users(
            n_groups=n_groups,
            n_users=n_users,
            group_prefix=group_prefix,
            user_prefix=user_prefix,
            domain=domain,
            store_id=store_id,
        )

    return _wrapper


@pytest.fixture
def aws_groups_w_users_with_legacy():
    def _wrapper(
        n_groups=1,
        n_users=3,
        group_prefix="",
        user_prefix="",
        domain="test.com",
        store_id="d-123412341234",
    ):
        return make_aws_groups_w_users_with_legacy(
            n_groups=n_groups,
            n_users=n_users,
            group_prefix=group_prefix,
            user_prefix=user_prefix,
            domain=domain,
            store_id=store_id,
        )

    return _wrapper


# --- Command Framework Factories (Level 1 fixtures) ---


@pytest.fixture
def argument_factory():
    """Factory for creating Argument instances."""
    return make_argument


@pytest.fixture
def command_factory():
    """Factory for creating Command instances."""
    return make_command


@pytest.fixture
def command_context_factory():
    """Factory for creating CommandContext instances."""
    return make_command_context


@pytest.fixture
def command_registry_factory():
    """Factory for creating CommandRegistry instances."""
    from infrastructure.commands.registry import CommandRegistry

    def _factory(namespace: str = "test") -> CommandRegistry:
        return CommandRegistry(namespace=namespace)

    return _factory


# --- Settings Mock Factory (Level 1 - for all tests) ---


@pytest.fixture
def make_mock_settings():
    """Factory for creating mock settings with package-specific overrides.

    This factory eliminates duplication of mock settings across different
    test packages. Each package can override specific settings without
    recreating the entire mock.

    Usage:
        def mock_settings(make_mock_settings):
            return make_mock_settings(
                **{
                    'slack.SLACK_TOKEN': 'xoxb-test-token',
                    'commands.providers': {},
                }
            )

    Returns:
        Callable: Factory function that accepts **overrides kwargs
    """
    from unittest.mock import MagicMock

    def _factory(**overrides):
        """Create mock settings with provided overrides."""
        settings = MagicMock()

        # Set common defaults for all packages
        settings.aws.AWS_REGION = "us-east-1"

        # Apply package-specific overrides
        for key, value in overrides.items():
            if "." in key:
                # Handle nested attributes: 'slack.SLACK_TOKEN' -> settings.slack.SLACK_TOKEN
                parts = key.split(".")
                obj = settings
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
            else:
                setattr(settings, key, value)

        return settings

    return _factory

"""Fixtures for AWS client tests.

Provides factory-as-fixture pattern for creating configurable fake boto3 clients
used across AWS client unit tests, following the testing strategy.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from infrastructure.clients.aws import AWSClients
from infrastructure.clients.aws.session_provider import SessionProvider
from infrastructure.configuration.integrations.aws import AwsSettings


class FakePaginator:
    """Fake boto3 paginator that yields provided pages."""

    def __init__(self, pages):
        self._pages = list(pages)

    def paginate(self, **kwargs):
        """Yield pages in sequence."""
        for page in self._pages:
            yield page


class FakeClient:
    """Configurable fake boto3 client for unit tests.

    Supports:
    - Paginated responses via `get_paginator()`
    - API method responses via `__getattr__` lookup
    - Both static and callable response configurations
    """

    def __init__(
        self,
        paginated_pages: Optional[List[Dict[str, Any]]] = None,
        api_responses: Optional[Dict[str, Any]] = None,
        can_paginate: Optional[Any] = None,
    ):
        self._paginated_pages = paginated_pages or []
        self._api_responses = api_responses or {}
        if can_paginate is None:
            self._can_paginate = bool(self._paginated_pages)
        else:
            self._can_paginate = can_paginate

    def get_paginator(self, *args, **kwargs):
        """Return a paginator for the given method name."""
        if not self._paginated_pages:
            raise AttributeError("No paginator available")
        return FakePaginator(self._paginated_pages)

    def __getattr__(self, name: str):
        """Provide callable for API methods that returns configured responses."""
        if name in self._api_responses:
            resp = self._api_responses[name]
            if callable(resp):

                def _call(*_args, **_kwargs):
                    return resp(**_kwargs)

                return _call

            def _call_const(*_args, **_kwargs):
                return resp

            return _call_const

        if self._paginated_pages:

            def _noop(*_args, **_kwargs):
                return {}

            return _noop

        raise AttributeError(name)

    def can_paginate(self, method_name: str) -> bool:
        """Indicate whether paginator is available for this method."""
        if callable(self._can_paginate):
            try:
                return bool(self._can_paginate(method_name))
            except Exception:
                return False
        return bool(self._can_paginate)


@pytest.fixture
def aws_factory(mock_aws_settings):
    """Provide a simple AWSClients instance for unit tests.

    Tests that need to customize boto3 behavior should still monkeypatch
    `infrastructure.clients.aws.executor.get_boto3_client` to return fake
    clients. This fixture centralizes the construction and keeps tests
    consistent with the project's testing strategy.

    Configured with:
    - aws_region: us-east-1
    - default_identity_store_id: store-1234567890 (for Identity Store operations)
    """
    return AWSClients(aws_settings=mock_aws_settings)


@pytest.fixture
def make_fake_client():
    """Factory fixture for creating configurable fake boto3 clients.

    Returns a callable that accepts optional paginated_pages, api_responses,
    and can_paginate parameters and returns a FakeClient configured with
    those values.

    Usage:
        def test_something(make_fake_client):
            client = make_fake_client(paginated_pages=[{...}, {...}])
            monkeypatch.setattr(aws_client, "get_boto3_client", lambda *a, **k: client)
    """

    def _factory(
        paginated_pages: Optional[List[Dict[str, Any]]] = None,
        api_responses: Optional[Dict[str, Any]] = None,
        can_paginate: Optional[Any] = None,
    ) -> FakeClient:
        """Create a FakeClient with the given configuration."""
        return FakeClient(
            paginated_pages=paginated_pages,
            api_responses=api_responses,
            can_paginate=can_paginate,
        )

    return _factory


@pytest.fixture
def mock_aws_settings():
    """Fixture providing a mock AwsSettings instance for testing AWSClients.

    Returns a MagicMock configured with standard AWS settings properties:
    - AWS_REGION: us-east-1
    - INSTANCE_ID: store-1234567890
    - INSTANCE_ARN: arn:aws:sso:::instance/sso-instance-id
    - SERVICE_ROLE_MAP: Dict mapping services to role ARNs
    - ENDPOINT_URL: None (for local/test endpoints)

    Tests can further customize this mock as needed:
        def test_something(mock_aws_settings):
            mock_aws_settings.AWS_REGION = "us-west-2"
            ...
    """
    settings = MagicMock(spec=AwsSettings)
    settings.AWS_REGION = "us-east-1"
    settings.INSTANCE_ID = "store-1234567890"
    settings.INSTANCE_ARN = "arn:aws:sso:::instance/sso-instance-id"
    settings.SERVICE_ROLE_MAP = {
        "dynamodb": "arn:aws:iam::123456789012:role/DynamoDBRole",
        "organizations": "arn:aws:iam::123456789012:role/OrgsRole",
        "sso-admin": "arn:aws:iam::123456789012:role/SSOAdminRole",
        "config": "arn:aws:iam::123456789012:role/ConfigRole",
        "guardduty": "arn:aws:iam::123456789012:role/GuardDutyRole",
        "ce": "arn:aws:iam::123456789012:role/CostExplorerRole",
        "logging": "arn:aws:iam::123456789012:role/LoggingRole",
        "audit": "arn:aws:iam::123456789012:role/AuditRole",
    }
    settings.ENDPOINT_URL = None
    return settings


@pytest.fixture
def dynamodb_client():
    """Fixture for DynamoDBClient with mocked SessionProvider."""
    from infrastructure.clients.aws.dynamodb import DynamoDBClient

    session_provider = SessionProvider(region="us-east-1")
    return DynamoDBClient(
        session_provider=session_provider,
        default_role_arn=None,
    )


@pytest.fixture
def identity_store_client():
    """Fixture for IdentityStoreClient with mocked SessionProvider."""
    from infrastructure.clients.aws.identity_store import IdentityStoreClient

    session_provider = SessionProvider(region="us-east-1")
    return IdentityStoreClient(
        session_provider=session_provider,
        default_identity_store_id="store-1234567890",
    )


@pytest.fixture
def organizations_client():
    """Fixture for OrganizationsClient with mocked SessionProvider."""
    from infrastructure.clients.aws.organizations import OrganizationsClient

    session_provider = SessionProvider(region="us-east-1")
    return OrganizationsClient(
        session_provider=session_provider,
        default_role_arn=None,
    )


@pytest.fixture
def sso_admin_client():
    """Fixture for SsoAdminClient with mocked SessionProvider."""
    from infrastructure.clients.aws.sso_admin import SsoAdminClient

    session_provider = SessionProvider(region="us-east-1")
    return SsoAdminClient(
        session_provider=session_provider,
        default_sso_instance_arn="arn:aws:sso:::instance/sso-instance-id",
    )


@pytest.fixture
def config_client():
    """Fixture for ConfigClient with mocked SessionProvider."""
    from infrastructure.clients.aws.config import ConfigClient

    session_provider = SessionProvider(region="us-east-1")
    return ConfigClient(
        session_provider=session_provider,
        default_role_arn=None,
    )


@pytest.fixture
def guard_duty_client():
    """Fixture for GuardDutyClient with mocked SessionProvider."""
    from infrastructure.clients.aws.guard_duty import GuardDutyClient

    session_provider = SessionProvider(region="us-east-1")
    return GuardDutyClient(
        session_provider=session_provider,
        default_role_arn=None,
    )


@pytest.fixture
def cost_explorer_client():
    """Fixture for CostExplorerClient with mocked SessionProvider."""
    from infrastructure.clients.aws.cost_explorer import CostExplorerClient

    session_provider = SessionProvider(region="us-east-1")
    return CostExplorerClient(
        session_provider=session_provider,
        default_role_arn=None,
    )

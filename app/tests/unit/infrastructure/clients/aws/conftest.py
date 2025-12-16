"""Fixtures for AWS client tests.

Provides factory-as-fixture pattern for creating configurable fake boto3 clients
used across AWS client unit tests, following the testing strategy.
"""

from typing import Any, Dict, List, Optional

import pytest

from infrastructure.clients.aws import AWSClientFactory


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
def aws_factory():
    """Provide a simple AWSClientFactory instance for unit tests.

    Tests that need to customize boto3 behavior should still monkeypatch
    `infrastructure.clients.aws.client.get_boto3_client` to return fake
    clients. This fixture centralizes the construction and keeps tests
    consistent with the project's testing strategy.
    """
    return AWSClientFactory(aws_region="us-east-1")


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

"""Unit tests for the conditional-write store and lease store providers.

The coordination slice is replaced with one built from constructor arguments, so each test
observes that the builder passes the slice's table name and record TTL to the store and the
caller's in-progress TTL in place of the slice's, as plain arguments.
"""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

import infrastructure.coordination.factory as factory_module
from contracts.coordination import ClaimOutcome, ClaimResult, LeaseStore
from infrastructure import coordination
from infrastructure.coordination.dynamodb import DynamoDBConditionalWriteStore
from infrastructure.coordination.factory import build_lease_store, get_lease_store
from infrastructure.coordination.settings import ConditionalWriteSettings

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_get_aws_client(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    dynamodb_client = MagicMock(spec=["put_item", "get_item", "delete_item"])
    get_aws_client = MagicMock(return_value=dynamodb_client)
    monkeypatch.setattr(factory_module, "get_aws_client", get_aws_client, raising=False)
    return get_aws_client, dynamodb_client


@pytest.fixture
def base_settings(monkeypatch: pytest.MonkeyPatch) -> ConditionalWriteSettings:
    base = ConditionalWriteSettings(table_name="leases_elsewhere", record_ttl_seconds=900, in_progress_ttl_seconds=30)
    monkeypatch.setattr("infrastructure.coordination.factory.get_conditional_write_settings", lambda: base)
    return base


@pytest.fixture
def clear_lease_store_cache() -> Iterator[None]:
    get_lease_store.cache_clear()
    yield
    get_lease_store.cache_clear()


@pytest.mark.usefixtures("mock_get_aws_client", "base_settings")
def test_build_conditional_write_store_overrides_in_progress_ttl_only() -> None:
    """The lock's in-progress TTL replaces the slice's; the table and record TTL stay the slice's."""
    build_conditional_write_store = getattr(coordination, "build_conditional_write_store", None)
    assert callable(build_conditional_write_store), "infrastructure.coordination.build_conditional_write_store must be exported"

    store = build_conditional_write_store(in_progress_ttl_seconds=14400)

    assert isinstance(store, DynamoDBConditionalWriteStore)
    assert store.table_name == "leases_elsewhere"
    assert store.record_ttl_seconds == 900
    assert store.in_progress_ttl_seconds == 14400


@pytest.mark.usefixtures("base_settings")
def test_build_lease_store_wraps_a_dynamodb_store_with_the_lease_ttl(mock_get_aws_client) -> None:
    """The lease is acquired through a conditional put whose in-progress expiry uses the lease TTL."""
    _, dynamodb_client = mock_get_aws_client
    dynamodb_client.put_item.return_value = {}

    lease_store = build_lease_store(in_progress_ttl_seconds=14400)

    assert isinstance(lease_store, LeaseStore)
    assert lease_store.acquire("leases:test") is not None
    item = dynamodb_client.put_item.call_args.kwargs["Item"]
    assert int(item["in_progress_expires_at"]["N"]) - int(item["claimed_at"]["N"]) == 14400


@pytest.mark.usefixtures("mock_get_aws_client", "base_settings")
def test_build_lease_store_fails_closed_on_indeterminate_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    """The provider picks FAIL_CLOSED: an INDETERMINATE claim is not acquired."""
    monkeypatch.setattr(DynamoDBConditionalWriteStore, "claim", lambda self, key: ClaimOutcome(result=ClaimResult.INDETERMINATE))

    assert build_lease_store(in_progress_ttl_seconds=600).acquire("leases:test") is None


@pytest.mark.usefixtures("mock_get_aws_client", "base_settings", "clear_lease_store_cache")
class TestGetLeaseStore:
    """Tests for the TTL-parameterized lease store provider."""

    def test_get_lease_store_returns_singleton_per_ttl(self) -> None:
        assert get_lease_store(600) is get_lease_store(600)

    def test_get_lease_store_returns_distinct_instance_for_different_ttl(self) -> None:
        assert get_lease_store(600) is not get_lease_store(1800)

    def test_get_lease_store_returns_a_lease_store(self) -> None:
        assert isinstance(get_lease_store(600), LeaseStore)

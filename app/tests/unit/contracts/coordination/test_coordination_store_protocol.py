"""Tests for the ConditionalWriteStore Protocol contract.

Validates the claim/complete/release Protocol shape, the ClaimResult enum,
the ClaimOutcome value object, and that no vendor (DynamoDB) vocabulary
leaks into the Protocol surface.
"""

import dataclasses
import inspect
import uuid
from typing import Any

import pytest

from contracts.coordination import (
    ClaimOutcome,
    ClaimResult,
    ConditionalWriteStore,
)
from contracts.coordination import store as store_module

pytestmark = pytest.mark.unit


class FakeConditionalWriteStore:
    """Minimal hand-written fake used only to probe Protocol conformance."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}

    def claim(self, key: str):
        record = self._records.get(key)
        if record is None:
            token = uuid.uuid4().hex
            self._records[key] = {"status": "IN_PROGRESS", "outcome": None, "token": token}
            return ClaimOutcome(result=ClaimResult.NEW, claim_token=token)
        if record["status"] == "COMPLETED":
            return ClaimOutcome(result=ClaimResult.COMPLETED, outcome=record["outcome"])
        return ClaimOutcome(result=ClaimResult.IN_PROGRESS)

    def complete(self, key: str, outcome: dict[str, Any], claim_token: str) -> bool:
        if self._records.get(key, {}).get("token") != claim_token:
            return False
        self._records[key] = {"status": "COMPLETED", "outcome": outcome, "token": claim_token}
        return True

    def release(self, key: str, claim_token: str) -> bool:
        record = self._records.get(key, {})
        if record.get("token") != claim_token or record.get("status") != "IN_PROGRESS":
            return False
        del self._records[key]
        return True


class TestConditionalWriteStoreProtocolShape:
    """The Protocol must be runtime-checkable and free of vendor vocabulary."""

    def test_protocol_is_runtime_checkable(self):
        assert isinstance(FakeConditionalWriteStore(), ConditionalWriteStore)

    def test_claim_method_has_no_vendor_parameters(self):
        params = list(inspect.signature(ConditionalWriteStore.claim).parameters)
        assert params == ["self", "key"]

    def test_complete_method_takes_the_claim_token_and_no_vendor_parameters(self):
        params = list(inspect.signature(ConditionalWriteStore.complete).parameters)
        assert params == ["self", "key", "outcome", "claim_token"]

    def test_release_method_takes_the_claim_token_and_no_vendor_parameters(self):
        params = list(inspect.signature(ConditionalWriteStore.release).parameters)
        assert params == ["self", "key", "claim_token"]

    @pytest.mark.parametrize("method", ["complete", "release"])
    def test_claim_token_is_required(self, method):
        """No default, so no caller can skip the ownership check by omission."""
        parameter = inspect.signature(getattr(ConditionalWriteStore, method)).parameters["claim_token"]
        assert parameter.default is inspect.Parameter.empty

    @pytest.mark.parametrize("method", ["complete", "release"])
    def test_ownership_checked_methods_report_whether_they_applied(self, method):
        assert inspect.signature(getattr(ConditionalWriteStore, method)).return_annotation is bool

    @pytest.mark.parametrize(
        "forbidden_term",
        [
            "ConditionExpression",
            "ExpressionAttributeNames",
            "ExpressionAttributeValues",
            "TableName",
            "PartitionKey",
        ],
    )
    def test_protocol_source_has_no_vendor_query_syntax(self, forbidden_term):
        source = inspect.getsource(store_module)
        assert forbidden_term not in source


class TestClaimResult:
    """ClaimResult must expose exactly the three documented outcomes."""

    def test_has_exactly_three_members(self):
        assert {member.name for member in ClaimResult} == {
            "NEW",
            "COMPLETED",
            "IN_PROGRESS",
        }


class TestClaimOutcome:
    """ClaimOutcome is the frozen internal result entity returned by claim()."""

    def test_is_frozen_dataclass(self):
        outcome = ClaimOutcome(result=ClaimResult.NEW)
        assert dataclasses.is_dataclass(outcome)
        with pytest.raises(dataclasses.FrozenInstanceError):
            outcome.result = ClaimResult.COMPLETED  # type: ignore[misc]

    def test_outcome_payload_defaults_to_none(self):
        outcome = ClaimOutcome(result=ClaimResult.NEW)
        assert outcome.outcome is None

    def test_claim_token_defaults_to_none(self):
        outcome = ClaimOutcome(result=ClaimResult.IN_PROGRESS)
        assert outcome.claim_token is None

    def test_claim_token_round_trips_for_new_claims(self):
        outcome = ClaimOutcome(result=ClaimResult.NEW, claim_token="a" * 32)
        assert outcome.claim_token == "a" * 32

    def test_outcome_payload_round_trips_for_completed_claims(self):
        payload = {"status": "ok", "id": 42}
        outcome = ClaimOutcome(result=ClaimResult.COMPLETED, outcome=payload)
        assert outcome.outcome == payload

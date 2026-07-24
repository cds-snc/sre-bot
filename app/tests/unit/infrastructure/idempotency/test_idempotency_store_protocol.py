"""Tests for the IdempotencyStore Protocol contract.

Validates the claim/complete/release Protocol shape, the ClaimResult enum,
the ClaimOutcome value object, and that no vendor (DynamoDB) vocabulary
leaks into the Protocol surface.
"""

import dataclasses
import inspect
from typing import Any

import pytest

from infrastructure.idempotency import protocol
from infrastructure.idempotency.protocol import (
    ClaimOutcome,
    ClaimResult,
    IdempotencyStore,
)

pytestmark = pytest.mark.unit


class FakeIdempotencyStore:
    """Minimal hand-written fake used only to probe Protocol conformance."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}

    def claim(self, key: str):
        record = self._records.get(key)
        if record is None:
            self._records[key] = {"status": "IN_PROGRESS", "outcome": None}
            return ClaimOutcome(result=ClaimResult.NEW)
        if record["status"] == "COMPLETED":
            return ClaimOutcome(result=ClaimResult.COMPLETED, outcome=record["outcome"])
        return ClaimOutcome(result=ClaimResult.IN_PROGRESS)

    def complete(self, key: str, outcome: dict[str, Any]) -> None:
        self._records[key] = {"status": "COMPLETED", "outcome": outcome}

    def release(self, key: str) -> None:
        self._records.pop(key, None)


class TestIdempotencyStoreProtocolShape:
    """The Protocol must be runtime-checkable and free of vendor vocabulary."""

    def test_protocol_is_runtime_checkable(self):
        assert isinstance(FakeIdempotencyStore(), IdempotencyStore)

    def test_claim_method_has_no_vendor_parameters(self):
        params = list(inspect.signature(IdempotencyStore.claim).parameters)
        assert params == ["self", "key"]

    def test_complete_method_has_no_vendor_parameters(self):
        params = list(inspect.signature(IdempotencyStore.complete).parameters)
        assert params == ["self", "key", "outcome"]

    def test_release_method_has_no_vendor_parameters(self):
        params = list(inspect.signature(IdempotencyStore.release).parameters)
        assert params == ["self", "key"]

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
        source = inspect.getsource(protocol)
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

    def test_outcome_payload_round_trips_for_completed_claims(self):
        payload = {"status": "ok", "id": 42}
        outcome = ClaimOutcome(result=ClaimResult.COMPLETED, outcome=payload)
        assert outcome.outcome == payload

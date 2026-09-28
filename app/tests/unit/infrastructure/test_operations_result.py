"""Unit tests for OperationResult and OperationStatus in infrastructure.

Moved from tests/unit/modules/groups/providers/test_base_provider.py (OperationResult/Status parts).
"""

import dataclasses

import pytest

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus


@pytest.mark.unit
class TestOperationStatus:
    def test_operation_status_success(self):
        assert OperationStatus.SUCCESS.value == "success"

    def test_operation_status_transient_error(self):
        assert OperationStatus.TRANSIENT_ERROR.value == "transient_error"

    def test_operation_status_permanent_error(self):
        assert OperationStatus.PERMANENT_ERROR.value == "permanent_error"

    def test_operation_status_unauthorized(self):
        assert OperationStatus.UNAUTHORIZED.value == "unauthorized"

    def test_operation_status_not_found(self):
        assert OperationStatus.NOT_FOUND.value == "not_found"


@pytest.mark.unit
class TestOperationResultFactories:
    def test_success_factory_minimal(self):
        result = OperationResult.success()
        assert result.status == OperationStatus.SUCCESS

    def test_success_factory_with_data(self):
        data = {"id": "123"}
        result = OperationResult.success(data=data, message="Created")
        assert result.status == OperationStatus.SUCCESS
        assert result.data == data

    def test_error_factory_minimal(self):
        result = OperationResult.error(OperationStatus.PERMANENT_ERROR, "Not found")
        assert result.status == OperationStatus.PERMANENT_ERROR

    def test_error_factory_with_error_code(self):
        result = OperationResult.error(OperationStatus.PERMANENT_ERROR, "Not found", error_code="404")
        assert result.error_code == "404"

    def test_transient_error_factory(self):
        result = OperationResult.transient_error("Timeout", error_code="TIMEOUT")
        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.message == "Timeout"

    def test_permanent_error_factory(self):
        result = OperationResult.permanent_error("Invalid input", error_code="VALIDATION_ERROR")
        assert result.status == OperationStatus.PERMANENT_ERROR


@pytest.mark.unit
class TestOperationResultEdgeCases:
    def test_operation_result_with_nested_data(self):
        data = {"user": {"id": "123", "groups": ["admin"]}}
        result = OperationResult.success(data=data)
        assert result.data["user"]["id"] == "123"

    def test_operation_result_with_empty_data(self):
        result = OperationResult.success(data={})
        assert result.data == {}


@pytest.mark.unit
class TestOperationResultObservability:
    """Test provider and operation fields for observability."""

    def test_success_with_provider_and_operation(self):
        result = OperationResult.success(
            data={"users": []},
            provider="google",
            operation="list_users",
        )
        assert result.provider == "google"
        assert result.operation == "list_users"
        assert result.is_success

    def test_error_with_provider_and_operation(self):
        result = OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            "Rate limited",
            error_code="RATE_LIMITED",
            retry_after=60,
            provider="aws",
            operation="list_groups",
        )
        assert result.provider == "aws"
        assert result.operation == "list_groups"
        assert result.retry_after == 60

    def test_provider_defaults_to_none(self):
        result = OperationResult.success(data={"test": "value"})
        assert result.provider is None

    def test_operation_defaults_to_none(self):
        result = OperationResult.permanent_error("Failed")
        assert result.operation is None


@pytest.mark.unit
class TestOperationResultEnvelopeShape:
    """Frozen envelope, optional success message and internal-only cause."""

    def test_result_is_immutable(self):
        """Assigning to a field raises, so a result cannot change after it is returned."""
        result = OperationResult.success(data={"id": "123"})
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.status = OperationStatus.PERMANENT_ERROR  # type: ignore[misc]

    def test_success_message_defaults_to_none(self):
        """A success built without a message carries None rather than a placeholder string."""
        result = OperationResult.success(data={"id": "123"})
        assert result.message is None

    def test_cause_round_trips_through_constructor(self):
        """The exact exception instance is kept so its traceback survives for diagnostics."""
        exc = RuntimeError("upstream exploded")
        result = OperationResult(status=OperationStatus.TRANSIENT_ERROR, message="Upstream failed", cause=exc)
        assert result.cause is exc

    def test_cause_defaults_to_none(self):
        """Factories never attach a cause unless one is passed explicitly."""
        assert OperationResult.permanent_error("Failed").cause is None

    def test_cause_is_absent_from_repr(self):
        """repr is what reaches logs, so the diagnostic exception must not leak through it."""
        exc = RuntimeError("secret-token-in-message")
        result = OperationResult(status=OperationStatus.PERMANENT_ERROR, message="Failed", cause=exc)
        text = repr(result)
        assert "cause" not in text
        assert "secret-token-in-message" not in text

    def test_equality_ignores_cause(self):
        """Two results with the same outcome compare equal whatever exception was attached."""
        first = OperationResult(status=OperationStatus.PERMANENT_ERROR, message="Failed", cause=ValueError("a"))
        second = OperationResult(status=OperationStatus.PERMANENT_ERROR, message="Failed", cause=KeyError("b"))
        assert first == second

    def test_retry_after_accepts_fractional_seconds(self):
        """Upstream retry hints may be fractional and are stored without truncation."""
        result = OperationResult.transient_error("Rate limited", retry_after=1.5)
        assert result.retry_after == 1.5

    @pytest.mark.parametrize("method", ["map", "bind", "unwrap", "unwrap_or"])
    def test_railway_helpers_are_absent(self, method):
        """The envelope exposes no monad helpers; callers branch on status instead."""
        assert not hasattr(OperationResult, method)

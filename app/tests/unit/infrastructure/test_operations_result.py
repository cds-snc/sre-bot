"""Unit tests for OperationResult and OperationStatus in infrastructure.

Moved from tests/unit/modules/groups/providers/test_base_provider.py (OperationResult/Status parts).
"""

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
        result = OperationResult.error(
            OperationStatus.PERMANENT_ERROR, "Not found", error_code="404"
        )
        assert result.error_code == "404"

    def test_transient_error_factory(self):
        result = OperationResult.transient_error("Timeout", error_code="TIMEOUT")
        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.message == "Timeout"

    def test_permanent_error_factory(self):
        result = OperationResult.permanent_error(
            "Invalid input", error_code="VALIDATION_ERROR"
        )
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

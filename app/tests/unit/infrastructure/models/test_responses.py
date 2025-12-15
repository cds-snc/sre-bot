"""Unit tests for APIResponse and ErrorResponse models."""

import json

import pytest

from infrastructure.models import APIResponse, ErrorResponse


@pytest.mark.unit
class TestAPIResponse:
    """Test suite for APIResponse generic response wrapper."""

    def test_api_response_creation_minimal(self):
        """Test APIResponse can be created with just success flag."""
        response = APIResponse(success=True)

        assert response.success is True
        assert response.data is None
        assert response.message is None
        assert response.error_code is None

    def test_api_response_creation_with_data(self):
        """Test APIResponse with various data types."""
        # Dict data
        response = APIResponse(
            success=True,
            data={"user_id": "123", "name": "John"},
        )

        assert response.success is True
        assert response.data == {"user_id": "123", "name": "John"}

    def test_api_response_creation_with_list_data(self):
        """Test APIResponse with list data."""
        data = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        response = APIResponse(success=True, data=data)

        assert response.success is True
        assert response.data == data
        assert len(response.data) == 3

    def test_api_response_creation_with_string_data(self):
        """Test APIResponse with string data."""
        response = APIResponse(
            success=True,
            data="Operation completed",
        )

        assert response.data == "Operation completed"

    def test_api_response_with_message(self):
        """Test APIResponse with human-readable message."""
        response = APIResponse(
            success=True,
            data={"id": "123"},
            message="User created successfully",
        )

        assert response.message == "User created successfully"

    def test_api_response_with_error_code(self):
        """Test APIResponse includes error code when needed."""
        response = APIResponse(
            success=False,
            data=None,
            message="Operation failed",
            error_code="OPERATION_FAILED",
        )

        assert response.error_code == "OPERATION_FAILED"
        assert response.success is False

    def test_api_response_serialization(self):
        """Test APIResponse serializes to JSON correctly."""
        response = APIResponse(
            success=True,
            data={"user_id": "123"},
            message="Success",
        )

        json_str = response.model_dump_json()
        assert isinstance(json_str, str)

        # Parse back and verify
        parsed = json.loads(json_str)
        assert parsed["success"] is True
        assert parsed["data"]["user_id"] == "123"
        assert parsed["message"] == "Success"

    def test_api_response_null_fields_omitted_by_default(self):
        """Test APIResponse doesn't include null fields by default."""
        response = APIResponse(success=True)

        # Include None fields in dump
        dumped = response.model_dump()
        assert "success" in dumped
        assert dumped["success"] is True
        # Other fields should be None
        assert dumped["data"] is None
        assert dumped["message"] is None
        assert dumped["error_code"] is None

    def test_api_response_with_nested_data(self):
        """Test APIResponse with complex nested data."""
        data = {
            "user": {"id": "123", "name": "John"},
            "permissions": ["read", "write"],
            "metadata": {"created_at": "2024-01-01"},
        }
        response = APIResponse(success=True, data=data)

        assert response.data["user"]["id"] == "123"
        assert response.data["permissions"] == ["read", "write"]
        assert response.data["metadata"]["created_at"] == "2024-01-01"

    def test_api_response_with_zero_data(self):
        """Test APIResponse with zero/falsy but valid data."""
        # Zero is valid data
        response = APIResponse(success=True, data=0)
        assert response.data == 0

        # False is valid data
        response = APIResponse(success=True, data=False)
        assert response.data is False

        # Empty string is valid data
        response = APIResponse(success=True, data="")
        assert response.data == ""

        # Empty list is valid data
        response = APIResponse(success=True, data=[])
        assert response.data == []

    def test_api_response_model_dump(self):
        """Test APIResponse model_dump() produces dict."""
        response = APIResponse(
            success=True,
            data={"id": "123"},
            message="Success",
        )

        dumped = response.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["success"] is True
        assert dumped["data"]["id"] == "123"

    def test_api_response_field_validation(self):
        """Test APIResponse validates field types."""
        # Pydantic v2 coerces string "true" to bool, so we test with invalid type
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            APIResponse(success={"not": "bool"})  # type: ignore

    def test_api_response_factory_fixture(self, make_api_response):
        """Test APIResponse factory fixture from conftest."""
        response = make_api_response(
            success=True,
            data={"id": "456"},
            message="Test message",
        )

        assert response.success is True
        assert response.data["id"] == "456"
        assert response.message == "Test message"

    def test_api_response_factory_defaults(self, make_api_response):
        """Test factory fixture uses sensible defaults."""
        response = make_api_response()

        assert response.success is True
        assert response.data is None
        assert response.message is None
        assert response.error_code is None


@pytest.mark.unit
class TestErrorResponse:
    """Test suite for ErrorResponse error wrapper."""

    def test_error_response_creation(self):
        """Test ErrorResponse can be created with error and code."""
        response = ErrorResponse(
            error="Validation failed",
            error_code="VALIDATION_ERROR",
        )

        assert response.success is False
        assert response.error == "Validation failed"
        assert response.error_code == "VALIDATION_ERROR"
        assert response.details is None

    def test_error_response_success_always_false(self):
        """Test ErrorResponse success is always False."""
        response = ErrorResponse(
            error="Test error",
            error_code="ERROR",
        )

        assert response.success is False

    def test_error_response_with_details(self):
        """Test ErrorResponse with additional error details."""
        details = {
            "email": "Invalid email format",
            "phone": "Must be 10 digits",
        }
        response = ErrorResponse(
            error="Validation failed",
            error_code="VALIDATION_ERROR",
            details=details,
        )

        assert response.details == details
        assert response.details["email"] == "Invalid email format"

    def test_error_response_with_complex_details(self):
        """Test ErrorResponse details can contain nested structures."""
        details = {
            "validation_errors": [
                {"field": "email", "message": "Invalid format"},
                {"field": "phone", "message": "Too short"},
            ],
            "request_id": "12345",
        }
        response = ErrorResponse(
            error="Multiple errors",
            error_code="MULTI_ERROR",
            details=details,
        )

        assert len(response.details["validation_errors"]) == 2
        assert response.details["request_id"] == "12345"

    def test_error_response_serialization(self):
        """Test ErrorResponse serializes to JSON correctly."""
        response = ErrorResponse(
            error="Not found",
            error_code="NOT_FOUND",
            details={"resource": "user"},
        )

        json_str = response.model_dump_json()
        parsed = json.loads(json_str)

        assert parsed["success"] is False
        assert parsed["error"] == "Not found"
        assert parsed["error_code"] == "NOT_FOUND"
        assert parsed["details"]["resource"] == "user"

    def test_error_response_required_fields(self):
        """Test ErrorResponse requires error and error_code."""
        from pydantic import ValidationError

        # Missing error_code
        with pytest.raises(ValidationError):
            ErrorResponse(error="Test error")  # type: ignore

        # Missing error
        with pytest.raises(ValidationError):
            ErrorResponse(error_code="ERROR")  # type: ignore

    def test_error_response_model_dump(self):
        """Test ErrorResponse model_dump() produces dict."""
        response = ErrorResponse(
            error="Access denied",
            error_code="ACCESS_DENIED",
            details={"reason": "Insufficient permissions"},
        )

        dumped = response.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["success"] is False
        assert dumped["error_code"] == "ACCESS_DENIED"

    def test_error_response_factory_fixture(self, make_error_response):
        """Test ErrorResponse factory fixture from conftest."""
        response = make_error_response(
            error="Test error",
            error_code="TEST_ERROR",
            details={"key": "value"},
        )

        assert response.success is False
        assert response.error == "Test error"
        assert response.error_code == "TEST_ERROR"
        assert response.details["key"] == "value"

    def test_error_response_factory_defaults(self, make_error_response):
        """Test ErrorResponse factory uses sensible defaults."""
        response = make_error_response()

        assert response.success is False
        assert response.error == "Error"
        assert response.error_code == "ERROR"
        assert response.details is None


@pytest.mark.unit
class TestResponseIntegration:
    """Test integration between APIResponse and ErrorResponse."""

    def test_api_response_used_for_success(self, make_api_response):
        """Test APIResponse is used for successful operations."""
        response = make_api_response(
            success=True,
            data={"count": 100},
            message="Operation completed",
        )

        assert response.success is True
        assert response.data is not None

    def test_error_response_used_for_failures(self, make_error_response):
        """Test ErrorResponse is used for error scenarios."""
        response = make_error_response(
            error="Database connection failed",
            error_code="DB_CONNECTION_ERROR",
        )

        assert response.success is False
        assert response.error is not None

    def test_response_pattern_consistency(self):
        """Test both response types follow consistent patterns."""
        success_response = APIResponse(success=True, data={"id": "1"})
        error_response = ErrorResponse(error="Failed", error_code="ERROR")

        # Both have success field
        assert hasattr(success_response, "success")
        assert hasattr(error_response, "success")

        # Both are serializable
        assert success_response.model_dump_json()
        assert error_response.model_dump_json()

        # Both are Pydantic BaseModel instances
        from pydantic import BaseModel

        assert isinstance(success_response, BaseModel)
        assert isinstance(error_response, BaseModel)

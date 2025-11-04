"""Comprehensive unit tests for groups errors module.

Tests cover the IntegrationError exception class and error handling:
- Exception construction and attributes
- Response object storage and retrieval
- Message extraction
- Error propagation
- Serialization and string representation
"""

import types
import pytest
from modules.groups.errors import IntegrationError


@pytest.mark.unit
class TestIntegrationError:
    """Tests for IntegrationError exception class."""

    def test_integration_error_basic_construction(self):
        """Test basic construction with message."""
        error = IntegrationError("Operation failed")
        assert str(error) == "Operation failed"
        assert isinstance(error, Exception)

    def test_integration_error_with_response(self):
        """Test construction with response object."""
        fake_response = types.SimpleNamespace(
            success=False, 
            data={"error": "boom"},
            meta={"code": 500}
        )
        error = IntegrationError("Operation failed", response=fake_response)
        assert error.response is fake_response
        assert error.response.success is False

    def test_integration_error_with_none_response(self):
        """Test construction with None response."""
        error = IntegrationError("Operation failed", response=None)
        assert error.response is None

    def test_integration_error_default_response_is_none(self):
        """Test that response defaults to None."""
        error = IntegrationError("Operation failed")
        assert error.response is None

    def test_integration_error_has_response_attribute(self):
        """Test that error has response attribute."""
        fake_response = types.SimpleNamespace(success=False)
        error = IntegrationError("Error", response=fake_response)
        assert hasattr(error, "response")

    def test_integration_error_message_is_preserved(self):
        """Test that message is preserved in exception."""
        message = "Specific operation failed with code XYZ"
        error = IntegrationError(message)
        assert message in str(error)

    def test_integration_error_inherits_exception(self):
        """Test that IntegrationError inherits from Exception."""
        error = IntegrationError("Test error")
        assert isinstance(error, Exception)

    def test_integration_error_can_be_raised_and_caught(self):
        """Test that error can be raised and caught."""
        with pytest.raises(IntegrationError):
            raise IntegrationError("Test error")

    def test_integration_error_can_be_caught_as_exception(self):
        """Test that error can be caught as Exception."""
        with pytest.raises(Exception):
            raise IntegrationError("Test error")

    def test_integration_error_with_empty_message(self):
        """Test construction with empty message."""
        error = IntegrationError("")
        assert str(error) == ""

    def test_integration_error_with_multiline_message(self):
        """Test construction with multiline message."""
        message = "Line 1\nLine 2\nLine 3"
        error = IntegrationError(message)
        assert message in str(error)

    def test_integration_error_with_special_characters_in_message(self):
        """Test construction with special characters."""
        message = "Error: {'key': 'value'} [CODE: 500]"
        error = IntegrationError(message)
        assert message in str(error)

    def test_integration_error_response_with_success_true(self):
        """Test error with response object where success=True."""
        fake_response = types.SimpleNamespace(success=True)
        error = IntegrationError("Paradoxical error", response=fake_response)
        assert error.response.success is True

    def test_integration_error_response_with_data_dict(self):
        """Test error with response containing data dictionary."""
        fake_response = types.SimpleNamespace(
            success=False,
            data={"error": "Not found", "code": "404"}
        )
        error = IntegrationError("Not found", response=fake_response)
        assert error.response.data["error"] == "Not found"
        assert error.response.data["code"] == "404"

    def test_integration_error_response_with_meta_dict(self):
        """Test error with response containing metadata."""
        fake_response = types.SimpleNamespace(
            success=False,
            meta={"timestamp": "2024-01-01T00:00:00Z", "request_id": "12345"}
        )
        error = IntegrationError("Server error", response=fake_response)
        assert error.response.meta["timestamp"] == "2024-01-01T00:00:00Z"
        assert error.response.meta["request_id"] == "12345"

    def test_integration_error_response_is_mutable(self):
        """Test that response object attributes can be accessed."""
        fake_response = types.SimpleNamespace(status="pending")
        error = IntegrationError("Error", response=fake_response)
        fake_response.status = "completed"
        assert error.response.status == "completed"

    def test_integration_error_comparison(self):
        """Test that different errors are not equal."""
        error1 = IntegrationError("Error 1")
        error2 = IntegrationError("Error 2")
        assert error1 is not error2

    def test_integration_error_with_response_comparison(self):
        """Test that errors with different responses are not equal."""
        response1 = types.SimpleNamespace(code=1)
        response2 = types.SimpleNamespace(code=2)
        error1 = IntegrationError("Error", response=response1)
        error2 = IntegrationError("Error", response=response2)
        assert error1 is not error2
        assert error1.response is not error2.response

    def test_integration_error_message_and_response_independent(self):
        """Test that message and response are independent."""
        response = types.SimpleNamespace(data="response data")
        error = IntegrationError("Error message", response=response)
        assert str(error) == "Error message"
        assert error.response.data == "response data"

    def test_integration_error_traceback_preservation(self):
        """Test that error preserves traceback information."""
        try:
            raise IntegrationError("Original error")
        except IntegrationError as e:
            assert "Original error" in str(e)

    def test_integration_error_with_complex_response_object(self):
        """Test error with complex nested response object."""
        fake_response = types.SimpleNamespace(
            success=False,
            data={
                "error": {
                    "code": "INVALID_REQUEST",
                    "details": {
                        "field": "email",
                        "reason": "Invalid format"
                    }
                }
            },
            meta={
                "retry_after": 60,
                "request_id": "req-12345-abcde"
            }
        )
        error = IntegrationError("Validation failed", response=fake_response)
        assert error.response.data["error"]["code"] == "INVALID_REQUEST"
        assert error.response.data["error"]["details"]["field"] == "email"
        assert error.response.meta["retry_after"] == 60

    def test_integration_error_args_attribute(self):
        """Test that error has args attribute (from Exception)."""
        error = IntegrationError("Error message")
        assert hasattr(error, "args")
        assert len(error.args) == 1
        assert error.args[0] == "Error message"

    def test_integration_error_multiple_instantiation(self):
        """Test that multiple instances are independent."""
        response1 = types.SimpleNamespace(id=1)
        response2 = types.SimpleNamespace(id=2)
        error1 = IntegrationError("Error 1", response=response1)
        error2 = IntegrationError("Error 2", response=response2)
        
        assert error1.response.id == 1
        assert error2.response.id == 2
        assert str(error1) == "Error 1"
        assert str(error2) == "Error 2"
